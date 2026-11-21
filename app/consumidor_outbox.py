import hashlib
import http.client
import json
import re
import sys
import time
from urllib.parse import urlparse

from app import db
from app.config import Configuracao, carregar_config
from app.migracoes import adaptar_marcadores
from app.repositorio import Repositorio


class FalhaPublicacao(RuntimeError):
    pass


def _descrever_erro(erro: Exception) -> str:
    texto = re.sub(r"https?://\S+", "<url>", str(erro).strip())
    return (texto or type(erro).__name__)[:500]


class PublicadorLocal:
    def publicar(self, evento: dict) -> None:
        payload = str(evento.get("payload") or "")
        registo = {
            "publicador": "local",
            "estado": "PUBLICADO",
            "evento": evento["evento"],
            "id": evento["id"],
            "criado_em": db.agora(),
            "payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16],
        }
        print(json.dumps(registo, sort_keys=True), flush=True)


class PublicadorWebhook:
    def __init__(
        self,
        configuracao: Configuracao | None = None,
        url: str | None = None,
        timeout: float = 5.0,
        retries: int = 2,
    ):
        config = configuracao or carregar_config()
        self.url = url or config.webhook_url
        self.timeout = timeout
        self.retries = max(0, retries)
        if not self.url:
            raise ValueError("OUTBOX_WEBHOOK_URL nao configurada")
        destino = urlparse(self.url)
        if destino.scheme not in {"http", "https"} or not destino.hostname:
            raise ValueError("OUTBOX_WEBHOOK_URL deve ser http:// ou https://")
        self.esquema = destino.scheme
        self.anfitriao = destino.hostname
        self.porta = destino.port or (443 if destino.scheme == "https" else 80)
        self.caminho = destino.path or "/"
        if destino.query:
            self.caminho = f"{self.caminho}?{destino.query}"

    def publicar(self, evento: dict) -> None:
        try:
            conteudo = json.loads(evento.get("payload") or "null")
        except (TypeError, ValueError):
            conteudo = evento.get("payload")
        corpo = json.dumps(
            {
                "id": evento["id"],
                "evento": evento["evento"],
                "payload": conteudo,
                "criado_em": db.agora(),
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        classe = http.client.HTTPSConnection if self.esquema == "https" else http.client.HTTPConnection
        ultimo_erro = FalhaPublicacao("webhook sem resposta")
        for tentativa in range(self.retries + 1):
            conexao_http = None
            try:
                conexao_http = classe(self.anfitriao, self.porta, timeout=self.timeout)
                conexao_http.request(
                    "POST",
                    self.caminho,
                    body=corpo,
                    headers={"Content-Type": "application/json", "User-Agent": "his-outbox/1"},
                )
                resposta = conexao_http.getresponse()
                estado = resposta.status
                resposta.read()
                if 200 <= estado < 300:
                    return
                ultimo_erro = FalhaPublicacao(f"webhook respondeu HTTP {estado}")
            except (OSError, http.client.HTTPException):
                ultimo_erro = FalhaPublicacao("webhook indisponivel")
            finally:
                if conexao_http is not None:
                    conexao_http.close()
            if tentativa < self.retries:
                time.sleep(min(0.25 * (2 ** tentativa), 1.0))
        raise ultimo_erro


def publicador_padrao(configuracao: Configuracao | None = None):
    config = configuracao or carregar_config()
    if config.webhook_url:
        return PublicadorWebhook(configuracao=config)
    return PublicadorLocal()


def publicar_pendentes(
    limite: int = 100,
    publicador=None,
    repositorio: Repositorio | None = None,
) -> dict:
    repositorio = repositorio or Repositorio()
    publicador = publicador or publicador_padrao(repositorio.configuracao)
    resultado = {"processados": 0, "eventos": [], "falhas": []}
    with repositorio.ligacao() as conexao:
        pendentes = conexao.execute(
            adaptar_marcadores(
                "SELECT id, evento, payload FROM outbox WHERE estado = 'PENDENTE' "
                "ORDER BY id LIMIT ?",
                conexao,
            ),
            (limite,),
        ).fetchall()
        for pendente in pendentes:
            identificador = pendente["id"]
            episodio = {
                "id": identificador,
                "evento": pendente["evento"],
                "payload": pendente["payload"],
            }
            try:
                publicador.publicar(episodio)
            except Exception as erro:
                mensagem = _descrever_erro(erro)
                conexao.execute(
                    adaptar_marcadores(
                        "UPDATE outbox SET tentativas = tentativas + 1, ultimo_erro = ? WHERE id = ?",
                        conexao,
                    ),
                    (mensagem, identificador),
                )
                resultado["falhas"].append(
                    {"id": identificador, "evento": episodio["evento"], "erro": mensagem[:200]}
                )
                continue
            conexao.execute(
                adaptar_marcadores(
                    "UPDATE outbox SET estado = 'PUBLICADO', tentativas = tentativas + 1, "
                    "publicado_em = ?, ultimo_erro = NULL WHERE id = ?",
                    conexao,
                ),
                (db.agora(), identificador),
            )
            resultado["eventos"].append({"id": identificador, "evento": episodio["evento"]})
        conexao.commit()
    resultado["processados"] = len(resultado["eventos"])
    return resultado


def main() -> None:
    db.inicializar()
    Repositorio().aplicar_migracoes()
    while True:
        resultado = publicar_pendentes()
        print(json.dumps(resultado, sort_keys=True), flush=True)
        if "--once" in sys.argv:
            break
        time.sleep(5)


if __name__ == "__main__":
    main()

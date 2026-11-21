import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent.parent


def _texto(nome: str, valor: str, obrigatorio: bool = True) -> str:
    resultado = valor.strip()
    if obrigatorio and not resultado:
        raise ValueError(f"{nome} nao pode ser vazio")
    return resultado


def _caminho(nome: str, valor: str) -> Path:
    return Path(_texto(nome, valor)).expanduser()


def _porta(nome: str, valor: str) -> int:
    try:
        numero = int(valor.strip())
    except ValueError as exc:
        raise ValueError(f"{nome} deve ser um numero inteiro") from exc
    if not 1 <= numero <= 65535:
        raise ValueError(f"{nome} deve estar entre 1 e 65535")
    return numero


def _dsn(valor: str) -> str | None:
    resultado = valor.strip()
    if not resultado:
        return None
    if not resultado.lower().startswith(("postgresql://", "postgres://")):
        raise ValueError("HIS_DB_DSN deve usar o esquema postgresql:// ou postgres://")
    return resultado


def _webhook(valor: str) -> str:
    resultado = valor.strip()
    if not resultado:
        return ""
    endereco = urlparse(resultado)
    if endereco.scheme not in {"http", "https"} or not endereco.netloc:
        raise ValueError("OUTBOX_WEBHOOK_URL deve ser um URL http ou https valido")
    return resultado


@dataclass(frozen=True)
class Configuracao:
    caminho_db: Path
    dsn: str | None
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    postgres_db: str
    redis_host: str
    redis_port: int
    rabbitmq_host: str
    rabbitmq_port: int
    webhook_url: str
    chave_assinatura_path: Path

    @property
    def modo_publicador(self) -> str:
        return "webhook" if self.webhook_url else "local"

    def __repr__(self) -> str:
        return (
            "Configuracao("
            f"caminho_db={self.caminho_db}, "
            f"dsn={'definido' if self.dsn else 'vazio'}, "
            f"postgres_host={self.postgres_host}, "
            f"postgres_port={self.postgres_port}, "
            f"postgres_user={self.postgres_user}, "
            "postgres_password=***, "
            f"postgres_db={self.postgres_db}, "
            f"redis_host={self.redis_host}, "
            f"redis_port={self.redis_port}, "
            f"rabbitmq_host={self.rabbitmq_host}, "
            f"rabbitmq_port={self.rabbitmq_port}, "
            f"webhook_url={'definido' if self.webhook_url else 'vazio'}, "
            f"chave_assinatura_path={self.chave_assinatura_path})"
        )


def carregar_config() -> Configuracao:
    return Configuracao(
        caminho_db=_caminho(
            "HIS_DB_PATH", os.environ.get("HIS_DB_PATH", str(BASE / "data" / "his.db"))
        ),
        dsn=_dsn(os.environ.get("HIS_DB_DSN", "")),
        postgres_host=_texto("POSTGRES_HOST", os.environ.get("POSTGRES_HOST", "localhost")),
        postgres_port=_porta("POSTGRES_PORT", os.environ.get("POSTGRES_PORT", "5432")),
        postgres_user=_texto("POSTGRES_USER", os.environ.get("POSTGRES_USER", "his")),
        postgres_password=_texto(
            "POSTGRES_PASSWORD", os.environ.get("POSTGRES_PASSWORD", ""), obrigatorio=False
        ),
        postgres_db=_texto("POSTGRES_DB", os.environ.get("POSTGRES_DB", "his")),
        redis_host=_texto("REDIS_HOST", os.environ.get("REDIS_HOST", "localhost")),
        redis_port=_porta("REDIS_PORT", os.environ.get("REDIS_PORT", "6379")),
        rabbitmq_host=_texto("RABBITMQ_HOST", os.environ.get("RABBITMQ_HOST", "localhost")),
        rabbitmq_port=_porta("RABBITMQ_PORT", os.environ.get("RABBITMQ_PORT", "5672")),
        webhook_url=_webhook(os.environ.get("OUTBOX_WEBHOOK_URL", "")),
        chave_assinatura_path=_caminho(
            "HIS_SIGNING_KEY_PATH",
            os.environ.get("HIS_SIGNING_KEY_PATH", str(BASE / "data" / "his_signing.key")),
        ),
    )


CONFIGURACAO = carregar_config()

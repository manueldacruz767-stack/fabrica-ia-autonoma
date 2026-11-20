import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from google import genai

RAIZ = Path(__file__).resolve().parent
ARQUIVO_ENV = RAIZ / ".env"
DIRETORIO_SKILLS = RAIZ / "skills"

load_dotenv(ARQUIVO_ENV)

MODELOS_PADRAO = (
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
)

VALORES_VERDADEIROS = {"1", "true", "sim", "yes", "on"}
OPERADORES_PERIGOSOS = (";", "&&", "||", "|", "`", "$(", ">", "<", "\n", "\r")
COMANDOS_PERMITIDOS = {
    "git": {"status", "log", "diff", "remote", "branch"},
    "gh": {"auth", "repo", "run", "workflow"},
    "npm": {"--version", "list"},
    "pip": {"--version", "list", "show"},
    "pip3": {"--version", "list", "show"},
    "ls": set(),
    "vercel": {"--version", "whoami", "list", "deploy"},
    "docker": {"--version", "ps"},
}
NOME_SKILL_VALIDO = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass(frozen=True)
class Geracao:
    texto: str
    modelo: str


def chave_api() -> str:
    valores = dotenv_values(ARQUIVO_ENV)
    return str(
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or valores.get("GEMINI_API_KEY")
        or valores.get("GOOGLE_API_KEY")
        or ""
    ).strip()


def tem_chave_api() -> bool:
    return bool(chave_api())


def modelos_candidatos(modelo: str | None = None) -> list[str]:
    preferido = str(modelo or os.getenv("GEMINI_MODEL") or "").strip().removeprefix("models/")
    if not preferido:
        return list(MODELOS_PADRAO)
    return [preferido] + [item for item in MODELOS_PADRAO if item != preferido]


def carregar_skill(nome_agente: str) -> str:
    nome_base = Path(str(nome_agente)).name
    if nome_base.endswith(".md"):
        nome_base = nome_base[:-3]
    if not NOME_SKILL_VALIDO.fullmatch(nome_base):
        return f"Atua como especialista em {nome_agente}, com rigor técnico e boas práticas."
    caminho = DIRETORIO_SKILLS / f"{nome_base}.md"
    if caminho.is_file():
        return caminho.read_text(encoding="utf-8").strip()
    return f"Atua como especialista em {nome_base}, com rigor técnico e boas práticas."


def construir_prompt(agente: str, tarefa: str, contexto: str = "") -> str:
    bloco_contexto = f"\n[CONTEXTO_OPERACIONAL]\n{contexto.strip()}\n" if contexto and contexto.strip() else ""
    return (
        f"[AGENTE]\n{agente}\n\n"
        "[REGRA_OBRIGATORIA]\nConsulta e aplica a skill oficial abaixo antes de qualquer raciocinio. "
        "Nao alteres a skill; cumpre-a.\n\n"
        f"[SKILL_OFICIAL]\n{carregar_skill(agente)}\n[/SKILL_OFICIAL]\n"
        f"{bloco_contexto}\n"
        f"[TAREFA]\n{tarefa}\n\n"
        "[FORMATO]\nResponde em Markdown, em portugues de Portugal, com seccoes curtas e verificaveis. "
        "Nao afirmes que executaste comandos, commits, builds, deploys ou consultas a base de dados "
        "a menos que o contexto contenha a saida real dessas acoes."
    )


def gerar_texto(prompt: str, modelo: str | None = None, tentativas: int = 2) -> Geracao:
    chave = chave_api()
    if not chave:
        raise RuntimeError("GEMINI_API_KEY nao configurada. Define o segredo no GitHub ou a variavel no .env.")
    cliente = genai.Client(api_key=chave)
    falhas: list[str] = []
    total_tentativas = max(1, tentativas)

    for nome_modelo in modelos_candidatos(modelo):
        for tentativa in range(1, total_tentativas + 1):
            try:
                resposta = cliente.models.generate_content(
                    model=nome_modelo,
                    contents=prompt,
                    config={"temperature": 0.4},
                )
                texto = str(getattr(resposta, "text", "") or "").strip()
                if not texto:
                    raise RuntimeError("resposta vazia")
                return Geracao(texto=texto, modelo=nome_modelo)
            except Exception as exc:
                codigo = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                resumo = str(exc).splitlines()[0][:140]
                falhas.append(f"{nome_modelo} tentativa {tentativa}: {type(exc).__name__} {codigo or ''} {resumo}".strip())
                if codigo in (400, 403, 404):
                    break
                if tentativa < total_tentativas:
                    time.sleep(1.5 * tentativa)

    raise RuntimeError("Nenhum modelo Gemini respondeu.\n" + "\n".join(falhas[-12:]))


def texto_validacao(agente: str, tarefa: str) -> str:
    primeira_linha = carregar_skill(agente).splitlines()[0] if carregar_skill(agente) else "(sem skill)"
    return (
        f"## {agente}\n\n"
        "Modo de validacao: prompt e skill carregados sem chamada a API.\n\n"
        f"**Tarefa:** {tarefa}\n\n"
        f"**Skill:** {primeira_linha}"
    )


def acoes_externas_ativas() -> bool:
    return str(os.getenv("FABRICA_ACOES_EXTERNAS", "")).strip().lower() in VALORES_VERDADEIROS


def validar_comando(comando: str) -> list[str]:
    if not isinstance(comando, str) or not comando.strip():
        raise ValueError("comando vazio")
    if any(operador in comando for operador in OPERADORES_PERIGOSOS):
        raise ValueError("operadores de encadeamento nao permitidos")
    try:
        partes = shlex.split(comando)
    except ValueError as exc:
        raise ValueError("comando malformado") from exc
    if not partes or partes[0] not in COMANDOS_PERMITIDOS:
        raise ValueError(f"comando nao permitido: {partes[0] if partes else 'vazio'}")
    subcomandos = COMANDOS_PERMITIDOS[partes[0]]
    if subcomandos and (len(partes) < 2 or partes[1] not in subcomandos):
        raise ValueError(f"subcomando nao permitido para {partes[0]}")
    if partes[0] == "vercel" and "--prod" in partes:
        raise ValueError("deploy em producao bloqueado; usa apenas preview")
    return partes


def executar_comando(comando: str, cwd: str | None = None, timeout: int = 60) -> str:
    if not acoes_externas_ativas():
        return f"[BLOQUEADO] FABRICA_ACOES_EXTERNAS desativado; nao executado: {comando}"
    try:
        partes = validar_comando(comando)
    except ValueError as exc:
        return f"[RECUSADO] {exc}"
    try:
        resultado = subprocess.run(
            partes,
            shell=False,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"[ERRO] {type(exc).__name__}: {exc}"
    estado = "OK" if resultado.returncode == 0 else f"FALHOU ({resultado.returncode})"
    corpo = "\n".join(parte for parte in ((resultado.stdout or "").strip(), (resultado.stderr or "").strip()) if parte)
    return f"[{estado}] {comando}\n{corpo[:4000]}".rstrip()


def montar_relatorio(ideia: str, secoes: list[tuple[str, str, str | None]]) -> str:
    linhas = ["# Fabrica de IA Autonoma - Relatorio Final", "", f"**Ideia:** {ideia}", ""]
    for agente, texto, modelo in secoes:
        if modelo:
            linhas.extend([f"## {agente}", "", f"_Modelo: {modelo}_", "", texto, "", "---", ""])
        else:
            linhas.extend([f"## {agente}", "", texto, "", "---", ""])
    return "\n".join(linhas).rstrip() + "\n"


def salvar_saida(conteudo: str, caminho: str | Path) -> Path:
    destino = Path(caminho)
    if not destino.is_absolute():
        destino = RAIZ / destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8")
    return destino

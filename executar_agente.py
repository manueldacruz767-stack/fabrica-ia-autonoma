import argparse
import os
import sys

from fabrica_core import (
    carregar_contexto,
    construir_prompt,
    executar_comando,
    gerar_texto,
    salvar_saida,
    tem_chave_api,
    texto_validacao,
)
from pesquisa_web import pesquisar_web

TAREFA_PADRAO = (
    "Analisa o estado atual da infraestrutura, identifica riscos concretos e propõe "
    "um plano de automação segura e verificável para o projeto."
)


def executar_agente_autonomo(
    nome_agente: str,
    tarefa: str,
    query_pesquisa: str | None = None,
    comando_sistema: str | None = None,
    modelo: str | None = None,
    tentativas: int = 2,
    dry_run: bool = False,
    saida: str | None = None,
    contexto_documentos: str = "",
) -> str:
    print(f"[Fabrica] Agente despertado: {nome_agente}")

    contexto = ""
    if contexto_documentos:
        contexto += f"[DOCUMENTOS]\n{contexto_documentos}\n"
    if query_pesquisa:
        print(f"[Fabrica] Pesquisa web: {query_pesquisa}")
        contexto += f"[PESQUISA_WEB]\n{pesquisar_web(query_pesquisa)}\n"
    if comando_sistema:
        print(f"[Fabrica] Comando solicitado: {comando_sistema}")
        contexto += f"[SISTEMA]\n{executar_comando(comando_sistema)}\n"

    prompt = construir_prompt(nome_agente, tarefa, contexto)
    if dry_run:
        relatorio = texto_validacao(nome_agente, tarefa)
        if contexto:
            relatorio += f"\n\n{contexto}"
    else:
        geracao = gerar_texto(prompt, modelo, tentativas)
        print(f"[Fabrica] Modelo utilizado: {geracao.modelo}")
        relatorio = geracao.texto

    print(f"\n=== RELATORIO DO AGENTE ({nome_agente}) ===\n{relatorio}\n{'=' * 70}")
    if saida:
        destino = salvar_saida(relatorio, saida)
        print(f"[Fabrica] Relatorio gravado em {destino}")
    return relatorio


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description="Executa um agente especializado da Fabrica de IA")
    analisador.add_argument("--agente", default="devops", help="Nome da skill do agente")
    analisador.add_argument("--tarefa", default=os.getenv("PROJETO_IDEIA", TAREFA_PADRAO), help="Tarefa a executar")
    analisador.add_argument(
        "--contexto",
        default=os.getenv("FABRICA_CONTEXTO", ""),
        help="Ficheiro ou diretorio .md com documentos de contexto",
    )
    analisador.add_argument("--pesquisa", default=None, help="Consulta opcional para a pesquisa web")
    analisador.add_argument("--comando", default=None, help="Comando opcional (exige FABRICA_ACOES_EXTERNAS=1)")
    analisador.add_argument("--saida", default=None, help="Caminho opcional do relatorio")
    analisador.add_argument("--modelo", default=None, help="Modelo Gemini preferido")
    analisador.add_argument("--tentativas", type=int, default=2, help="Tentativas por modelo")
    analisador.add_argument("--dry-run", action="store_true", help="Valida o fluxo sem chamar a API")
    argumentos = analisador.parse_args(argv)

    if not argumentos.dry_run and not tem_chave_api():
        print("Erro: GEMINI_API_KEY nao encontrada. Define o segredo no GitHub ou a variavel no .env.", file=sys.stderr)
        return 2

    try:
        documentos = carregar_contexto(argumentos.contexto)
    except (OSError, ValueError) as exc:
        print(f"Erro ao carregar contexto: {exc}", file=sys.stderr)
        return 1

    try:
        executar_agente_autonomo(
            nome_agente=argumentos.agente,
            tarefa=argumentos.tarefa,
            contexto_documentos=documentos,
            query_pesquisa=argumentos.pesquisa,
            comando_sistema=argumentos.comando,
            modelo=argumentos.modelo,
            tentativas=argumentos.tentativas,
            dry_run=argumentos.dry_run,
            saida=argumentos.saida,
        )
    except RuntimeError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

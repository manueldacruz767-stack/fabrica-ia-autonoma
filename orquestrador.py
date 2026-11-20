import argparse
import os
import sys

from fabrica_core import (
    carregar_contexto,
    construir_prompt,
    gerar_texto,
    montar_relatorio,
    salvar_saida,
    tem_chave_api,
    texto_validacao,
)

AGENTES_TAREFAS = (
    (
        "scrum_master",
        "Produz o backlog da Versao 0.1 com historias, prioridade, sprints e criterios de aceicao verificaveis.",
    ),
    (
        "arquiteto",
        "Decide uma stack simples e proporcional ao projeto e desenha a arquitetura em camadas, com limites claros entre componentes.",
    ),
    (
        "programador",
        "Converte a arquitetura num plano de implementacao ordenado, com ficheiros, responsabilidades e riscos tecnicos.",
    ),
    (
        "qa",
        "Define o plano de testes unitarios, integracao e aceitacao, com comandos concretos e critérios de conclusao.",
    ),
)


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description="Orquestrador da Fabrica de IA Autonoma")
    analisador.add_argument("--ideia", default=os.getenv("PROJETO_IDEIA", "Sistema de gestao de tarefas"), help="Ideia do projeto")
    analisador.add_argument(
        "--contexto",
        default=os.getenv("FABRICA_CONTEXTO", ""),
        help="Ficheiro ou diretorio .md com documentos de contexto",
    )
    analisador.add_argument("--saida", default="projeto_final.md", help="Caminho do relatorio gerado")
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

    print(f"[Fabrica] Ideia recebida: {argumentos.ideia}")
    if documentos:
        print(f"[Fabrica] Contexto carregado: {len(documentos)} caracteres")
    secoes = []

    for agente, tarefa in AGENTES_TAREFAS:
        contexto = f"Ideia do projeto: {argumentos.ideia}\n{documentos}".strip()
        prompt = construir_prompt(agente, tarefa, contexto)
        if argumentos.dry_run:
            texto = texto_validacao(agente, tarefa)
            modelo = None
        else:
            print(f"[Fabrica] A executar agente {agente}...")
            try:
                geracao = gerar_texto(prompt, argumentos.modelo, argumentos.tentativas)
            except RuntimeError as exc:
                print(f"Erro: {exc}", file=sys.stderr)
                return 1
            texto = geracao.texto
            modelo = geracao.modelo
            print(f"[Fabrica] {agente} concluido com {modelo}.")
        secoes.append((agente, texto, modelo))

    destino = salvar_saida(montar_relatorio(argumentos.ideia, secoes), argumentos.saida)
    print(f"[Fabrica] Relatorio gravado em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

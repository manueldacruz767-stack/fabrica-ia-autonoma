import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    print("Erro: GEMINI_API_KEY não encontrada no ficheiro .env", file=sys.stderr)
    sys.exit(1)

SKILLS_DIR = Path("skills")

def carregar_skill(nome_agente: str) -> str:
    """Lê estritamente o ficheiro de diretrizes/skill do agente. As skills são regras fixas."""
    ficheiro_skill = SKILLS_DIR / f"{nome_agente}.md"
    if ficheiro_skill.exists():
        with open(ficheiro_skill, "r", encoding="utf-8") as f:
            return f.read()
    return f"Aja estritamente de acordo com a sua especialidade como {nome_agente.upper()} e cumpra os padrões da fábrica."

def criar_instrucao_com_skill(nome_agente: str, instrucao_base: str) -> str:
    """Obriga o agente a assimilar a sua skill como regra inalterável antes de iniciar."""
    conteudo_skill = carregar_skill(nome_agente)
    
    prompt_rigoroso = f"""
[DIRETIVA OBRIGATÓRIA DE EXECUÇÃO - LEI SUPREMA]
Antes de iniciar qualquer raciocínio, planeamento ou ação, DEVE consultar e assimilar rigorosamente a sua skill oficial abaixo. As diretrizes descritas na skill são leis absolutas para o seu comportamento, stack tecnológica e entregas. Você NÃO altera a skill; você cumpre-a rigorosamente.

--- SKILL OFICIAL DO AGENTE ({nome_agente.upper()}) ---
{conteudo_skill}
------------------------------------------------------

[TAREFAS E CONTEXTO OPERACIONAL ATUAL]
{instrucao_base}
"""
    return prompt_rigoroso

if __name__ == "__main__":
    print("[Fábrica de IA Autónoma] Orquestrador central carregado com sucesso.")

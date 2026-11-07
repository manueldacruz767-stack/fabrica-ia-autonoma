import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis do .env local
load_dotenv()

# Validar chaves essenciais
if not os.getenv("GEMINI_API_KEY"):
    print("Erro: GEMINI_API_KEY não encontrada no ficheiro .env", file=sys.stderr)
    sys.exit(1)

SKILLS_DIR = Path("skills")

def carregar_skill(nome_agente: str) -> str:
    """Lê o ficheiro de diretrizes/skill do agente específico."""
    ficheiro_skill = SKILLS_DIR / f"{nome_agente}.md"
    if ficheiro_skill.exists():
        with open(ficheiro_skill, "r", encoding="utf-8") as f:
            return f.read()
    return "Aja de acordo com a sua especialidade técnica e os padrões da fábrica."

def criar_instrucao_com_skill(nome_agente: str, instrucao_base: str) -> str:
    """Obriga o agente a consultar e assimilar rigorosamente a sua skill antes de qualquer acção."""
    conteudo_skill = carregar_skill(nome_agente)
    
    instrucao_rigorosa = f"""
[DIRETIVA OBRIGATÓRIA DE EXECUÇÃO]
Antes de iniciar qualquer raciocínio, planeamento ou resposta, DEVE consultar e assimilar rigorosamente a sua skill oficial abaixo. As diretrizes aqui descritas são leis absolutas para o seu comportamento e entregas.

--- SKILL OFICIAL DO AGENTE ---
{conteudo_skill}
-------------------------------

[TAREFAS E CONTEXTO ATUAL]
{instrucao_base}
"""
    return instrucao_rigorosa

if __name__ == "__main__":
    projeto = os.getenv("PROJETO_IDEIA", "Projeto Padrão da Fábrica")
    print(f"[Fábrica de IA Autónoma] Orquestrador carregado com sucesso!")
    print(f"[Projeto Alvo]: {projeto}")
    print("[Estado]: Todos os agentes estão configurados para consultar obrigatoriamente as suas skills locais.")

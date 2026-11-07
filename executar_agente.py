import os
from google import genai
from orquestrador import criar_instrucao_com_skill
from pesquisa_web import pesquisar_web
from ferramentas_sistema import executar_comando_sistema
from dotenv import load_dotenv

load_dotenv()

# Inicializar o cliente oficial do Google GenAI
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def executar_agente_autonomo(nome_agente: str, tarefa: str, query_pesquisa: str = None, comando_sistema: str = None):
    print(f"\n[Fábrica Autónoma] A despertar o agente especializado: {nome_agente.upper()}...")
    
    contexto_extra = ""
    
    # 1. Investigação na Web (se solicitada)
    if query_pesquisa:
        print(f"[Fábrica] A investigar na web em tempo real: '{query_pesquisa}'...")
        contexto_extra += f"\n\n[DADOS DE INVESTIGAÇÃO WEB RECOLHIDOS]:\n{pesquisar_web(query_pesquisa)}\n"
        
    # 2. Interação Real com o Sistema / Infraestrutura (CLI: Git, GitHub, Vercel, Python)
    if comando_sistema:
        print(f"[Fábrica] A executar comando no sistema operacional/CLI: '{comando_sistema}'...")
        saida_sistema = executar_comando_sistema(comando_sistema)
        contexto_extra += f"\n\n[ESTADO ATUAL DO SISTEMA / SAÍDA DO COMANDO]:\n{saida_sistema}\n"
    
    tarefa_completa = tarefa + contexto_extra
    
    # 3. Cruzar diretrizes obrigatórias da skill com a tarefa operacional
    prompt_completo = criar_instrucao_com_skill(nome_agente, tarefa_completa)
    
    print(f"[Fábrica] A processar tokens com o Gemini (modelo gemini-3.8-flash)...")
    resposta = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt_completo,
    )
    
    print(f"\n=== RELATÓRIO DO AGENTE ({nome_agente.upper()}) ===")
    print(resposta.text)
    print("=" * 70)

if __name__ == "__main__":
    # Exemplo de teste prático da orquestração unificada
    tarefa_padrao = (
        "Analisa o estado atual da infraestrutura, verifica as diretrizes do teu ecossistema "
        "e propõe o script de automação em Python para criar um repositório e preparar o deploy na Vercel."
    )
    
    # Despertar o agente DevOps com verificação simultânea do git e ferramentas CLI
    executar_agente_autonomo(
        nome_agente="devops", 
        tarefa=tarefa_padrao, 
        comando_sistema="git status && gh --version && vercel --version"
    )

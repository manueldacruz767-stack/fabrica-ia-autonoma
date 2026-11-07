import os
from google import genai
from orquestrador import criar_instrucao_com_skill
from pesquisa_web import pesquisar_web
from ferramentas_sistema import executar_comando_sistema
from dotenv import load_dotenv

load_dotenv()

# Inicializar o cliente com a nova SDK
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def executar_agente_completo(nome_agente: str, tarefa: str, query_pesquisa: str = None, comando_sistema: str = None):
    print(f"\n[Fábrica] A despertar o agente: {nome_agente.upper()}...")
    
    contexto_extra = ""
    
    if query_pesquisa:
        print(f"[Fábrica] A investigar na web: '{query_pesquisa}'...")
        contexto_extra += f"\n\n[DADOS DE INVESTIGAÇÃO WEB]:\n{pesquisar_web(query_pesquisa)}\n"
        
    if comando_sistema:
        print(f"[Fábrica] A executar verificação no sistema: '{comando_sistema}'...")
        saida_sistema = executar_comando_sistema(comando_sistema)
        contexto_extra += f"\n\n[ESTADO ATUAL DO SISTEMA/APP]:\n{saida_sistema}\n"
    
    tarefa_completa = tarefa + contexto_extra
    
    # Gerar instrução com skill obrigatória
    prompt_completo = criar_instrucao_com_skill(nome_agente, tarefa_completa)
    
    print(f"[Fábrica] A gerar solução com o Gemini (modelo gemini-1.5-flash)...")
    resposta = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt_completo,
    )
    
    print(f"\n=== RESPOSTA DO AGENTE ({nome_agente.upper()}) ===")
    print(resposta.text)
    print("=" * 60)

if __name__ == "__main__":
    tarefa = "Verificar o estado do repositório local e garantir que a estrutura está pronta."
    executar_agente_completo("devops", tarefa, comando_sistema="git status")

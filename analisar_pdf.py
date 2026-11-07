import sys
import os
from leitor_pdf import extrair_texto_pdf
from executar_agente import executar_tarefa_agente

def main():
    if len(sys.argv) < 2:
        print("Erro: Indica o caminho do ficheiro PDF.")
        print("Uso: python3 analisar_pdf.py caminho/para/documentacao.pdf")
        sys.exit(1)
        
    caminho_pdf = sys.argv[1]
    print(f"[Fábrica] A extrair texto do PDF: {caminho_pdf}...")
    
    conteudo_pdf = extrair_texto_pdf(caminho_pdf)
    if conteudo_pdf.startswith("Erro:"):
        print(conteudo_pdf)
        sys.exit(1)
        
    # Definir a tarefa para o agente programador ou arquiteto
    tarefa = f"Analisa a seguinte documentação técnica extraída de um PDF e cria o plano de implementação detalhado:\n\n{conteudo_pdf}"
    
    # Executar o agente programador (ou arquiteto)
    executar_tarefa_agente("programador", tarefa)

if __name__ == "__main__":
    main()

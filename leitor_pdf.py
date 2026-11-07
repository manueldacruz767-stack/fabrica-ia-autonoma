from pathlib import Path
from pypdf import PdfReader

def extrair_texto_pdf(caminho_pdf: str) -> str:
    """Lê um ficheiro PDF e devolve todo o seu texto extraído."""
    ficheiro = Path(caminho_pdf)
    if not ficheiro.exists():
        return f"Erro: O ficheiro PDF '{caminho_pdf}' não foi encontrado."
    
    leitor = PdfReader(ficheiro)
    texto_completo = ""
    
    for i, pagina in enumerate(leitor.pages):
        texto_pagina = pagina.extract_text()
        if texto_pagina:
            texto_completo += f"\n--- Página {i+1} ---\n" + texto_pagina
            
    return texto_completo

if __name__ == "__main__":
    # Teste rápido se executado diretamente
    print("Módulo de leitura de PDF carregado com sucesso.")

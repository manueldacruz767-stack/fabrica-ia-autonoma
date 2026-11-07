import os
import requests
from dotenv import load_dotenv

load_dotenv()

def pesquisar_web(query: str, num_resultados: int = 5) -> str:
    """Faz uma pesquisa na web usando a API do Serper e devolve os resultados formatados."""
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return "Erro: SERPER_API_KEY não encontrada no ficheiro .env."
    
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "num": num_resultados
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            dados = response.json()
            resultados_formatados = ""
            for item in dados.get("organic", []):
                titulo = item.get("title", "")
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                resultados_formatados += f"- **{titulo}**\n  Link: {link}\n  Resumo: {snippet}\n\n"
            return resultados_formatados if resultados_formatados else "Nenhum resultado encontrado."
        else:
            return f"Erro na API de pesquisa: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Erro de ligação à pesquisa: {str(e)}"

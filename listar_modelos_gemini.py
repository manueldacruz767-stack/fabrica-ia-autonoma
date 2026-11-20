import os
from dotenv import load_dotenv

load_dotenv()

from google import genai

chave = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not chave:
    raise SystemExit("Erro: define GEMINI_API_KEY (ou GOOGLE_API_KEY) no .env antes de correr isto.")

client = genai.Client(api_key=chave)

print("Modelos disponíveis que suportam generateContent:\n")
for modelo in client.models.list():
    metodos = getattr(modelo, "supported_actions", None) or getattr(modelo, "supported_generation_methods", [])
    if not metodos or "generateContent" in metodos:
        print(f"- {modelo.name}")

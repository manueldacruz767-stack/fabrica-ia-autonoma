import os
from crewai import Agent, Crew, Task
from langchain_google_genai import ChatGoogleGenerativeAI

os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "")
llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2)

print("🏢 Inicializando a equipa de agentes na nuvem...")

arquiteto = Agent(
    role="Arquiteto de Software Chefe",
    goal="Planear a arquitetura, stack tecnológica, escopo e contrato de API.",
    backstory="Líder técnico rigoroso.",
    verbose=True, llm=llm
)

backend_dev = Agent(
    role="Desenvolvedor Backend Sênior",
    goal="Escrever o código fonte funcional do servidor com base no plano do Arquiteto.",
    backstory="Especialista em APIs REST e bases de dados.",
    verbose=True, llm=llm
)

frontend_dev = Agent(
    role="Desenvolvedor Frontend Sênior",
    goal="Construir a interface do usuário conectando com os endpoints do backend.",
    backstory="Especialista em interfaces modernas e responsivas.",
    verbose=True, llm=llm
)

qa_tester = Agent(
    role="Engenheiro de Testes e Qualidade (QA)",
    goal="Rever o código gerado, apontar falhas ou bugs e garantir que está pronto.",
    backstory="Auditor técnico implacável com erros.",
    verbose=True, llm=llm
)

ideia_projeto = os.environ.get("PROJETO_IDEIA", "Um site de portfólio simples.")
print(f"💡 Projeto alvo: {ideia_projeto}")

t1 = Task(description=f"Faça o planeamento e contrato de API para: {ideia_projeto}", expected_output="Documento de arquitetura em Markdown", agent=arquiteto)
t2 = Task(description="Com base no plano, escreva o código do Backend.", expected_output="Código fonte do backend", agent=backend_dev)
t3 = Task(description="Com base no plano, escreva o código do Frontend.", expected_output="Código fonte do frontend", agent=frontend_dev)
t4 = Task(description="Faça a revisão de qualidade de todo o código gerado.", expected_output="Relatório de QA e código validado", agent=qa_tester)

fabrica = Crew(
    agents=[arquiteto, backend_dev, frontend_dev, qa_tester],
    tasks=[t1, t2, t3, t4],
    verbose=True
)

resultado = fabrica.kickoff()

with open("projeto_final.md", "w", encoding="utf-8") as f:
    f.write(str(resultado))

print("✅ Trabalho concluído pela equipa com sucesso!")

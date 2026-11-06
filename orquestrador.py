import os
from crewai import Agent, Task, Crew, Process

# Usando o modelo indicado pela mensagem de erro da API
llm_gemini = "gemini/gemini-3.8-flash"

ideia = os.getenv("PROJETO_IDEIA", "Sistema padrão de tarefas")

print("🏢 Inicializando a equipa de agentes na nuvem...")

arquiteto = Agent(
    role="Arquiteto de Software",
    goal="Desenhar a estrutura e listar os ficheiros necessários para a aplicação",
    backstory="Especialista em arquitetura de software e engenharia de requisitos.",
    llm=llm_gemini,
    verbose=True
)

tarefa_design = Task(
    description=f"Crie o plano de ficheiros e arquitetura para a ideia: {ideia}",
    expected_output="Uma lista clara de ficheiros e estrutura do projeto.",
    agent=arquiteto
)

equipa = Crew(
    agents=[arquiteto],
    tasks=[tarefa_design],
    process=Process.sequential
)

resultado = equipa.kickoff()
print("✅ Execução concluída com sucesso:")
print(resultado)

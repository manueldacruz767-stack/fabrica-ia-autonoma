import os
from crewai import Agent, Crew, Process, Task
from crewai.llm import LLM

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

llm = LLM(
    model=f"gemini/{os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')}",
    temperature=0.7,
    api_key=api_key,
)

# 1. Definir os Agentes da Fábrica de Software
arquiteto = Agent(
    role="Arquiteto de Software Chefe",
    goal="Desenhar a arquitetura técnica, stack tecnológica e estrutura de ficheiros para a ideia de projeto fornecida.",
    backstory="Um arquiteto experiente com visão de produto e foco em soluções escaláveis e limpas.",
    verbose=True,
    llm=llm
)

dev_backend = Agent(
    role="Desenvolvedor Backend Sénior",
    goal="Implementar a lógica de negócio, APIs e componentes de servidor necessários.",
    backstory="Especialista em robustez, segurança de dados e arquiteturas eficientes em backend.",
    verbose=True,
    llm=llm
)

dev_frontend = Agent(
    role="Desenvolvedor Frontend Sénior",
    goal="Criar interfaces de utilizador intuitivas, responsivas e visualmente apelativas.",
    backstory="Apaixonado por UX/UI, design moderno com temas escuros e componentes limpos.",
    verbose=True,
    llm=llm
)

qa = Agent(
    role="Engenheiro de Qualidade (QA)",
    goal="Rever o código e a documentação gerada, garantindo que cumprem os requisitos e estão livres de erros.",
    backstory="Meticuloso, focado em testes, boas práticas e na integridade final do projeto.",
    verbose=True,
    llm=llm
)

# Função principal para executar a Crew
def executar_fabrica(ideia_projeto: str):
    # 2. Definir as Tarefas
    tarefa_arquitetura = Task(
        description=f"Analisa a ideia de projeto: '{ideia_projeto}'. Cria a arquitetura completa e a estrutura de pastas.",
        expected_output="Um documento detalhado de arquitetura e planeamento técnico.",
        agent=arquiteto
    )

    tarefa_backend = Task(
        description="Com base na arquitetura definida, desenha e estrutura o código do backend.",
        expected_output="Esboço do código backend e endpoints principais.",
        agent=dev_backend
    )

    tarefa_frontend = Task(
        description="Com base na arquitetura, desenha a interface do utilizador (frontend) com foco em boa experiência.",
        expected_output="Estrutura de componentes e telas do frontend.",
        agent=dev_frontend
    )

    tarefa_revisao = Task(
        description="Revisa todo o trabalho produzido pelos agentes anteriores, consolida e gera o ficheiro final 'projeto_final.md'.",
        expected_output="Ficheiro markdown final consolidado (`projeto_final.md`) contendo todo o projeto estruturado.",
        agent=qa,
        output_file="projeto_final.md"
    )

    # 3. Criar e Executar a Crew
    fabrica_crew = Crew(
        agents=[arquiteto, dev_backend, dev_frontend, qa],
        tasks=[tarefa_arquitetura, tarefa_backend, tarefa_frontend, tarefa_revisao],
        process=Process.sequential,
        verbose=True
    )

    resultado = fabrica_crew.kickoff()
    return resultado

if __name__ == "__main__":
    ideia = "Plataforma de gestão de tarefas colaborativa em tempo real com autenticação."
    print(f"🚀 A iniciar a Fábrica de IA para a ideia: {ideia}")
    executar_fabrica(ideia)
    print("✅ Processo concluído! Verifica o ficheiro 'projeto_final.md'.")
        

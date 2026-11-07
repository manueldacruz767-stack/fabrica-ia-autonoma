import os
import subprocess
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from crewai_tools import SerperDevTool

# -------------------------------------------------------------------------
# 0. CONFIGURAÇÃO DE FERRAMENTAS E SEGURANÇA
# -------------------------------------------------------------------------
# Certifica-te de ter o Serper configurado: export SERPER_API_KEY="tua-chave"
search_tool = SerperDevTool()

@tool("Executar Comandos de Git e Infraestrutura")
def ferramenta_devops_git(comando: str) -> str:
    """
    Permite ao agente DevOps executar comandos seguros no terminal do Fedora,
    como inicializar o git, criar repositórios via GitHub CLI (gh) sob 'manueldacruz767-stack' e fazer push.
    Comandos permitidos: git, gh, docker, mkdir, echo
    """
    comandos_permitidos = ["git", "gh", "docker", "mkdir", "echo"]
    primeira_palavra = comando.strip().split(" ")[0]
    
    if primeira_palavra not in comandos_permitidos:
        return f"Erro de Segurança: O comando '{primeira_palavra}' não é permitido por razões de segurança."

    try:
        resultado = subprocess.run(
            comando, shell=True, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return f"Comando executado com sucesso:\n{resultado.stdout}"
    except subprocess.CalledProcessError as e:
        return f"Erro ao executar o comando:\n{e.stderr}"

# Função para carregar dinamicamente as skills de cada agente a partir da pasta 'skills/'
def carregar_skill(nome_ficheiro):
    caminho = os.path.join("skills", nome_ficheiro)
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
            if conteudo:
                return conteudo
    return "Atua estritamente como especialista na tua área profissional."

llm_gemini = "gemini/gemini-3.8-flash"
ideia_projeto = os.getenv("PROJETO_IDEIA", "Plataforma de Gestão Inteligente Segura")

print(f"🏢 A inicializar a Fábrica de IA Autónoma para o projeto: '{ideia_projeto}'...")

# -------------------------------------------------------------------------
# 1. DEFINIÇÃO DA EQUIPA DE 10 AGENTES COM AS SUAS SKILLS CARREGADAS
# -------------------------------------------------------------------------

scrum_master = Agent(
    role="Scrum Master & Agile Coach",
    goal="Definir marcos de entrega, roadmap técnico e gerir o fluxo ágil.",
    backstory=carregar_skill("scrum_master.md"),
    llm=llm_gemini,
    verbose=True
)

arquiteto_agent = Agent(
    role="Arquiteto de Software Sénior",
    goal="Desenhar a arquitetura macro do sistema e padrões de projeto.",
    backstory=carregar_skill("arquiteto.md"),
    tools=[search_tool],
    llm=llm_gemini,
    verbose=True
)

ux_ui_agent = Agent(
    role="Designer de UX/UI",
    goal="Mapear a jornada do utilizador, fluxos de ecrã e guias visuais.",
    backstory=carregar_skill("ux_ui.md"),
    llm=llm_gemini,
    verbose=True
)

dados_cache_agent = Agent(
    role="Arquiteto de Dados e Cache",
    goal="Modelar a base de dados (PostgreSQL/Supabase) e estratégia de cache com Redis.",
    backstory=carregar_skill("dados_cache.md"),
    llm=llm_gemini,
    verbose=True
)

seguranca_agent = Agent(
    role="Engenheiro de Cibersegurança & AppSec",
    goal="Garantir autenticação (JWT/OAuth2), encriptação e regras de blindagem defensiva.",
    backstory=carregar_skill("seguranca.md"),
    llm=llm_gemini,
    verbose=True
)

red_team_agent = Agent(
    role="Engenheiro Red Team & Penetration Tester",
    goal="Simular ataques de intrusão, detetar falhas lógicas e CVEs.",
    backstory=carregar_skill("red_team.md"),
    tools=[search_tool],
    llm=llm_gemini,
    verbose=True
)

backend_agent = Agent(
    role="Engenheiro Backend Sénior",
    goal="Desenvolver a lógica de servidor, APIs REST/GraphQL e regras de negócio.",
    backstory=carregar_skill("backend.md"),
    tools=[search_tool],
    llm=llm_gemini,
    verbose=True
)

frontend_agent = Agent(
    role="Engenheiro Frontend Sénior",
    goal="Estruturar a arquitetura de cliente, componentes e consumo de APIs.",
    backstory=carregar_skill("frontend.md"),
    llm=llm_gemini,
    verbose=True
)

qa_agent = Agent(
    role="Engenheiro de Qualidade e Testes (QA)",
    goal="Criar planos de testes unitários, integração e cenários E2E.",
    backstory=carregar_skill("qa.md"),
    llm=llm_gemini,
    verbose=True
)

devops_agent = Agent(
    role="Engenheiro DevOps e Automação",
    goal="Criar repositório Git, estruturar Dockerfile, pipelines CI/CD e criar o repositório no GitHub para 'manueldacruz767-stack'.",
    backstory=carregar_skill("devops.md"),
    tools=[search_tool, ferramenta_devops_git],
    llm=llm_gemini,
    verbose=True
)

# -------------------------------------------------------------------------
# 2. DEFINIÇÃO DAS TAREFAS EM CADEIA SEQUENCIAL
# -------------------------------------------------------------------------

t_scrum = Task(
    description=f"Analisa a ideia '{ideia_projeto}' e define o planeamento e o roadmap ágil.",
    expected_output="Roadmap ágil e marcos de entrega do projeto.",
    agent=scrum_master
)

t_arq = Task(
    description=f"Desenha a arquitetura geral do sistema e as tecnologias recomendadas para '{ideia_projeto}'.",
    expected_output="Diagrama de arquitetura macro e stack técnica.",
    agent=arquiteto_agent
)

t_ux = Task(
    description=f"Define a experiência visual (UX/UI), fluxos de navegação e componentes chave para '{ideia_projeto}'.",
    expected_output="Especificação de interface e wireframes lógicos.",
    agent=ux_ui_agent
)

t_dados = Task(
    description=f"Define a base de dados (PostgreSQL/Supabase/NoSQL) e a estratégia de cache (Redis) para '{ideia_projeto}'.",
    expected_output="Modelagem de dados, tabelas e arquitetura de cache.",
    agent=dados_cache_agent
)

t_backend = Task(
    description=f"Especifica a implementação de backend, endpoints de API REST e regras de negócio.",
    expected_output="Estrutura de código do servidor e serviços.",
    agent=backend_agent
)

t_frontend = Task(
    description=f"Especifica a implementação de frontend, componentes de cliente e consumo de APIs.",
    expected_output="Estrutura de código do cliente e interfaces.",
    agent=frontend_agent
)

# CICLO DE SEGURANÇA E INTRUSÃO
t_seguranca_inicial = Task(
    description=f"Define as diretrizes iniciais de autenticação (JWT/OAuth2) e barreiras de segurança para '{ideia_projeto}'.",
    expected_output="Plano de segurança preliminar.",
    agent=seguranca_agent
)

t_red_team = Task(
    description=(
        "Atua como Hacker Ético / Red Team. Analisa todo o sistema desenhado até agora "
        f"para '{ideia_projeto}', pesquisa vectores de ataque e simula uma auditoria de intrusão "
        "para detetar falhas e vulnerabilidades."
    ),
    expected_output="Relatório de Penetration Testing (Pentest) com as falhas encontradas.",
    agent=red_team_agent
)

t_seguranca_correcao = Task(
    description=(
        "Examina o relatório de intrusão do Red Team. Corrige todas as falhas de segurança "
        "apontadas, blinda os endpoints e atualiza o plano defensivo do software."
    ),
    expected_output="Relatório de remediação e blindagem de segurança aprovado.",
    agent=seguranca_agent
)

# VALIDAÇÃO E ENTREGA
t_qa = Task(
    description=(
        "Com base no sistema blindado, desenvolve o plano completo de testes unitários, "
        "integração e cenários E2E para assegurar a qualidade de funcionamento."
    ),
    expected_output="Plano de testes detalhado e critérios de aceitação (QA).",
    agent=qa_agent
)

t_devops = Task(
    description=(
        f"Prepara a infraestrutura para '{ideia_projeto}'. Utiliza a ferramenta de terminal "
        "para inicializar o Git local, criar o repositório público no GitHub sob a conta 'manueldacruz767-stack' "
        "através da GitHub CLI (`gh repo create ... --public --push`) e enviar todo o código gerado."
    ),
    expected_output="Repositório criado no GitHub e código enviado com sucesso via Git.",
    agent=devops_agent
)

# -------------------------------------------------------------------------
# 3. CRIAÇÃO E EXECUÇÃO DA CREW COMPLETA
# -------------------------------------------------------------------------

fabrica_crew = Crew(
    agents=[
        scrum_master, arquiteto_agent, ux_ui_agent, dados_cache_agent,
        backend_agent, frontend_agent, seguranca_agent, red_team_agent,
        seguranca_agent, qa_agent, devops_agent
    ],
    tasks=[
        t_scrum, t_arq, t_ux, t_dados, t_backend, t_frontend,
        t_seguranca_inicial, t_red_team, t_seguranca_correcao, t_qa, t_devops
    ],
    process=Process.sequential,
    verbose=True
)

resultado = fabrica_crew.kickoff()

# Guardar o resultado unificado num ficheiro Markdown profissional
with open("projeto_final_completo.md", "w", encoding="utf-8") as f:
    f.write(str(resultado))

print("🎉 Processo concluído com sucesso! O projeto completo foi gerado em 'projeto_final_completo.md'.")import os
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

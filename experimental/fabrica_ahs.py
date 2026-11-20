import os
import re
import shlex
import subprocess
import unicodedata
import psycopg2
from pydantic import BaseModel
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from crewai_tools import SerperDevTool
from dotenv import load_dotenv

load_dotenv()

if os.getenv("FABRICA_MODO_COMPLETO", "").strip().lower() not in {"1", "true", "sim", "yes", "on"}:
    raise SystemExit("Fabrica completa desativada. Define FABRICA_MODO_COMPLETO=1 para a executar.")

# ==========================================================================
# CONFIGURAÇÃO DO PROJETO (muda só isto para usar a fábrica noutro projeto)
# ==========================================================================
ideia_projeto = os.getenv("PROJETO_IDEIA", "Software de Gestão Alimentar - Versão 0.1")
NOME_ORGANIZACAO_GITHUB = os.getenv("NOME_ORGANIZACAO_GITHUB", "manueldacruz767-stack")

# Opcional: regras de negócio, conformidade legal, identidade visual — só
# entra na instrução dos agentes se preencheres. Deixa em branco para
# projetos sem requisitos especiais (a maioria).
CONTEXTO_ADICIONAL = os.getenv("CONTEXTO_ADICIONAL", "").strip()

REGRA_ANTI_OSCILACAO = f"""
[DIRETRIZ SUPREMA DE EXECUÇÃO - OBRIGATÓRIA PARA TODOS OS AGENTES]
1. Foco Absoluto no Projeto: Desenvolvimento estrito de '{ideia_projeto}', e de mais
nada. Não introduzas funcionalidades, domínios ou tecnologias que o pedido não pediu.
2. Uso Cirúrgico da Internet: SerperDevTool deve ser usada EXCLUSIVAMENTE para
consultar documentação técnica de suporte (ex: sintaxe de uma framework).
3. Proibição de Desvio: É ESTRITAMENTE PROIBIDO alterar regras de negócio ou
arquitetura com base em tutoriais gerais da internet. O plano interno é lei.
{f"4. Contexto específico deste projeto (segue à risca): {CONTEXTO_ADICIONAL}" if CONTEXTO_ADICIONAL else ""}
"""

search_tool = SerperDevTool()


# ==========================================================================
# UTILITÁRIOS DE SEGURANÇA
# ==========================================================================
OPERADORES_PERIGOSOS = [";", "&&", "||", "|", "`", "$(", ">", "<"]


def _tem_operador_perigoso(comando: str) -> bool:
    return any(op in comando for op in OPERADORES_PERIGOSOS)


def slugify(texto: str, max_len: int = 40) -> str:
    """Converte texto livre (vindo de um LLM) num nome seguro para pastas,
    repositórios e pacotes: minúsculas, hífens, sem acentos nem caracteres
    especiais. É SEMPRE isto, nunca o texto do LLM em bruto, que chega a
    um comando de shell ou a um caminho de ficheiro."""
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-zA-Z0-9\s-]", "", texto).strip().lower()
    texto = re.sub(r"[\s_-]+", "-", texto)
    return texto[:max_len].strip("-") or "projeto-sem-nome"


def _run_seguro(partes, cwd=None, timeout=120) -> str:
    try:
        resultado = subprocess.run(
            partes, shell=False, check=True, text=True, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
        return f"Sucesso:\n{resultado.stdout}"
    except subprocess.CalledProcessError as e:
        return f"Erro ao executar o comando:\n{e.stderr}"
    except subprocess.TimeoutExpired:
        return f"Erro: o comando excedeu o tempo limite ({timeout}s)."


# ==========================================================================
# FASE 1 — DECISÃO DE NOME E STACK (sem ferramentas de execução, só raciocínio)
# ==========================================================================
class DecisaoStack(BaseModel):
    nome_projeto_sugerido: str
    linguagem_backend: str
    framework_backend: str
    framework_frontend: str
    base_de_dados: str
    justificacao: str


llm_gemini = LLM(model=f"gemini/{os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite')}", temperature=0.7)


def carregar_skill(nome_ficheiro: str) -> str:
    caminho = os.path.join("skills", nome_ficheiro)
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
            if conteudo:
                return f"{conteudo}\n\n{REGRA_ANTI_OSCILACAO}"
    return f"Atua estritamente como especialista.\n\n{REGRA_ANTI_OSCILACAO}"


scrum_master = Agent(
    role="Scrum Master & Agile Coach",
    goal="Definir o roadmap ágil, Sprints e marcos de entrega do projeto.",
    backstory=carregar_skill("scrum_master.md"),
    llm=llm_gemini, verbose=True,
)

arquiteto_agent = Agent(
    role="Arquiteto de Software Sénior",
    goal=(
        "Escolher um nome curto e descritivo para o projeto e a stack tecnológica "
        "mais adequada ao tipo de produto, escala esperada e equipa (preferir a "
        "solução mais simples que cumpre os requisitos). Desenhar depois a macro "
        "arquitetura do sistema."
    ),
    backstory=carregar_skill("arquiteto.md"),
    tools=[search_tool],
    llm=llm_gemini, verbose=True,
)

t_scrum = Task(
    description=f"Elabora o plano e o backlog ágil para a Versão 0.1 de '{ideia_projeto}'.",
    expected_output="Backlog detalhado em Markdown.",
    agent=scrum_master,
)

t_stack = Task(
    description=(
        f"Com base no projeto '{ideia_projeto}', decide: (1) um nome curto e "
        "descritivo para o projeto (2 a 4 palavras, em português, sem o ano nem "
        "versão); (2) a linguagem e framework de backend; (3) o framework de "
        "frontend; (4) a base de dados. Prefere tecnologias amplamente suportadas "
        "e proporcionais ao tamanho do projeto — não escolhas microserviços, "
        "Kubernetes ou NoSQL sem uma razão concreta para este projeto. Justifica "
        "a escolha em 3 a 5 linhas."
    ),
    expected_output="Objeto estruturado com nome do projeto, stack escolhida e justificação.",
    output_pydantic=DecisaoStack,
    agent=arquiteto_agent,
)

print(f"[FASE 1] a decidir nome e stack para: '{ideia_projeto}'...")
crew_fase1 = Crew(
    agents=[scrum_master, arquiteto_agent],
    tasks=[t_scrum, t_stack],
    process=Process.sequential,
    verbose=True,
)
resultado_fase1 = crew_fase1.kickoff()

decisao = resultado_fase1.tasks_output[-1].pydantic
if decisao is None:
    raise RuntimeError(
        "O Arquiteto não devolveu a decisao de stack em formato estruturado. "
        "Corre novamente - pode ser uma falha pontual do modelo."
    )

slug_projeto = slugify(decisao.nome_projeto_sugerido or ideia_projeto)
projeto_dir = os.path.join("projetos", slug_projeto)
os.makedirs(projeto_dir, exist_ok=True)

resumo_stack = (
    f"Projeto: '{decisao.nome_projeto_sugerido}' (pasta local: {projeto_dir}). "
    f"Stack decidida - backend: {decisao.linguagem_backend} / {decisao.framework_backend}; "
    f"frontend: {decisao.framework_frontend}; base de dados: {decisao.base_de_dados}. "
    f"Justificacao do Arquiteto: {decisao.justificacao}"
)
print(f"[FASE 1 concluída]\n{resumo_stack}")


# ==========================================================================
# FERRAMENTAS DA FASE 2 (já configuradas com a pasta real do projeto)
# ==========================================================================

def construir_ferramenta_criar_ficheiro(projeto_dir: str):
    @tool("Criar ou atualizar um ficheiro dentro do projeto")
    def ferramenta_criar_ficheiro(caminho_relativo: str, conteudo: str) -> str:
        """Cria/atualiza um ficheiro de código dentro da pasta do projeto atual.
        Recusa caminhos absolutos ou com '..' (não sai da pasta do projeto)."""
        partes_caminho = caminho_relativo.replace("\\", "/").split("/")
        if os.path.isabs(caminho_relativo) or ".." in partes_caminho:
            return "Erro de Segurança: caminho inválido (absoluto ou com '..')."
        caminho_final = os.path.join(projeto_dir, caminho_relativo)
        os.makedirs(os.path.dirname(caminho_final) or ".", exist_ok=True)
        with open(caminho_final, "w", encoding="utf-8") as f:
            f.write(conteudo)
        return f"Ficheiro criado/atualizado: {caminho_final}"
    return ferramenta_criar_ficheiro


def construir_ferramenta_gestor_pacotes(projeto_dir: str):
    @tool("Gestor de pacotes do projeto (npm, pip, composer, mvn, gradle, yarn, pnpm)")
    def ferramenta_gestor_pacotes(comando: str) -> str:
        """Executa um comando de gestor de pacotes (ex.: 'npm install express',
        'pip install fastapi', 'composer require laravel/laravel') dentro da
        pasta do projeto. O gestor a usar depende da stack decidida pelo
        Arquiteto - usa o que corresponder à linguagem/framework escolhidos."""
        gestores_permitidos = {"npm", "pip", "pip3", "composer", "mvn", "gradle", "yarn", "pnpm"}
        if _tem_operador_perigoso(comando):
            return "Erro de Segurança: operadores de encadeamento não são permitidos."
        try:
            partes = shlex.split(comando)
        except ValueError as e:
            return f"Erro de Segurança: comando malformado ({e})."
        if not partes or partes[0] not in gestores_permitidos:
            return f"Erro de Segurança: gestor de pacotes '{partes[0] if partes else ''}' não é permitido."
        return _run_seguro(partes, cwd=projeto_dir, timeout=180)
    return ferramenta_gestor_pacotes


def construir_ferramenta_devops_git(projeto_dir: str):
    @tool("Executar comandos de Git, Vercel e infraestrutura dentro do projeto")
    def ferramenta_devops_git(comando: str) -> str:
        """Executa comandos git, gh, vercel ou docker dentro da pasta do projeto.
        Um comando por chamada; sem ';', '&&', '|' - para ações encadeadas,
        chama a ferramenta várias vezes."""
        comandos_permitidos = {"git", "gh", "vercel", "docker", "mkdir", "ls"}
        if _tem_operador_perigoso(comando):
            return "Erro de Segurança: operadores de encadeamento não são permitidos."
        try:
            partes = shlex.split(comando)
        except ValueError as e:
            return f"Erro de Segurança: comando malformado ({e})."
        if not partes or partes[0] not in comandos_permitidos:
            return f"Erro de Segurança: o comando '{partes[0] if partes else ''}' não é permitido."
        return _run_seguro(partes, cwd=projeto_dir, timeout=120)
    return ferramenta_devops_git


@tool("Criar repositório no GitHub (nome do projeto sanitizado automaticamente)")
def ferramenta_criar_repositorio_github(nome_proposto: str, privado: bool = False) -> str:
    """Cria um repositório no GitHub sob a organização configurada. O nome
    proposto é sempre convertido para um formato seguro (slug) antes de ser
    usado no comando - nunca o texto em bruto do agente."""
    slug = slugify(nome_proposto)
    visibilidade = "--private" if privado else "--public"
    comando = ["gh", "repo", "create", f"{NOME_ORGANIZACAO_GITHUB}/{slug}", visibilidade, "--confirm"]
    resultado = _run_seguro(comando, timeout=60)
    return f"{resultado}\n(Nome final usado, já sanitizado: {slug})"


ferramenta_criar_ficheiro = construir_ferramenta_criar_ficheiro(projeto_dir)
ferramenta_gestor_pacotes = construir_ferramenta_gestor_pacotes(projeto_dir)
ferramenta_devops_git = construir_ferramenta_devops_git(projeto_dir)

# Base de dados: leitura e escrita separadas, escrita bloqueia operações
# destrutivas (DROP/TRUNCATE e DELETE sem WHERE).
PADRAO_DESTRUTIVO = re.compile(r"\b(drop|truncate)\b", re.IGNORECASE)
PADRAO_DELETE_SEM_WHERE = re.compile(r"\bdelete\s+from\s+\w+\s*(;|$)", re.IGNORECASE)


@tool("Consultar dados na Base de Dados Real (apenas leitura)")
def ferramenta_db_leitura(query_sql: str) -> str:
    """Executa apenas instruções SELECT na base de dados real PostgreSQL/Supabase."""
    query = query_sql.strip()
    if not query.lower().startswith("select"):
        return "Erro de Segurança: esta ferramenta só permite SELECT."
    db_url = os.getenv("DATABASE_URL_READONLY") or os.getenv("DATABASE_URL")
    if not db_url:
        return "Erro: DATABASE_URL_READONLY/DATABASE_URL não configurada."
    try:
        with psycopg2.connect(db_url) as conexao, conexao.cursor() as cursor:
            cursor.execute(query)
            resultados = cursor.fetchall()
        return f"Sucesso! Dados obtidos:\n{resultados}"
    except Exception as e:
        return f"Erro ao consultar a base de dados: {str(e)}"


@tool("Aplicar migração ou alteração na Base de Dados Real (escrita)")
def ferramenta_db_escrita(query_sql: str) -> str:
    """Executa CREATE/ALTER/INSERT/UPDATE. Bloqueia DROP/TRUNCATE e DELETE sem WHERE."""
    query = query_sql.strip()
    if PADRAO_DESTRUTIVO.search(query):
        return "Erro de Segurança: DROP/TRUNCATE bloqueados; executar manualmente se for mesmo necessário."
    if PADRAO_DELETE_SEM_WHERE.search(query):
        return "Erro de Segurança: DELETE sem WHERE é bloqueado."
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return "Erro: DATABASE_URL não configurada."
    try:
        with psycopg2.connect(db_url) as conexao, conexao.cursor() as cursor:
            cursor.execute(query)
            conexao.commit()
        return "Comando SQL executado e aplicado com sucesso!"
    except Exception as e:
        return f"Erro ao interagir com a base de dados: {str(e)}"


# Red Team: alvo sempre fixado pelo código, nunca escolhido pelo agente.
ALVO_AUDITORIA = os.getenv("ALVO_AUDITORIA", "http://localhost:8080")
HOST_AUDITORIA = os.getenv("HOST_AUDITORIA", "localhost")


@tool("Ferramentas de Auditoria de Segurança (Red Team) sobre o sistema próprio")
def ferramenta_ataque_red_team(subcomando: str) -> str:
    """Executa nmap/sqlmap/curl SOMENTE contra o alvo fixado em ALVO_AUDITORIA/
    HOST_AUDITORIA. O agente escolhe o tipo de verificação, nunca o alvo."""
    ferramentas_permitidas = {"nmap", "sqlmap", "curl", "python3"}
    if _tem_operador_perigoso(subcomando):
        return "Erro de Segurança: operadores de encadeamento não são permitidos."
    try:
        partes = shlex.split(subcomando)
    except ValueError as e:
        return f"Erro de Segurança: comando malformado ({e})."
    if not partes or partes[0] not in ferramentas_permitidas:
        return f"Erro: a ferramenta '{partes[0] if partes else ''}' não é permitida."
    if partes[0] == "nmap":
        comando_final = ["nmap", "-sV", HOST_AUDITORIA]
    elif partes[0] == "sqlmap":
        endpoint = partes[-1] if len(partes) > 1 else ""
        comando_final = ["sqlmap", "-u", f"{ALVO_AUDITORIA}{endpoint}", "--batch"]
    elif partes[0] == "curl":
        comando_final = ["curl", "-I", ALVO_AUDITORIA]
    else:
        comando_final = partes
    resultado = _run_seguro(comando_final, timeout=60)
    return f"Relatório de Auditoria (alvo: {ALVO_AUDITORIA}):\n{resultado}"


# ==========================================================================
# FASE 2 — RESTANTES AGENTES (stack e nome já decididos)
# ==========================================================================
ux_ui_agent = Agent(
    role="Designer de UX/UI",
    goal=f"Mapear fluxos de ecrã para o projeto, aplicando a identidade visual definida (se houver). {resumo_stack}",
    backstory=carregar_skill("ux_ui.md"),
    llm=llm_gemini, verbose=True,
)

dados_cache_agent = Agent(
    role="Arquiteto de Dados e Base de Dados",
    goal=f"Modelar o esquema de dados na base de dados escolhida. {resumo_stack}",
    backstory=carregar_skill("dados_cache.md"),
    tools=[ferramenta_db_leitura, ferramenta_db_escrita],
    llm=llm_gemini, verbose=True,
)

seguranca_agent = Agent(
    role="Engenheiro de Cibersegurança & AppSec",
    goal="Garantir boas práticas de segurança (OWASP) e, quando aplicável, a conformidade legal indicada no contexto do projeto.",
    backstory=carregar_skill("seguranca.md"),
    llm=llm_gemini, verbose=True,
)

red_team_agent = Agent(
    role="Engenheiro Red Team & Auditor",
    goal=f"Auditar o sistema próprio em {ALVO_AUDITORIA}, nunca sistemas de terceiros.",
    backstory=carregar_skill("red_team.md"),
    tools=[search_tool, ferramenta_ataque_red_team],
    llm=llm_gemini, verbose=True,
)

backend_agent = Agent(
    role="Engenheiro Backend Sénior",
    goal=f"Implementar a API/serviço de backend na linguagem e framework decididos pela arquitetura. {resumo_stack}",
    backstory=carregar_skill("backend.md"),
    tools=[search_tool, ferramenta_db_leitura, ferramenta_gestor_pacotes, ferramenta_criar_ficheiro],
    llm=llm_gemini, verbose=True,
)

frontend_agent = Agent(
    role="Engenheiro Frontend Sénior",
    goal=f"Implementar a interface no framework decidido pela arquitetura. {resumo_stack}",
    backstory=carregar_skill("frontend.md"),
    tools=[search_tool, ferramenta_gestor_pacotes, ferramenta_criar_ficheiro],
    llm=llm_gemini, verbose=True,
)

qa_agent = Agent(
    role="Engenheiro de Qualidade e Testes (QA)",
    goal="Validar cenários de teste e critérios de aceitação do projeto.",
    backstory=carregar_skill("qa.md"),
    tools=[],
    llm=llm_gemini, verbose=True,
)

devops_agent = Agent(
    role="Engenheiro DevOps e Automação",
    goal=(
        f"Gerir a pasta local ({projeto_dir}), inicializar o Git, criar o "
        f"repositório no GitHub sob '{NOME_ORGANIZACAO_GITHUB}' com um nome "
        "que reflita o projeto, e publicar/fazer deploy."
    ),
    backstory=carregar_skill("devops.md"),
    tools=[search_tool, ferramenta_devops_git, ferramenta_criar_repositorio_github, ferramenta_gestor_pacotes],
    llm=llm_gemini, verbose=True,
)

t_arq = Task(
    description=f"{resumo_stack}\nDesenha a arquitetura técnica em camadas para '{ideia_projeto}', usando a stack acima.",
    expected_output="Documento de arquitetura aprovado.",
    agent=arquiteto_agent,
)
t_ux = Task(
    description=f"{resumo_stack}\nDefine os fluxos de ecrã e padrões visuais para '{ideia_projeto}'.",
    expected_output="Especificação visual estruturada.",
    agent=ux_ui_agent,
)
t_dados = Task(
    description=(
        f"{resumo_stack}\nModela o esquema relacional e executa migrações de teste reais para "
        f"'{ideia_projeto}'. Usa a ferramenta de escrita só para CREATE/ALTER/INSERT/UPDATE."
    ),
    expected_output="Esquema SQL criado e validado na BD.",
    agent=dados_cache_agent,
)
t_backend = Task(
    description=f"{resumo_stack}\nImplementa os controladores e serviços de backend para '{ideia_projeto}', escrevendo os ficheiros com a ferramenta de criação de ficheiros, dentro de {projeto_dir}.",
    expected_output="Código de backend estruturado e ficheiros criados.",
    agent=backend_agent,
)
t_frontend = Task(
    description=f"{resumo_stack}\nImplementa os componentes de interface para '{ideia_projeto}', escrevendo os ficheiros dentro de {projeto_dir}.",
    expected_output="Código de frontend estruturado e ficheiros criados.",
    agent=frontend_agent,
)
t_seg_ini = Task(
    description=f"Estabelece as normas de segurança e, se houver contexto de conformidade legal indicado, aplica-as: {CONTEXTO_ADICIONAL or 'nenhum requisito legal específico indicado'}.",
    expected_output="Diretrizes de segurança/privacidade definidas.",
    agent=seguranca_agent,
)
t_red = Task(
    description=f"Executa auditoria de segurança APENAS contra {ALVO_AUDITORIA}. Nunca contra domínios ou IPs de terceiros.",
    expected_output="Relatório de auditoria técnica.",
    agent=red_team_agent,
)
t_seg_cor = Task(
    description="Corrige imediatamente qualquer vulnerabilidade detetada pelo Red Team.",
    expected_output="Código blindado e aprovado.",
    agent=seguranca_agent,
)
t_qa = Task(
    description="Valida os planos de teste e o comportamento funcional do sistema.",
    expected_output="Relatório de QA validado.",
    agent=qa_agent,
)
t_devops = Task(
    description=(
        f"{resumo_stack}\nExecuta a infraestrutura para '{ideia_projeto}': "
        f"1. Inicializa o Git dentro de {projeto_dir}. "
        f"2. Cria o repositório no GitHub com a ferramenta dedicada, propondo um nome "
        f"baseado em '{decisao.nome_projeto_sugerido}' (a ferramenta sanitiza-o). "
        "3. Prepara e executa a publicação/deploy. "
        "Um comando por chamada de ferramenta, sem ';', '&&' ou '|'."
    ),
    expected_output=f"Repositório criado no GitHub ('{NOME_ORGANIZACAO_GITHUB}') e código publicado.",
    agent=devops_agent,
)

fabrica_crew = Crew(
    agents=[
        ux_ui_agent, dados_cache_agent, backend_agent, frontend_agent,
        seguranca_agent, red_team_agent, qa_agent, devops_agent,
    ],
    tasks=[
        t_arq, t_ux, t_dados, t_backend, t_frontend,
        t_seg_ini, t_red, t_seg_cor, t_qa, t_devops,
    ],
    process=Process.sequential,
    verbose=True,
)

if __name__ == "__main__":
    print(f"[FASE 2] a construir '{decisao.nome_projeto_sugerido}' em {projeto_dir}...")
    resultado = fabrica_crew.kickoff()

    caminho_relatorio = os.path.join(projeto_dir, "relatorio_final.md")
    with open(caminho_relatorio, "w", encoding="utf-8") as f:
        f.write(f"# {decisao.nome_projeto_sugerido}\n\n{resumo_stack}\n\n---\n\n{str(resultado)}")

    print(f"Fábrica concluída! Relatório guardado em '{caminho_relatorio}'.")

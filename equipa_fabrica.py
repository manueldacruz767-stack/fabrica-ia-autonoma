import os
import re
import shlex
import subprocess
import unicodedata
import json
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
# CONFIGURAÇÃO DO PROJETO
# ==========================================================================
ideia_projeto = os.getenv("PROJETO_IDEIA", "Software de Gestão Alimentar - Versão 0.1")
NOME_ORGANIZACAO_GITHUB = os.getenv("NOME_ORGANIZACAO_GITHUB", "manueldacruz767-stack")
CONTEXTO_ADICIONAL = os.getenv("CONTEXTO_ADICIONAL", "").strip()
MAX_TENTATIVAS_BUILD = int(os.getenv("MAX_TENTATIVAS_BUILD", "3"))

REGRA_ANTI_OSCILACAO = f"""
[DIRETRIZ SUPREMA DE EXECUÇÃO - OBRIGATÓRIA PARA TODOS OS AGENTES]
1. Foco Absoluto no Projeto: Desenvolvimento estrito de '{ideia_projeto}', e de mais
nada. Não introduzas funcionalidades, domínios ou tecnologias que o pedido não pediu.
2. Uso Cirúrgico da Internet: SerperDevTool deve ser usada EXCLUSIVAMENTE para
consultar documentação técnica de suporte.
3. Proibição de Desvio: É ESTRITAMENTE PROIBIDO alterar regras de negócio ou
arquitetura com base em tutoriais gerais da internet. O plano interno é lei.
4. Ação Real, Nunca Especulação: quando tiveres uma ferramenta disponível,
USA-A para produzir resultados reais e verificáveis (ficheiros escritos no
disco, builds corridos, queries executadas). Nunca descrevas em texto algo
que podias ter feito de verdade com uma ferramenta.
{f"5. Contexto específico deste projeto: {CONTEXTO_ADICIONAL}" if CONTEXTO_ADICIONAL else ""}
"""

search_tool = SerperDevTool()

OPERADORES_PERIGOSOS = [";", "&&", "||", "|", "`", "$(", ">", "<"]


def _tem_operador_perigoso(comando: str) -> bool:
    return any(op in comando for op in OPERADORES_PERIGOSOS)


def slugify(texto: str, max_len: int = 40) -> str:
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
        return f"FALHOU (código {e.returncode}):\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
    except subprocess.TimeoutExpired:
        return f"Erro: o comando excedeu o tempo limite ({timeout}s)."
    except FileNotFoundError:
        return f"Erro: comando '{partes[0]}' não está instalado neste sistema."


def _caminho_seguro(base_dir: str, caminho_relativo: str):
    partes = caminho_relativo.replace("\\", "/").split("/")
    if os.path.isabs(caminho_relativo) or ".." in partes:
        return None
    return os.path.join(base_dir, caminho_relativo)


def _etapa_build(comando, cwd, timeout=300):
    resultado = _run_seguro(comando, cwd=cwd, timeout=timeout)
    return resultado.startswith("Sucesso"), resultado


def verificar_build(pasta: str):
    """Deteta o tipo de projeto numa pasta e corre o comando de
    build/compilação real adequado. Devolve (sucesso, saida)."""
    if not os.path.isdir(pasta):
        return False, f"Pasta não encontrada: {pasta}"
    if os.path.isfile(os.path.join(pasta, "pom.xml")):
        return _etapa_build(["mvn", "-q", "-DskipTests", "compile"], pasta)
    if os.path.isfile(os.path.join(pasta, "build.gradle")) or os.path.isfile(os.path.join(pasta, "build.gradle.kts")):
        return _etapa_build(["gradle", "compileJava", "-q"], pasta)
    if os.path.isfile(os.path.join(pasta, "package.json")):
        ok_install, saida_install = _etapa_build(["npm", "install"], pasta, timeout=300)
        if not ok_install:
            return False, saida_install
        scripts = {}
        try:
            with open(os.path.join(pasta, "package.json"), encoding="utf-8") as f:
                scripts = json.load(f).get("scripts", {})
        except Exception:
            pass
        if "build" in scripts:
            return _etapa_build(["npm", "run", "build"], pasta)
        if "test" in scripts:
            return _etapa_build(["npm", "test"], pasta)
        return True, "package.json encontrado e dependências instaladas; ainda sem script de build/test."
    tem_py = any(f.endswith(".py") for f in os.listdir(pasta)) if os.path.isdir(pasta) else False
    if tem_py or os.path.isfile(os.path.join(pasta, "requirements.txt")):
        return _etapa_build(["python3", "-m", "compileall", "-q", "."], pasta)
    return True, "Ainda sem ficheiros de projeto reconhecíveis nesta pasta."


def rodar_tarefa(agente, descricao, expected_output, output_pydantic=None):
    """Corre UMA task, num Crew isolado, e devolve o TaskOutput. Permite
    decidir em Python, entre tasks, se se repete, avança ou para —
    coisa que um único Crew.kickoff() com várias tasks não permite."""
    tarefa = Task(description=descricao, expected_output=expected_output,
                  agent=agente, output_pydantic=output_pydantic)
    crew = Crew(agents=[agente], tasks=[tarefa], process=Process.sequential, verbose=True)
    resultado = crew.kickoff()
    return resultado.tasks_output[-1]


# ==========================================================================
# FASE 1 — DECISÃO DE NOME E STACK
# ==========================================================================
class DecisaoStack(BaseModel):
    nome_projeto_sugerido: str
    linguagem_backend: str
    framework_backend: str
    framework_frontend: str
    base_de_dados: str
    justificacao: str


llm_gemini = LLM(model=f"gemini/{os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite')}", temperature=0.7)
# Confirmado a funcionar nesta conta via listar_modelos_gemini.py. Se voltares
# a ver 404, corre esse script de novo — os modelos Gemini mudam depressa.


def carregar_skill(nome_ficheiro: str) -> str:
    caminho = os.path.join("skills", nome_ficheiro)
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
            if conteudo:
                return f"{conteudo}\n\n{REGRA_ANTI_OSCILACAO}"
    return f"Atua estritamente como especialista.\n\n{REGRA_ANTI_OSCILACAO}"


scrum_master = Agent(role="Scrum Master & Agile Coach",
    goal="Definir o roadmap ágil, Sprints e marcos de entrega do projeto.",
    backstory=carregar_skill("scrum_master.md"), llm=llm_gemini, verbose=True)

arquiteto_agent = Agent(role="Arquiteto de Software Sénior",
    goal=("Escolher um nome curto e descritivo para o projeto e a stack mais "
          "adequada (preferir a solução mais simples que cumpre os requisitos), "
          "e depois desenhar a macro arquitetura do sistema."),
    backstory=carregar_skill("arquiteto.md"), tools=[search_tool], llm=llm_gemini, verbose=True)

t_scrum = Task(description=f"Elabora o plano e o backlog ágil para a Versão 0.1 de '{ideia_projeto}'.",
    expected_output="Backlog detalhado em Markdown.", agent=scrum_master)

t_stack = Task(
    description=(
        f"Com base no projeto '{ideia_projeto}', decide: (1) um nome curto e "
        "descritivo (2 a 4 palavras, português, sem ano/versão); (2) linguagem "
        "e framework de backend; (3) framework de frontend; (4) base de dados. "
        "Prefere tecnologias amplamente suportadas e proporcionais ao tamanho "
        "do projeto. Justifica em 3 a 5 linhas."
    ),
    expected_output="Objeto estruturado com nome, stack e justificação.",
    output_pydantic=DecisaoStack, agent=arquiteto_agent,
)

print(f"[FASE 1] a decidir nome e stack para: '{ideia_projeto}'...")
crew_fase1 = Crew(agents=[scrum_master, arquiteto_agent], tasks=[t_scrum, t_stack],
                   process=Process.sequential, verbose=True)
resultado_fase1 = crew_fase1.kickoff()

decisao = resultado_fase1.tasks_output[-1].pydantic
if decisao is None:
    raise RuntimeError("O Arquiteto não devolveu a decisão de stack em formato estruturado. Corre novamente.")

slug_projeto = slugify(decisao.nome_projeto_sugerido or ideia_projeto)
projeto_dir = os.path.join("projetos", slug_projeto)
backend_dir = os.path.join(projeto_dir, "backend")
frontend_dir = os.path.join(projeto_dir, "frontend")
docs_dir = os.path.join(projeto_dir, "docs")
for pasta in (projeto_dir, backend_dir, frontend_dir, docs_dir):
    os.makedirs(pasta, exist_ok=True)

resumo_stack = (
    f"Projeto: '{decisao.nome_projeto_sugerido}' (pasta: {projeto_dir}, "
    f"backend em {backend_dir}, frontend em {frontend_dir}). "
    f"Stack - backend: {decisao.linguagem_backend} / {decisao.framework_backend}; "
    f"frontend: {decisao.framework_frontend}; base de dados: {decisao.base_de_dados}. "
    f"Justificação do Arquiteto: {decisao.justificacao}"
)
print(f"[FASE 1 concluída]\n{resumo_stack}")

# Backlog do Scrum Master: já é texto gerado; grava-se diretamente (ele corre
# antes de existir pasta de projeto, por isso nunca teve ferramenta válida).
with open(os.path.join(projeto_dir, "backlog.md"), "w", encoding="utf-8") as f:
    f.write(resultado_fase1.tasks_output[0].raw)
print(f"[FASE 1] backlog.md gravado.")


# ==========================================================================
# FERRAMENTAS DA FASE 2
# ==========================================================================

def construir_ferramenta_criar_ficheiro(base_dir: str, nome: str):
    @tool(f"Criar ou atualizar um ficheiro dentro de {nome}")
    def ferramenta_criar_ficheiro(caminho_relativo: str, conteudo: str) -> str:
        """Cria/atualiza um ficheiro de código dentro desta pasta. Recusa
        caminhos absolutos ou com '..'. Usa isto para ESCREVER o resultado
        final, nunca para só o descreveres em texto."""
        caminho_final = _caminho_seguro(base_dir, caminho_relativo)
        if caminho_final is None:
            return "Erro de Segurança: caminho inválido (absoluto ou com '..')."
        os.makedirs(os.path.dirname(caminho_final) or ".", exist_ok=True)
        with open(caminho_final, "w", encoding="utf-8") as f:
            f.write(conteudo)
        return f"Ficheiro criado/atualizado: {caminho_final}"
    return ferramenta_criar_ficheiro


def construir_ferramenta_ler_ficheiro(base_dir: str, nome: str):
    @tool(f"Ler o conteúdo de um ficheiro dentro de {nome}")
    def ferramenta_ler_ficheiro(caminho_relativo: str) -> str:
        """Lê e devolve o conteúdo de um ficheiro já existente. Usa isto
        ANTES de corrigir um ficheiro, para saberes o que lá está."""
        caminho_final = _caminho_seguro(base_dir, caminho_relativo)
        if caminho_final is None:
            return "Erro de Segurança: caminho inválido."
        if not os.path.isfile(caminho_final):
            return f"Erro: ficheiro não encontrado: {caminho_relativo}"
        with open(caminho_final, "r", encoding="utf-8") as f:
            return f.read()
    return ferramenta_ler_ficheiro


def construir_ferramenta_listar_ficheiros(base_dir: str, nome: str):
    @tool(f"Listar os ficheiros existentes dentro de {nome}")
    def ferramenta_listar_ficheiros(subpasta: str = "") -> str:
        """Lista os caminhos relativos dos ficheiros já criados. Usa isto
        para saber o que já existe antes de ler/corrigir ficheiros."""
        base = _caminho_seguro(base_dir, subpasta) if subpasta else base_dir
        if base is None or not os.path.isdir(base):
            return f"Erro: pasta não encontrada: {subpasta}"
        linhas = [os.path.relpath(os.path.join(raiz, nome_f), base_dir)
                  for raiz, _d, fs in os.walk(base) for nome_f in fs]
        return "\n".join(sorted(linhas)) if linhas else "(pasta vazia)"
    return ferramenta_listar_ficheiros


def construir_ferramenta_gestor_pacotes(base_dir: str, nome: str):
    @tool(f"Gestor de pacotes para {nome} (npm, pip, composer, mvn, gradle, yarn, pnpm)")
    def ferramenta_gestor_pacotes(comando: str) -> str:
        """Executa um comando de gestor de pacotes dentro desta pasta."""
        gestores = {"npm", "pip", "pip3", "composer", "mvn", "gradle", "yarn", "pnpm"}
        if _tem_operador_perigoso(comando):
            return "Erro de Segurança: operadores de encadeamento não permitidos."
        try:
            partes = shlex.split(comando)
        except ValueError as e:
            return f"Erro de Segurança: comando malformado ({e})."
        if not partes or partes[0] not in gestores:
            return f"Erro de Segurança: gestor '{partes[0] if partes else ''}' não permitido."
        return _run_seguro(partes, cwd=base_dir, timeout=180)
    return ferramenta_gestor_pacotes


def construir_ferramenta_devops_git(base_dir: str):
    @tool("Executar comandos de Git, Vercel e infraestrutura dentro do projeto")
    def ferramenta_devops_git(comando: str) -> str:
        """Executa git, gh, vercel ou docker dentro da pasta do projeto. Um
        comando por chamada, sem ';', '&&', '|'. NUNCA uses '--prod' no
        vercel — só preview; produção é publicação manual humana."""
        permitidos = {"git", "gh", "vercel", "docker", "mkdir", "ls"}
        if _tem_operador_perigoso(comando):
            return "Erro de Segurança: operadores de encadeamento não permitidos."
        try:
            partes = shlex.split(comando)
        except ValueError as e:
            return f"Erro de Segurança: comando malformado ({e})."
        if not partes or partes[0] not in permitidos:
            return f"Erro de Segurança: comando '{partes[0] if partes else ''}' não permitido."
        if partes[0] == "vercel" and "--prod" in partes:
            return "Erro de Segurança: deploy em produção bloqueado. Usa só preview."
        return _run_seguro(partes, cwd=base_dir, timeout=180)
    return ferramenta_devops_git


@tool("Criar repositório no GitHub (nome sanitizado, privado por omissão)")
def ferramenta_criar_repositorio_github(nome_proposto: str, privado: bool = True) -> str:
    """Cria um repositório no GitHub sob a organização configurada. Privado
    por omissão. O nome proposto é sempre convertido para slug seguro."""
    slug = slugify(nome_proposto)
    visibilidade = "--private" if privado else "--public"
    comando = ["gh", "repo", "create", f"{NOME_ORGANIZACAO_GITHUB}/{slug}", visibilidade, "--confirm"]
    return f"{_run_seguro(comando, timeout=60)}\n(Nome final sanitizado: {slug})"


# Ferramentas de backend e frontend (cada um só mexe na sua própria pasta)
ferramenta_criar_ficheiro_backend = construir_ferramenta_criar_ficheiro(backend_dir, "backend")
ferramenta_gestor_pacotes_backend = construir_ferramenta_gestor_pacotes(backend_dir, "backend")
ferramenta_criar_ficheiro_frontend = construir_ferramenta_criar_ficheiro(frontend_dir, "frontend")
ferramenta_gestor_pacotes_frontend = construir_ferramenta_gestor_pacotes(frontend_dir, "frontend")

# Ferramentas de projeto completo (UX/UI, Segurança, QA mexem em tudo)
ferramenta_criar_ficheiro_projeto = construir_ferramenta_criar_ficheiro(projeto_dir, "projeto")
ferramenta_ler_ficheiro_projeto = construir_ferramenta_ler_ficheiro(projeto_dir, "projeto")
ferramenta_listar_ficheiros_projeto = construir_ferramenta_listar_ficheiros(projeto_dir, "projeto")
ferramenta_devops_git = construir_ferramenta_devops_git(projeto_dir)

PADRAO_DESTRUTIVO = re.compile(r"\b(drop|truncate)\b", re.IGNORECASE)
PADRAO_DELETE_SEM_WHERE = re.compile(r"\bdelete\s+from\s+\w+\s*(;|$)", re.IGNORECASE)


@tool("Consultar dados na Base de Dados Real (apenas leitura)")
def ferramenta_db_leitura(query_sql: str) -> str:
    """Executa apenas SELECT na base de dados real."""
    query = query_sql.strip()
    if not query.lower().startswith("select"):
        return "Erro de Segurança: só SELECT."
    db_url = os.getenv("DATABASE_URL_READONLY") or os.getenv("DATABASE_URL")
    if not db_url:
        return "Erro: DATABASE_URL não configurada."
    try:
        with psycopg2.connect(db_url) as conexao, conexao.cursor() as cursor:
            cursor.execute(query)
            return f"Sucesso! Dados obtidos:\n{cursor.fetchall()}"
    except Exception as e:
        return f"Erro ao consultar a base de dados: {str(e)}"


@tool("Aplicar migração ou alteração na Base de Dados Real (escrita)")
def ferramenta_db_escrita(query_sql: str) -> str:
    """CREATE/ALTER/INSERT/UPDATE. Bloqueia DROP/TRUNCATE e DELETE sem WHERE."""
    query = query_sql.strip()
    if PADRAO_DESTRUTIVO.search(query):
        return "Erro de Segurança: DROP/TRUNCATE bloqueados."
    if PADRAO_DELETE_SEM_WHERE.search(query):
        return "Erro de Segurança: DELETE sem WHERE bloqueado."
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return "Erro: DATABASE_URL não configurada."
    try:
        with psycopg2.connect(db_url) as conexao, conexao.cursor() as cursor:
            cursor.execute(query)
            conexao.commit()
        return "Comando SQL executado com sucesso!"
    except Exception as e:
        return f"Erro ao interagir com a base de dados: {str(e)}"


ALVO_AUDITORIA = os.getenv("ALVO_AUDITORIA", "http://localhost:8080")
HOST_AUDITORIA = os.getenv("HOST_AUDITORIA", "localhost")


@tool("Ferramentas de Auditoria de Segurança (Red Team) sobre o sistema próprio")
def ferramenta_ataque_red_team(subcomando: str) -> str:
    """nmap/sqlmap/curl SOMENTE contra ALVO_AUDITORIA/HOST_AUDITORIA, fixado
    pelo código. O agente escolhe o tipo de verificação, nunca o alvo."""
    permitidos = {"nmap", "sqlmap", "curl", "python3"}
    if _tem_operador_perigoso(subcomando):
        return "Erro de Segurança: operadores de encadeamento não permitidos."
    try:
        partes = shlex.split(subcomando)
    except ValueError as e:
        return f"Erro de Segurança: comando malformado ({e})."
    if not partes or partes[0] not in permitidos:
        return f"Erro: ferramenta '{partes[0] if partes else ''}' não permitida."
    if partes[0] == "nmap":
        comando_final = ["nmap", "-sV", HOST_AUDITORIA]
    elif partes[0] == "sqlmap":
        endpoint = partes[-1] if len(partes) > 1 else ""
        comando_final = ["sqlmap", "-u", f"{ALVO_AUDITORIA}{endpoint}", "--batch"]
    elif partes[0] == "curl":
        comando_final = ["curl", "-I", ALVO_AUDITORIA]
    else:
        comando_final = partes
    return f"Relatório de Auditoria (alvo: {ALVO_AUDITORIA}):\n{_run_seguro(comando_final, timeout=60)}"


# ==========================================================================
# AGENTES DA FASE 2
# ==========================================================================
ux_ui_agent = Agent(role="Designer de UX/UI",
    goal=f"Mapear fluxos de ecrã e GRAVAR a especificação num ficheiro real. {resumo_stack}",
    backstory=carregar_skill("ux_ui.md"), tools=[ferramenta_criar_ficheiro_projeto], llm=llm_gemini, verbose=True)

dados_cache_agent = Agent(role="Arquiteto de Dados e Base de Dados",
    goal=f"Modelar o esquema de dados na base de dados escolhida. {resumo_stack}",
    backstory=carregar_skill("dados_cache.md"), tools=[ferramenta_db_leitura, ferramenta_db_escrita], llm=llm_gemini, verbose=True)

seguranca_agent = Agent(role="Engenheiro de Cibersegurança & AppSec",
    goal="Ler o código real, identificar vulnerabilidades e APLICAR as correções diretamente nos ficheiros.",
    backstory=carregar_skill("seguranca.md"),
    tools=[ferramenta_listar_ficheiros_projeto, ferramenta_ler_ficheiro_projeto, ferramenta_criar_ficheiro_projeto],
    llm=llm_gemini, verbose=True)

red_team_agent = Agent(role="Engenheiro Red Team & Auditor",
    goal=f"Auditar o sistema próprio em {ALVO_AUDITORIA}, nunca sistemas de terceiros.",
    backstory=carregar_skill("red_team.md"), tools=[search_tool, ferramenta_ataque_red_team], llm=llm_gemini, verbose=True)

backend_agent = Agent(role="Engenheiro Backend Sénior",
    goal=f"Implementar um backend REAL e FUNCIONAL na stack decidida, dentro de {backend_dir}. {resumo_stack}",
    backstory=carregar_skill("backend.md"),
    tools=[search_tool, ferramenta_db_leitura, ferramenta_gestor_pacotes_backend, ferramenta_criar_ficheiro_backend],
    llm=llm_gemini, verbose=True)

frontend_agent = Agent(role="Engenheiro Frontend Sénior",
    goal=f"Implementar um frontend REAL e FUNCIONAL na stack decidida, dentro de {frontend_dir}. {resumo_stack}",
    backstory=carregar_skill("frontend.md"),
    tools=[search_tool, ferramenta_gestor_pacotes_frontend, ferramenta_criar_ficheiro_frontend],
    llm=llm_gemini, verbose=True)

qa_agent = Agent(role="Engenheiro de Qualidade e Testes (QA)",
    goal="Validar o backend e o frontend com execução REAL de build/testes e gravar o resultado real, nunca opinião.",
    backstory=carregar_skill("qa.md"),
    tools=[ferramenta_listar_ficheiros_projeto, ferramenta_ler_ficheiro_projeto, ferramenta_criar_ficheiro_projeto],
    llm=llm_gemini, verbose=True)

devops_agent = Agent(role="Engenheiro DevOps e Automação",
    goal=(f"Gerir {projeto_dir}, inicializar Git, criar repositório privado no GitHub sob "
          f"'{NOME_ORGANIZACAO_GITHUB}', e criar deploy de PREVIEW no Vercel (nunca produção)."),
    backstory=carregar_skill("devops.md"),
    tools=[search_tool, ferramenta_devops_git, ferramenta_criar_repositorio_github,
           ferramenta_gestor_pacotes_backend, ferramenta_gestor_pacotes_frontend],
    llm=llm_gemini, verbose=True)


# ==========================================================================
# EXECUÇÃO DA FASE 2 (orquestrada em Python: controlo total sobre repetições)
# ==========================================================================
print(f"\n[FASE 2] a construir '{decisao.nome_projeto_sugerido}' em {projeto_dir}...\n")

secoes_relatorio = []

# --- Arquitetura: escreve docs/arquitetura.md ---
saida_arq = rodar_tarefa(
    arquiteto_agent,
    f"{resumo_stack}\nDesenha a arquitetura técnica em camadas para '{ideia_projeto}', usando a stack acima.",
    "Documento de arquitetura em Markdown.",
)
with open(os.path.join(docs_dir, "arquitetura.md"), "w", encoding="utf-8") as f:
    f.write(saida_arq.raw)
secoes_relatorio.append(("Arquitetura", saida_arq.raw))
print("[FASE 2] docs/arquitetura.md gravado.")

# --- UX/UI: o próprio agente grava com a ferramenta ---
saida_ux = rodar_tarefa(
    ux_ui_agent,
    f"{resumo_stack}\nDefine os fluxos de ecrã para '{ideia_projeto}' e GRAVA em 'docs/especificacao-ux.md' com a ferramenta de criação de ficheiros.",
    "Ficheiro docs/especificacao-ux.md criado.",
)
secoes_relatorio.append(("UX/UI", saida_ux.raw))

# --- Dados: ações reais na BD ---
saida_dados = rodar_tarefa(
    dados_cache_agent,
    f"{resumo_stack}\nModela o esquema relacional e executa migrações de teste reais para '{ideia_projeto}'. Usa a escrita só para CREATE/ALTER/INSERT/UPDATE.",
    "Esquema SQL criado e validado na BD.",
)
secoes_relatorio.append(("Dados", saida_dados.raw))

# --- Backend: ciclo escrever -> compilar de verdade -> corrigir ---
erro_backend = ""
backend_ok = False
for tentativa in range(1, MAX_TENTATIVAS_BUILD + 1):
    desc = (
        f"{resumo_stack}\nImplementa um backend REAL e FUNCIONAL para '{ideia_projeto}' "
        f"dentro de {backend_dir}, escrevendo os ficheiros com a ferramenta de criação "
        f"de ficheiros e instalando as dependências necessárias com o gestor de pacotes."
    )
    if erro_backend:
        desc += f"\n\nA tentativa anterior FALHOU a compilar/instalar. Corrige este erro real:\n{erro_backend}"
    saida_backend = rodar_tarefa(backend_agent, desc, "Backend implementado, ficheiros criados e dependências instaladas.")
    print(f"[Backend] tentativa {tentativa}: a verificar build real...")
    backend_ok, saida_build = verificar_build(backend_dir)
    print(f"[Backend] resultado do build: {'OK' if backend_ok else 'FALHOU'}")
    if backend_ok:
        break
    erro_backend = saida_build
secoes_relatorio.append(("Backend", f"{saida_backend.raw}\n\n--- Resultado do build (tentativa {tentativa}) ---\n{'OK' if backend_ok else erro_backend}"))
if not backend_ok:
    print(f"[AVISO] Backend não ficou validado após {MAX_TENTATIVAS_BUILD} tentativas. Revê manualmente em {backend_dir}.")

# --- Frontend: mesmo ciclo ---
erro_frontend = ""
frontend_ok = False
for tentativa in range(1, MAX_TENTATIVAS_BUILD + 1):
    desc = (
        f"{resumo_stack}\nImplementa um frontend REAL e FUNCIONAL para '{ideia_projeto}' "
        f"dentro de {frontend_dir}, escrevendo os ficheiros e instalando dependências."
    )
    if erro_frontend:
        desc += f"\n\nA tentativa anterior FALHOU a compilar/instalar. Corrige este erro real:\n{erro_frontend}"
    saida_frontend = rodar_tarefa(frontend_agent, desc, "Frontend implementado, ficheiros criados e dependências instaladas.")
    print(f"[Frontend] tentativa {tentativa}: a verificar build real...")
    frontend_ok, saida_build = verificar_build(frontend_dir)
    print(f"[Frontend] resultado do build: {'OK' if frontend_ok else 'FALHOU'}")
    if frontend_ok:
        break
    erro_frontend = saida_build
secoes_relatorio.append(("Frontend", f"{saida_frontend.raw}\n\n--- Resultado do build (tentativa {tentativa}) ---\n{'OK' if frontend_ok else erro_frontend}"))
if not frontend_ok:
    print(f"[AVISO] Frontend não ficou validado após {MAX_TENTATIVAS_BUILD} tentativas. Revê manualmente em {frontend_dir}.")

# --- Segurança inicial: lê e corrige o código real ---
saida_seg_ini = rodar_tarefa(
    seguranca_agent,
    (f"Lista e lê o código em {backend_dir} e {frontend_dir}. Identifica vulnerabilidades "
     f"(OWASP) e CORRIGE-AS diretamente, reescrevendo os ficheiros afetados. "
     f"{('Aplica também este contexto de conformidade: ' + CONTEXTO_ADICIONAL) if CONTEXTO_ADICIONAL else ''}"),
    "Vulnerabilidades corrigidas diretamente nos ficheiros; resumo das correções.",
)
secoes_relatorio.append(("Segurança (revisão inicial)", saida_seg_ini.raw))

# --- Red Team: auditoria real contra o alvo fixo ---
saida_red = rodar_tarefa(
    red_team_agent,
    f"Executa auditoria de segurança APENAS contra {ALVO_AUDITORIA}. Nunca contra terceiros.\nContexto do backend: {saida_backend.raw[:1500]}",
    "Relatório de auditoria técnica.",
)
secoes_relatorio.append(("Red Team", saida_red.raw))

# --- Segurança (correção pós Red Team) ---
saida_seg_cor = rodar_tarefa(
    seguranca_agent,
    f"Lê o relatório do Red Team abaixo e os ficheiros afetados em {backend_dir}/{frontend_dir}, e CORRIGE imediatamente cada vulnerabilidade, reescrevendo os ficheiros.\n\nRelatório do Red Team:\n{saida_red.raw}",
    "Ficheiros corrigidos e resumo de cada correção aplicada.",
)
secoes_relatorio.append(("Segurança (correção pós Red Team)", saida_seg_cor.raw))

# --- QA final: build/testes reais + relatório real ---
ok_backend_final, saida_backend_final = verificar_build(backend_dir)
ok_frontend_final, saida_frontend_final = verificar_build(frontend_dir)
saida_qa = rodar_tarefa(
    qa_agent,
    (f"O build REAL do backend deu: {'OK' if ok_backend_final else 'FALHOU'}\n{saida_backend_final}\n\n"
     f"O build REAL do frontend deu: {'OK' if ok_frontend_final else 'FALHOU'}\n{saida_frontend_final}\n\n"
     f"Lista os ficheiros existentes para contexto e GRAVA um relatório final em 'relatorio_qa.md' "
     f"com este resultado real (não opines além do que os builds mostraram)."),
    "Ficheiro relatorio_qa.md criado com o resultado real e definitivo.",
)
secoes_relatorio.append(("QA (final)", saida_qa.raw))

# --- DevOps: ações reais de infraestrutura ---
saida_devops = rodar_tarefa(
    devops_agent,
    (f"{resumo_stack}\nExecuta a infraestrutura para '{ideia_projeto}': "
     f"1. Inicializa o Git dentro de {projeto_dir}. "
     f"2. Cria o repositório no GitHub (privado) com a ferramenta dedicada, "
     f"propondo um nome baseado em '{decisao.nome_projeto_sugerido}'. "
     f"3. Cria um deploy de PREVIEW no Vercel para {frontend_dir} (nunca '--prod'). "
     "Um comando por chamada, sem ';', '&&' ou '|'."),
    f"Repositório criado no GitHub ('{NOME_ORGANIZACAO_GITHUB}') e deploy de preview no Vercel.",
)
secoes_relatorio.append(("DevOps", saida_devops.raw))

# --- Relatório final consolidado ---
caminho_relatorio = os.path.join(projeto_dir, "relatorio_final.md")
with open(caminho_relatorio, "w", encoding="utf-8") as f:
    f.write(f"# {decisao.nome_projeto_sugerido}\n\n{resumo_stack}\n\n")
    f.write(f"**Backend validado por build real:** {'✅ Sim' if backend_ok else '⚠️ Não — revisão manual necessária'}\n")
    f.write(f"**Frontend validado por build real:** {'✅ Sim' if frontend_ok else '⚠️ Não — revisão manual necessária'}\n\n---\n\n")
    for titulo, texto in secoes_relatorio:
        f.write(f"## {titulo}\n\n{texto}\n\n---\n\n")

print(f"\n🎉 Fábrica concluída! Relatório consolidado em '{caminho_relatorio}'.")
print(f"   Backend: {'validado' if backend_ok else 'PRECISA DE REVISÃO MANUAL'} ({backend_dir})")
print(f"   Frontend: {'validado' if frontend_ok else 'PRECISA DE REVISÃO MANUAL'} ({frontend_dir})")

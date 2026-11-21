# Fabrica de IA Autonoma

Fabricas de software automatizadas com agentes especializados, Gemini e GitHub Actions. O fluxo padrao gera backlog, arquitetura, plano de implementacao e plano de testes num relatorio Markdown, sem executar acoes externas.

## Requisitos

- Python 3.11 ou superior
- Uma chave de API do Google Gemini (`GEMINI_API_KEY`)

## Configuracao local

```bash
python3.11 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edita o `.env` e coloca a tua `GEMINI_API_KEY`. Nunca commites o `.env`.

## Execucao

```bash
python orquestrador.py --ideia "Sistema de gestao de tarefas" --contexto contexto/hospital --saida projeto_final.md
python executar_agente.py --agente devops --tarefa "Revisar a automacao do repositorio" --saida relatorio_agente.md
```

Validacao sem chave de API e sem chamadas externas:

```bash
python orquestrador.py --dry-run --ideia validacao --saida /tmp/validacao.md
python executar_agente.py --dry-run --agente devops
```

Opcoes uteis: `--contexto` carrega um ficheiro ou diretorio de `.md` como documentos de base (ex.: `contexto/hospital`), `--modelo` escolhe o modelo Gemini preferido, `--tentativas` define repeticoes por modelo, `--pesquisa` ativa a pesquisa Serper, `--comando` solicita um comando de sistema.

## App hospitalar (MVP executavel)

O plano gerado em `projeto_final.md` foi transformado numa aplicacao real e auto-contida: API FastAPI, interface web, SQLite, RBAC, trilha de auditoria com hash, fila de Manchester, stock, leitos e higienizacao.

```bash
python -m pip install -r requirements-app.txt
python run_app.py
```

Abre `http://127.0.0.1:8000`. Para usar outra porta: `HIS_PORT=8080 python run_app.py`. A base de dados e criada em `data/his.db` (podes alterar com `HIS_DB_PATH`).

Logins de demonstracao:

| Utilizador | Palavra-passe | Perfil |
| --- | --- | --- |
| `admin` | `admin123` | Administrador Geral |
| `medico` | `medico123` | Medico |
| `enfermeiro` | `enfermeiro123` | Enfermeiro |
| `farmacia` | `farmacia123` | Farmacia |
| `limpeza` | `limpeza123` | Higienizacao |
| `gestor` | `gestor123` | Gestor de Leitos |
| `auditor` | `auditor123` | Auditoria Interna |
| `rh` | `rh123` | Recursos Humanos |
| `chefe` | `chefe123` | Chefia de Servico |
| `compras` | `compras123` | Compras e Aprovisionamento |
| `financeiro` | `financeiro123` | Financas e Contabilidade |
| `juridico` | `juridico123` | Assessoria Juridica |
| `logistica` | `logistica123` | Logistica e Armazem |
| `laboratorio` | `laboratorio123` | Laboratorio |
| `imagiologia` | `imagiologia123` | Imagiologia |
| `fisioterapia` | `fisioterapia123` | Reabilitacao |
| `rececionista` | `rececionista123` | Rececao e Agendamento |
| `diretor_clinico` | `diretor_clinico123` | Direcao Clinica |
| `diretor_enfermagem` | `diretor_enfermagem123` | Direcao de Enfermagem |
| `relacoes_publicas` | `relacoes_publicas123` | Relacoes Publicas |
| `comissao_etica` | `comissao_etica123` | Comissao de Etica |
| `direcao_pedagogica` | `direcao_pedagogica123` | Direcao Pedagogica |
| `engenharia_clinica` | `engenharia_clinica123` | Engenharia Clinica |
| `nutricionista` | `nutricionista123` | Nutricao e Dietetica |
| `transportes` | `transportes123` | Transportes e Ambulancias |
| `seguranca` | `seguranca123` | Seguranca Patrimonial |
| `ti` | `ti123` | Tecnologias de Informacao |
| `lavandaria` | `lavandaria123` | Lavandaria |
| `cozinha` | `cozinha123` | Cozinha |

Fluxo suportado na interface: registar paciente (incluindo desconhecido), abrir episodio, triagem com cor de Manchester, alocar leito, registar atendimento, prescrever, dispensar com segregacao de funcoes, dar alta medica (dispara higienizacao e encerra prescricoes), concluir higienizacao e concluir alta administrativa. O ciclo ambulatorial inclui `AGENDADO -> CHECK_IN_REALIZADO -> PRE_CONSULTA -> EM_CONSULTA -> FINALIZADO`. O internamento regista leito e motivo, e a cirurgia valida checklist, bloqueia equipamentos com manutencao vencida e pode transferir para a UCI. Tambem inclui escalas e pedidos de RH, requisicoes com validacao tecnica e cabimento, cotacoes e propostas, contratos assinados digitalmente, folha salarial e ponto, alcaladas (ate 5000 basta a Direcao Administrativa; acima disso exigem parecer favoravel de Juridico e Auditoria Interna antes da Direcao Geral), empenho e rececao por terceiro, orcamento/empenhos financeiros, pedidos MDT com resultado e validacao medica, lotes de esterilizacao, chamados de manutencao com SLA e escalonamento, stock setorial com guias de movimento, evolucao diaria, balanco hidrico, sumario de alta assinado, transferencia com guia e registo de obito. O painel mostra KPIs e a area de auditoria mostra a cadeia de hashes, unidade, perfil ativo, dispositivo, `correlation_id` e os eventos de dominio.

Endpoints principais: `/api/dashboard`, `/api/pacientes`, `/api/episodios`, `/api/fila`, `/api/consultas`, `/api/episodios/{id}/evolucoes`, `/api/episodios/{id}/balanco-hidrico`, `/api/episodios/{id}/sumario-alta`, `/api/episodios/{id}/transferencia`, `/api/episodios/{id}/obito`, `/api/unidades`, `/api/documentos/assinar`, `/api/stock-setorial`, `/api/leitos`, `/api/stock`, `/api/prescricoes/pendentes`, `/api/cirurgias/*`, `/api/esterilizacoes`, `/api/equipamentos`, `/api/manutencao/chamados`, `/api/manutencao/chamados/{id}/escalonar`, `/api/rh/*`, `/api/compras/*`, `/api/financeiro/*`, `/api/mdt/*`, `/api/auditoria`, `/api/eventos`. A documentacao interativa da API esta em `/docs`.

Testes do app:

```bash
python -m unittest tests.test_app -v
```

## Containerizacao e observabilidade

```bash
docker compose up --build
```

O compose sobe a API em `http://127.0.0.1:8000`, o consumidor do outbox, sidecars de PostgreSQL/Redis/RabbitMQ para migracao incremental e Prometheus/Grafana. A saude da aplicacao esta em `/health`, as metricas Prometheus em `/metrics`, e os eventos pendentes podem ser publicados por `POST /api/eventos/publicar` ou pelo consumidor `python -m app.consumidor_outbox`. Os logs JSON incluem `correlation_id`, que Tambem e devolvido no cabecalho `X-Correlation-ID` e pode ser enviado pelo cliente no pedido.

## GitHub Actions

Existem cinco fluxos, todos corrigidos e ativos:

| Workflow | Gatilho | Entrada principal | Saida |
| --- | --- | --- | --- |
| `fabrica_24h.yml` | diario as 08:00 UTC + manual | `vars.PROJETO_IDEIA` | `projeto_final.md` |
| `fabricar.yml` | manual | `projeto_ideia` | `projeto_final.md` |
| `main.yml` | manual | `ideia_projeto` | `relatorio_agente.md` |
| `app.yml` | alteracoes em `app/`, `tests/`, requisitos do app e CI | testes + compileall | validacao do HIS |
| `seguranca.yml` | alteracoes em `app/`, `tests/`, requisitos e CI | bandit + procura de segredos | validacao de seguranca |

Secrets necessarios em **Settings > Secrets and variables > Actions**:

- `GEMINI_API_KEY` (obrigatorio)

Variables opcionais:

- `GEMINI_MODEL` (por omissao usa `gemini-3.1-flash-lite`)
- `PROJETO_IDEIA` (usado pelo fluxo 24/7)
- `FABRICA_CONTEXTO` (caminho do diretorio `.md` com documentos de base)
- `FABRICA_ACOES_EXTERNAS` (define se os comandos de sistema sao executados)

Os fluxos validam a configuracao em modo seco, geram o relatorio, fazem upload do artifact e commitam o ficheiro gerado. O segredo antigo `GOOCLE_API_KEY` nao e utilizado.

## Modelos e resiliencia

O codigo tenta modelos por ordem e alterna automaticamente quando um modelo devolve 404 ou esta sobrecarregado (503):

1. `gemini-3.1-flash-lite`
2. `gemini-3.5-flash-lite`
3. `gemini-3.6-flash`
4. `gemini-3.7-flash`
5. `gemini-3.5-flash`
6. `gemini-3.8-flash`

`GEMINI_MODEL` coloca um modelo preferido no inicio da lista. O script `listar_modelos_gemini.py` mostra os modelos disponiveis na conta.

## Acoes externas

As acoes externas sao controladas pela variavel de repositorio `FABRICA_ACOES_EXTERNAS` (ativada neste repositorio). Para desativar: `gh variable set FABRICA_ACOES_EXTERNAS --body false`.

Comandos permitidos: `git status/log/diff/remote/branch`, `gh auth/repo/run/workflow`, `vercel --version/whoami/list/deploy`, `npm/pip --version/list`, `ls`, `docker --version/ps`. Python arbitrario, encadeamentos e `vercel --prod` sao bloqueados.

Localmente:

```bash
FABRICA_ACOES_EXTERNAS=1 python executar_agente.py --comando "git status --short"
```

Secrets usados nos workflows: `GEMINI_API_KEY`, `SERPER_API_KEY`, `FABRICA_GH_TOKEN`, `VERCEL_TOKEN`, `DATABASE_URL`.

A fabrica completa com CrewAI e agentes adicionais e opt-in:

```bash
python -m pip install -r requirements-crewai.txt
FABRICA_MODO_COMPLETO=1 python equipa_fabrica.py
```

## Testes

```bash
python -m unittest discover -s tests -v
python -m compileall -q fabrica_core.py orquestrador.py executar_agente.py ferramentas_sistema.py pesquisa_web.py
```

## Estrutura

- `fabrica_core.py` - cliente Gemini com fallback, skills, seguranca e escrita de relatorios
- `orquestrador.py` - entrada principal multi-agente
- `executar_agente.py` - entrada de agente unico
- `skills/` - diretrizes obrigatorias dos agentes
- `contexto/hospital/` - documentos `.md` do sistema hospitalar usados como contexto
- `equipa_fabrica.py` - fabrica completa com CrewAI (opt-in)
- `app/` - aplicacao hospitalar FastAPI, regras de dominio, seguranca e interface web
- `run_app.py` - arranque local do app
- `requirements-app.txt` - dependencias do app
- `experimental/fabrica_ahs.py` - variacao antiga guardada para referencia
- `.github/workflows/` - automatizacao na nuvem

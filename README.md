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

## GitHub Actions

Existem tres fluxos, todos corrigidos e ativos:

| Workflow | Gatilho | Entrada principal | Saida |
| --- | --- | --- | --- |
| `fabrica_24h.yml` | diario as 08:00 UTC + manual | `vars.PROJETO_IDEIA` | `projeto_final.md` |
| `fabricar.yml` | manual | `projeto_ideia` | `projeto_final.md` |
| `main.yml` | manual | `ideia_projeto` | `relatorio_agente.md` |

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
- `experimental/fabrica_ahs.py` - variacao antiga guardada para referencia
- `.github/workflows/` - automatizacao na nuvem

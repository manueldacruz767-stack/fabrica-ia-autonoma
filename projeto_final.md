# Fabrica de IA Autonoma - Relatorio Final

**Ideia:** FutPremier - Fabrica de IA Autonoma

## scrum_master

_Modelo: gemini-3.1-flash-lite_

Como Scrum Master da **FutPremier - Fábrica de IA Autónoma**, apresento o planeamento da Versão 0.1. O foco desta fase é a infraestrutura base e a capacidade de processamento de dados de futebol.

---

### Backlog da Versão 0.1 (MVP)

| ID | História de Utilizador | Prioridade | Sprint |
| :--- | :--- | :--- | :--- |
| US01 | Configuração do ambiente de ingestão de dados de ligas europeias. | Alta | 1 |
| US02 | Desenvolvimento do motor de análise de performance de jogadores. | Alta | 1 |
| US03 | Implementação da API de interface para consulta de métricas. | Média | 2 |
| US04 | Criação do módulo de relatórios automatizados de scouting. | Média | 2 |

---

### Detalhe das Tarefas e Critérios de Aceitação

#### Sprint 1: Fundação e Ingestão
**US01: Ingestão de Dados**
*   **Tarefas:** Configurar conectores com fontes de dados (APIs de futebol), estruturar base de dados relacional.
*   **Critérios de Aceitação:**
    1. Conexão estabelecida com pelo menos 3 ligas principais.
    2. Dados brutos armazenados com sucesso em formato JSON/SQL.
    3. Validação de integridade de dados (ausência de valores nulos críticos).

**US02: Motor de Análise**
*   **Tarefas:** Criar algoritmos de cálculo de métricas (xG, passes decisivos, ocupação de espaço).
*   **Critérios de Aceitação:**
    1. O motor processa um jogo completo em menos de 5 minutos.
    2. As métricas calculadas correspondem aos dados de entrada com margem de erro < 0.1%.

#### Sprint 2: Interface e Output
**US03: API de Consulta**
*   **Tarefas:** Desenvolver endpoints para consulta de jogadores e equipas.
*   **Critérios de Aceitação:**
    1. Endpoints respondem em formato JSON.
    2. Autenticação básica implementada.
    3. Documentação Swagger/OpenAPI disponível.

**US04: Relatórios de Scouting**
*   **Tarefas:** Criar template de relatório PDF/Markdown baseado nos dados processados.
*   **Critérios de Aceitação:**
    1. Relatório gerado automaticamente após o processamento de cada jogo.
    2. Inclusão de indicadores de performance (KPIs) definidos na US02.

---

### Notas de Comunicação
*   **Sincronização:** As equipas de Engenharia de Dados e IA devem reunir-se diariamente (Daily Scrum) para garantir que a estrutura de dados da US01 suporta os algoritmos da US02.
*   **Qualidade:** Nenhum código será considerado concluído sem a passagem nos testes unitários definidos nos critérios de aceitação.

---

## arquiteto

_Modelo: gemini-3.1-flash-lite_

Como Arquiteto de Software, apresento a proposta estrutural para o **FutPremier - Fábrica de IA Autónoma**. O foco é a separação de responsabilidades, escalabilidade e a utilização da stack híbrida definida.

---

### 1. Stack Tecnológica
*   **Backend:** Node.js (TypeScript) com NestJS (Modularidade).
*   **Frontend:** Next.js (SSR/SSG para performance).
*   **Base de Dados Relacional:** Supabase (PostgreSQL) para gestão de utilizadores, ligas, apostas e dados transacionais.
*   **Base de Dados NoSQL:** MongoDB Atlas para armazenamento de logs de execução da IA, histórico de prompts e dados não estruturados de análise de jogos.
*   **Infraestrutura:** Vercel (Frontend/API) + Supabase (Auth/DB) + MongoDB Atlas (Cloud).

---

### 2. Arquitetura em Camadas

A arquitetura segue o padrão de **Clean Architecture**, garantindo que a lógica de negócio seja independente de frameworks e bases de dados.

#### A. Camada de Apresentação (Interface)
*   **Componente:** Next.js.
*   **Responsabilidade:** Renderização da interface do utilizador, gestão de estado global e consumo da API via SDK do Supabase.

#### B. Camada de Aplicação (API Gateway / Orquestração)
*   **Componente:** NestJS (Controllers e Services).
*   **Responsabilidade:** Validação de inputs, orquestração de chamadas entre serviços de IA e persistência de dados.

#### C. Camada de Domínio (Core Business)
*   **Componente:** Entidades e Casos de Uso.
*   **Responsabilidade:** Regras de negócio da "Fábrica de IA" (ex: lógica de decisão de apostas, processamento de métricas). Não conhece a base de dados.

#### D. Camada de Infraestrutura (Data Access)
*   **Componente:** Repositórios.
*   **Responsabilidade:** 
    *   **Supabase Client:** Persistência relacional (Users, Wallets, Matches).
    *   **MongoDB Driver:** Persistência de logs de IA e telemetria de performance.

---

### 3. Limites e Integração

*   **Isolamento de Dados:**
    *   O **Supabase** atua como a "fonte da verdade" para o estado do sistema e autenticação.
    *   O **MongoDB** atua como um "Data Lake" para observabilidade e análise histórica da IA, garantindo que o PostgreSQL não seja sobrecarregado com logs de alta frequência.
*   **Segurança:**
    *   Utilização de *Row Level Security* (RLS) no Supabase para garantir que cada utilizador aceda apenas aos seus dados.
    *   Variáveis de ambiente segregadas para chaves de API de IA (ex: OpenAI/Anthropic) e strings de conexão das bases de dados.

---

### 4. Fluxo de Execução (Exemplo)
1.  O utilizador solicita uma análise via **Frontend**.
2.  O **NestJS** processa a lógica de negócio.
3.  O sistema consulta o **Supabase** para validar permissões e dados da liga.
4.  O sistema executa a IA e armazena o resultado/log no **MongoDB Atlas** para auditoria futura.
5.  O resultado final é persistido no **Supabase** e retornado ao utilizador.

---

## programador

_Modelo: gemini-3.1-flash-lite_

Como Programador Full-Stack Sénior, apresento o plano de implementação para o **FutPremier - Fábrica de IA Autónoma**. A arquitetura foca-se em microsserviços desacoplados, garantindo escalabilidade e modularidade.

---

### 1. Estrutura de Ficheiros (Arquitetura)

```text
/futpremier-core
├── /api-gateway (Node.js/Fastify)      # Orquestração e Auth
├── /worker-ia (Python/FastAPI)         # Processamento de modelos e análise
├── /data-pipeline (Python/Pandas)      # ETL de dados de futebol
├── /shared-lib                         # Módulos reutilizáveis (logger, db-client)
└── docker-compose.yml                  # Orquestração de ambiente
```

---

### 2. Responsabilidades por Módulo

*   **API Gateway (Node.js):** Gestão de rotas, autenticação JWT, rate limiting e proxy para os serviços internos.
*   **Worker IA (Python):** Motor de inferência. Recebe inputs, processa via modelos de ML (Scikit-learn/PyTorch) e retorna previsões.
*   **Data Pipeline (Python):** Ingestão de dados via APIs externas, limpeza com Pandas e persistência em base de dados vetorial/relacional.
*   **Shared Lib:** Contratos de interface, tratamento de erros centralizado e utilitários de logging.

---

### 3. Plano de Implementação Ordenado

1.  **Fase 1 (Infraestrutura):** Configuração do `docker-compose` e definição dos contratos de API (OpenAPI/Swagger).
2.  **Fase 2 (Data Layer):** Implementação do `data-pipeline` para garantir a integridade dos dados de treino.
3.  **Fase 3 (Core IA):** Desenvolvimento dos endpoints de inferência no `worker-ia` com FastAPI.
4.  **Fase 4 (Gateway):** Implementação da camada de segurança e roteamento no `api-gateway`.
5.  **Fase 5 (Monitorização):** Integração de logs estruturados e métricas de performance.

---

### 4. Riscos Técnicos

*   **Latência de Inferência:** O processamento de modelos complexos pode exceder o timeout do gateway. *Mitigação:* Implementar filas de mensagens (RabbitMQ/Redis) para processamento assíncrono.
*   **Drift de Dados:** A qualidade dos dados de futebol varia. *Mitigação:* Implementar validação de schema rigorosa no pipeline de ingestão.
*   **Escalabilidade do Estado:** O estado da IA autónoma pode tornar-se um gargalo. *Mitigação:* Utilizar armazenamento distribuído (Redis) para cache de contexto curto.

---

### 5. Padrões de Qualidade
*   **Código:** Seguir *Clean Code* e *SOLID*.
*   **Testes:** Cobertura mínima de 80% (PyTest para Python, Jest para Node.js).
*   **Excepções:** Tratamento global de erros com códigos de estado HTTP padronizados e registo de stack trace em ambiente de desenvolvimento.

---

## qa

_Modelo: gemini-3.1-flash-lite_

Como Agente de Garantia de Qualidade (QA) para o projeto **FutPremier - Fábrica de IA Autónoma**, apresento o plano de testes estruturado para assegurar a robustez e a conformidade do sistema.

---

### 1. Plano de Testes Unitários
Focados na lógica isolada dos módulos de IA e processamento de dados.

*   **Comandos Concretos:**
    *   `pytest tests/unit/test_agent_logic.py`: Validar a tomada de decisão da IA.
    *   `pytest tests/unit/test_data_parser.py`: Validar a normalização de inputs de dados de futebol.
*   **Critérios de Conclusão:**
    *   Cobertura de código mínima de 85%.
    *   Zero falhas em testes de lógica de decisão (ex: predição de resultados).

### 2. Plano de Testes de Integração
Focados na comunicação entre os módulos da Fábrica de IA e APIs externas.

*   **Comandos Concretos:**
    *   `pytest tests/integration/test_api_flow.py`: Verificar a persistência de dados entre a IA e a base de dados.
    *   `pytest tests/integration/test_external_provider.py`: Validar a integridade da resposta das APIs de estatísticas desportivas.
*   **Critérios de Conclusão:**
    *   Sucesso na troca de mensagens entre o orquestrador e os agentes.
    *   Tratamento de erros (timeouts/404) implementado e funcional.

### 3. Plano de Testes de Aceitação (UAT)
Validação baseada nos critérios do Scrum Master para o FutPremier.

*   **Comandos Concretos:**
    *   `python scripts/run_acceptance_suite.py --scenario full_cycle`: Executar o fluxo completo de uma análise de jogo.
*   **Critérios de Conclusão:**
    *   A IA deve gerar um relatório de predição formatado conforme o template definido.
    *   O tempo de resposta do sistema deve ser inferior a 5 segundos por análise.
    *   Os resultados devem ser auditáveis através dos logs de execução.

---

### Procedimento de Reporte de Bugs
Qualquer falha detetada durante a execução dos comandos acima deve ser registada seguindo o formato:
1.  **ID do Bug:** [Data]-[Módulo]-[Breve Descrição]
2.  **Passos para Reproduzir:** (Comandos exatos utilizados)
3.  **Resultado Esperado:** (O que deveria ter ocorrido)
4.  **Resultado Obtido:** (O erro retornado)
5.  **Severidade:** (Crítica/Alta/Média/Baixa)

---
*Nota: Este plano está pronto para ser aplicado no ambiente de desenvolvimento. Aguardo a disponibilização do repositório para iniciar a execução dos testes.*

---

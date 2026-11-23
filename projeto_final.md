# Fabrica de IA Autonoma - Relatorio Final

**Ideia:** Sistema de Gestão Hospitalar Pública (HIS)

## scrum_master

_Modelo: gemini-3.6-flash_

# Agent: Scrum Master
**Versão do Documento:** 1.0 (Plano de Sprint e Backlog da Versão 0.1)  
**Projeto:** Sistema de Gestão Hospitalar Pública (HIS)

---

## 1. Visão Geral da Versão 0.1 (MVP Foundation)

O objetivo da **Versão 0.1** é estabelecer a base arquitetural e operacional do HIS, cobrindo a infraestrutura central, controlo de acessos (RBAC), o fluxo primário de **Urgência/Emergência** (Admissão, Triagem de Manchester e Atendimento Médico de Emergência), o motor imutável de **Audit Trail** e a observabilidade inicial com gestão de ativos críticos.

---

## 2. Divisão por Sprints

* **Sprint 1 (Duração: 2 semanas):** Arquitetura Base, Autenticação, Controlo de Acesso (RBAC) e Estrutura Orgânica.
* **Sprint 2 (Duração: 2 semanas):** Prontuário do Paciente, Admissão de Urgência e Triagem de Risco (Manchester).
* **Sprint 3 (Duração: 2 semanas):** Atendimento Médico de Urgência, Prescrição Inicial, Audit Trail Imutável e Observabilidade.

---

## 3. Backlog Detalhado por História de Utilizador (User Stories)

### SPRINT 1: Arquitetura Base, Autenticação e Matriz RBAC

#### US01 — Setup da Arquitetura Base e Persistência
* **Prioridade:** P1 (Alta)
* **Sprint:** Sprint 1
* **Descrição:** Como Engenheiro de Software, quero inicializar a estrutura do monólito modular (Spring Boot / NestJS) com PostgreSQL, Redis e RabbitMQ/Transactional Outbox, para garantir a consistência de dados e mensageria assíncrona.
* **Tarefas Atómicas:**
  1. Configurar projeto base com estrutura modular por domínios.
  2. Criar migrations do banco relacional (PostgreSQL) para tabelas core.
  3. Configurar Redis para cache de permissões e controle de sessão.
  4. Configurar RabbitMQ para eventos de domínio internos.
* **Critérios de Aceitação (Verificáveis):**
  - [ ] A aplicação arranca via Docker Compose subindo PostgreSQL, Redis e RabbitMQ sem erros.
  - [ ] A base de dados executa migrations com sucesso e cria os schemas iniciais.
  - [ ] Um evento de teste publicado no RabbitMQ é consumido com sucesso por um ouvinte de teste.

#### US02 — Gestão de Autenticação JWT e Matriz RBAC Granular
* **Prioridade:** P1 (Alta)
* **Sprint:** Sprint 1
* **Descrição:** Como Administrador do Sistema, quero autenticar utilizadores e aplicar permissões baseadas em perfis (RBAC), para garantir que cada profissional aceda apenas às funcionalidades autorizadas.
* **Tarefas Atómicas:**
  1. Implementar endpoint de login com emissão de token JWT contendo `utilizador_id`, `perfil_ativo` e `unidade_hospitalar`.
  2. Criar middleware/interceptor de autorização validando permissões por rota e método HTTP.
  3. Mapear perfis iniciais: Diretor Geral, Diretor Clínico, Médico, Enfermeiro-Chefe, Enfermeiro, Técnico MDT e Admin Financeiro.
* **Critérios de Aceitação (Verificáveis):**
  - [ ] Utilizador autenticado recebe um token JWT válido com validade máxima de 8 horas.
  - [ ] Requisição efetuada por perfil sem permissão devolve status HTTP `403 Forbidden`.
  - [ ] Utilizador com perfil `Médico` consegue aceder à rota de prescrição; perfil `Administrativo` recebe `403` na mesma rota.

#### US03 — Cadastro de Unidades Organizacionais e Utilizadores
* **Prioridade:** P2 (Média)
* **Sprint:** Sprint 1
* **Descrição:** Como Administrador, quero registar a hierarquia de unidades hospitalares e os utilizadores do sistema, para permitir a alocação correta nos setores.
* **Tarefas Atómicas:**
  1. Criar modelo e endpoints para CRUD de Unidades Organizacionais (Serviço de Urgência, Bloco, UCI, Farmácia, etc.).
  2. Criar endpoints para registo e vinculação de utilizadores a perfis e unidades.
* **Critérios de Aceitação (Verificáveis):**
  - [ ] É possível cadastrar uma unidade organizacional hierárquica (ex.: Nível 1 -> Direção Geral; Nível 3 -> Urgência).
  - [ ] Tentar inativar um utilizador invalida imediatamente as sessões ativas do mesmo no Redis.

---

### SPRINT 2: Admissão, Prontuário e Triagem de Urgência

#### US04 — Gestão do Prontuário do Paciente e Ficha Provisória
* **Prioridade:** P1 (Alta)
* **Sprint:** Sprint 2
* **Descrição:** Como Rececionista/Enfermeiro, quero cadastrar e pesquisar prontuários de pacientes, permitindo a abertura de ficha provisória em casos de emergência desacompanhada.
* **Tarefas Atómicas:**
  1. Criar entidade `Paciente` (Nome, Documento, Data Nascimento, Sexo, Nome da Mãe).
  2. Implementar funcionalidade "Paciente Indocumentado / Desconhecido" com identificador temporário gerado automaticamente.
  3. Criar rotina de fusão de prontuários (Merge) para unificar ficha provisória à definitiva posterior.
* **Critérios de Aceitação (Verificáveis):**
  - [ ] O sistema permite criar uma ficha de emergência apenas com Sexo Estimado e Cor/Características sem documento de identificação.
  - [ ] A funcionalidade de fusão transfere todo o histórico clínico da ficha provisória para o prontuário definitivo e marca a ficha anterior como `FUSIONADA`.

#### US05 — Abertura de Episódio de Urgência e Encaminhamento
* **Prioridade:** P1 (Alta)
* **Sprint:** Sprint 2
* **Descrição:** Como Rececionista, quero abrir um episódio de urgência para um paciente, alterando o seu estado para `AGUARDANDO_TRIAGEM`.
* **Tarefas Atómicas:**
  1. Criar máquina de estados do Episódio de Urgência.
  2. Criar endpoint para abertura de episódio associando paciente, data/hora e setor de acolhimento.
  3. Disparar evento de domínio `EpisodioUrgenciaCriado`.
* **Critérios de Aceitação (Verificáveis):**
  - [ ] Abertura de episódio altera o estado do paciente para `AGUARDANDO_TRIAGEM`.
  - [ ] O sistema impede a abertura de dois episódios de urgência ativos em simultâneo para o mesmo paciente.

#### US06 — Classificação de Risco (Triagem de Manchester)
* **Prioridade:** P1 (Alta)
* **Sprint:** Sprint 2
* **Descrição:** Como Enfermeiro, quero registar os sinais vitais e a queixa principal do paciente para definir a prioridade de atendimento (Protocolo de Manchester).
* **Tarefas Atómicas:**
  1. Criar interface e API para registo de sinais vitais (PA, Frequência Cardíaca, Temperatura, SpO2, Glicemia).
  2. Implementar formulário de classificação com atribuição de cor/prioridade (Vermelho, Laranja, Amarelo, Verde, Azul).
  3. Atualizar estado do episódio para `AGUARDANDO_MEDICO` e ordenar a fila de espera por prioridade/tempo.
* **Critérios de Aceitação (Verificáveis):**
  - [ ] O registo de triagem calcula e atribui a cor de risco corretamente segundo o algoritmo configurado.
  - [ ] A lista de pacientes aguardando médico exibe no topo os pacientes classificados como Vermelho/Laranja, independentemente da ordem de chegada.
  - [ ] O estado do episódio transita de `EM_TRIAGEM` para `AGUARDANDO_MEDICO`.

---

### SPRINT 3: Atendimento Médico, Prescrição, Audit Trail e Observabilidade

#### US07 — Atendimento Médico e Prescrição de Emergência
* **Prioridade:** P1 (Alta)
* **Sprint:** Sprint 3
* **Descrição:** Como Médico, quero registar a evolução clínica do paciente e emitir prescrição de medicamentos de urgência.
* **Tarefas Atómicas:**
  1. Criar interface/API para registo de anamnese, hipótese diagnóstica (CID-10) e conduta.
  2. Criar funcionalidade de prescrição de medicamentos integrada ao catálogo simples.
  3. Alterar estado do episódio para `EM_ATENDIMENTO` e post-atendimento para `AGUARDANDO_EXAMES_OU_MEDICACAO` ou `ENCERRADO`.
* **Critérios de Aceitação (Verificáveis):**
  - [ ] Apenas utilizadores com perfil `Médico` conseguem assinar e concluir o formulário de atendimento e prescrição.
  - [ ] Uma prescrição emitida dispara um evento assíncrono `PrescricaoEmitida` para visualização no módulo de enfermagem/farmácia.

#### US08 — Motor de Audit Trail Imutável e "Break-the-Glass"
* **Prioridade:** P1 (Alta)
* **Sprint:** Sprint 3
* **Descrição:** Como Auditor Interno, quero que todas as operações críticas e acessos excecionais sejam registados numa tabela imutável para conformidade legal e segurança.
* **Tarefas Atómicas:**
  1. Criar tabela particionada e repositório append-only para `logs_auditoria`.
  2. Implementar interceptador de auditoria registando: `utilizador_id`, `perfil_ativo`, `unidade_hospitalar`, `acao`, `dados_anteriores`, `dados_novos`, `timestamp` e `ip_origem`.
  3. Criar fluxo "Break-the-Glass" com justificativa obrigatória para acesso emergencial a dados restritos.
* **Critérios de Aceitação (Verificáveis):**
  - [ ] Qualquer alteração de estado no prontuário ou emissão de prescrição gera um registo em `logs_auditoria`.
  - [ ] O sistema rejeita pedidos de alteração ou eliminação (`UPDATE`/`DELETE`) de registos da tabela de audit trail.
  - [ ] Abertura de prontuário via "Break-the-Glass" sem preenchimento do campo de justificativa devolve erro de validação `400 Bad Request`.

#### US09 — Observabilidade e Gestão Básica de Ativos Médicos
* **Prioridade:** P2 (Média)
* **Sprint:** Sprint 3
* **Descrição:** Como Engenheiro Clínico / DevOps, quero monitorizar as métricas de saúde da aplicação e registar equipamentos vitais com alertas de manutenção preventivos.
* **Tarefas Atómicas:**
  1. Expor endpoints de `/actuator/health` ou `/health` detalhados (DB, Redis, RabbitMQ).
  2. Configurar métricas Prometheus para contagem de requisições, latência e erros 5xx.
  3. Criar cadastro básico de equipamentos médicos e funcionalidade de alerta para calibração vencida.
* **Critérios de Aceitação (Verificáveis):**
  - [ ] O endpoint de `/health` devolve HTTP 200 `UP` quando todos os serviços dependentes estão operacionais.
  - [ ] O Prometheus consegue raspar (*scrape*) as métricas de desempenho expostas pelo sistema.
  - [ ] Equipamentos com data de manutenção preventiva inferior a 7 dias geram um alerta visual no painel de administração.

---

## 4. Diretrizes de Comunicação entre Agentes da Fábrica

1. **Desenvolvimento (Backend / Frontend):**
   - Não iniciar o desenvolvimento de qualquer User Story sem que os **Critérios de Aceitação** estejam validados pelo Scrum Master e Product Owner.
   - Respeitar estritamente as regras de **Segregação de Funções (SoD)** e **RBAC** descritas na especificação funcional.
2. **Garantia da Qualidade (QA / Testes):**
   - Os testes automatizados (unitários e de integração) devem cobrir obrigatoriamente as transições da máquina de estados do episódio e o registo imutável do Audit Trail.
3. **DevOps / Infraestrutura:**
   - Garantir que as variáveis de ambiente e segredos de produção nunca sejam expostos em código-fonte, utilizando ficheiros `.env` e repositórios seguros.

---

## arquiteto

_Modelo: gemini-3.1-flash-lite_

Como Arquiteto de Software, apresento a proposta de arquitetura para o Sistema de Gestão Hospitalar (HIS), focada em modularidade, resiliência e conformidade com as exigências de um hospital público.

---

### 1. Stack Tecnológica Recomendada
A escolha prioriza a robustez do ecossistema Java e a flexibilidade do Frontend moderno, mantendo a persistência híbrida conforme a nossa *skill* oficial.

*   **Backend:** Java 21 + Spring Boot 3.x (Arquitetura Modular Monolith).
*   **Frontend:** Angular 17+ (TypeScript) com Angular Material (foco em formulários complexos e acessibilidade).
*   **Persistência Relacional (Dados Críticos):** **Supabase (PostgreSQL)** para prontuários, transações financeiras, escalas e gestão de leitos (Garante ACID).
*   **Persistência NoSQL (Logs/Auditoria):** **MongoDB Atlas** para trilhas de auditoria imutáveis, logs de sistema e dados não estruturados de dispositivos médicos.
*   **Cache e Mensageria:** Redis (Sessões/Rate Limiting) e RabbitMQ (Eventos de domínio/Integração HL7).
*   **Infraestrutura:** Docker + Kubernetes (K8s) para orquestração e alta disponibilidade.

---

### 2. Arquitetura em Camadas (Modular Monolith)

A estrutura é dividida em **Bounded Contexts** (Módulos) independentes dentro do mesmo *deployable*, permitindo a extração futura para microsserviços.

#### A. Camada de Apresentação (Frontend)
*   **Interface:** SPA (Single Page Application) com roteamento baseado em permissões (RBAC).
*   **Componentes:** Formulários reativos, dashboards de monitorização em tempo real e atalhos de teclado para triagem.

#### B. Camada de API Gateway / Segurança
*   **Autenticação:** JWT com integração OAuth2/OIDC.
*   **RBAC/ABAC:** Interceptor de segurança que valida permissões em cada *endpoint* com base no perfil do utilizador (Médico, Enfermeiro, Administrativo).

#### C. Camada de Domínio (Backend - Spring Boot)
*   **Módulos:**
    *   `Core-Assistencial`: Urgência, Internamento, Bloco.
    *   `Core-Suporte`: Logística, Farmácia, RH, Financeiro.
    *   `Core-Governança`: Auditoria, Pareceres Jurídicos, KPI.
*   **Padrões:**
    *   **State Machines:** Para transições de estado (ex: `AGUARDANDO_TRIAGEM` -> `EM_ATENDIMENTO`).
    *   **Transactional Outbox:** Para garantir que eventos (ex: `AltaMedica`) sejam publicados no RabbitMQ apenas se a transação no Postgres for confirmada.

#### D. Camada de Persistência (Híbrida)
*   **PostgreSQL (Supabase):** Tabelas normalizadas para dados transacionais (Pacientes, Prescrições, Escalas).
*   **MongoDB Atlas:** Coleção de documentos para *Audit Trail* (quem, quando, o quê, IP, perfil) e logs de telemetria de equipamentos.

---

### 3. Fluxo de Dados e Integração

1.  **Entrada:** O pedido chega via API Gateway, validado pelo Spring Security.
2.  **Processamento:** O módulo de domínio executa a regra de negócio e inicia a transação ACID no PostgreSQL.
3.  **Auditoria:** O *Event Listener* captura a alteração e envia um evento assíncrono para o MongoDB (Auditoria) e RabbitMQ (Notificações/Alertas).
4.  **Observabilidade:** Prometheus coleta métricas de latência e saúde dos *pods* K8s, exportando para o Grafana.

---

### 4. Limites e Regras de Segurança (SoD)

*   **Segregação de Funções (SoD):** A camada de serviço impede que o mesmo `User_ID` inicie e aprove a mesma transação financeira (ex: `Compra` vs `Aprovação`).
*   **Break-the-Glass:** *Endpoint* específico que permite acesso emergencial, registando o evento com flag de "Acesso Excecional" no MongoDB, disparando alerta imediato para a Auditoria Interna.
*   **Isolamento:** Cada módulo de domínio possui o seu próprio esquema de base de dados (ou *namespace* no Postgres), garantindo que falhas em módulos não críticos (ex: RH) não impactem o módulo crítico (ex: Urgência).

Esta arquitetura garante que o sistema seja **previsível**, **auditorável** e **altamente disponível**, requisitos fundamentais para a gestão hospitalar pública.

---

## programador

_Modelo: gemini-3.1-flash-lite_

Este plano de implementação organiza o desenvolvimento do **Sistema de Gestão Hospitalar (HIS)** seguindo uma abordagem de **Monólito Modular**, garantindo a separação de domínios e a integridade transacional exigida.

---

### 1. Estrutura de Diretórios (Modular Monolith)
A estrutura reflete os domínios de negócio, facilitando a futura extração para microsserviços.

```text
/src
  /modules
    /urgencia       # Triagem, Admissão, Fluxo de Manchester
    /ambulatorio    # Agendamento, Consultas
    /internamento   # Gestão de Leitos, Bloco, UCI
    /mdt            # Laboratório, Imagiologia, Farmácia
    /administrativo # RH, Financeiro, Compras, Logística
    /governanca     # Auditoria, Pareceres, Relatórios
  /shared
    /database       # Configuração PostgreSQL, Migrations
    /messaging      # RabbitMQ/Outbox Pattern
    /security       # RBAC/ABAC, JWT, Auth
    /observability  # Logs JSON, Correlation ID
```

---

### 2. Plano de Implementação (Fases)

#### Fase 1: Fundação e Segurança (Semanas 1-4)
*   **Setup:** Configuração do ambiente (Node.js/NestJS ou Java/Spring Boot), Docker Compose e PostgreSQL.
*   **Segurança:** Implementação do motor de **RBAC/ABAC** conforme a matriz de permissões.
*   **Audit Trail:** Criação do *Interceptor* global para registo imutável de ações (`AuditLog`).
*   **Risco Técnico:** Falha na granularidade das permissões. *Mitigação:* Testes unitários para cada regra de acesso.

#### Fase 2: Ciclo Assistencial (Semanas 5-12)
*   **Módulos:** Urgência e Internamento.
*   **Funcionalidades:** Máquinas de estado para pacientes (`ADMITIDO` -> `TRIAGEM` -> `ALTA`).
*   **Integração:** Implementação do padrão *Outbox* para disparar eventos de "Leito Ocupado/Livre" para o módulo de Serviços Gerais.
*   **Risco Técnico:** Concorrência na alocação de leitos. *Mitigação:* Uso de transações ACID e bloqueios otimistas no PostgreSQL.

#### Fase 3: Ciclo de Suporte e Logística (Semanas 13-20)
*   **Módulos:** Administrativo, Financeiro e MDT.
*   **Funcionalidades:** Fluxo de compras com aprovação por alçadas e gestão de stock.
*   **Segregação de Funções (SoD):** Garantir que o utilizador que solicita não é o mesmo que aprova.
*   **Risco Técnico:** Rutura de stock crítico. *Mitigação:* Alertas automáticos via Prometheus/Grafana.

#### Fase 4: Governação e Observabilidade (Semanas 21-24)
*   **BI:** Configuração do *Data Mart* analítico e conexão com Apache Superset.
*   **Monitorização:** Dashboards de saúde do sistema (latência, erros 5xx, filas).
*   **Disaster Recovery:** Testes de restauração de backups WAL.

---

### 3. Responsabilidades por Domínio (Squads)

| Squad | Foco Principal | Responsabilidade |
| :--- | :--- | :--- |
| **Squad Clínico** | Urgência, Internamento, MDT | Prontuário, Prescrição, Máquinas de Estado. |
| **Squad Apoio** | Adm, Financeiro, Logística | Workflow de Compras, RH, Gestão de Stocks. |
| **Squad Core/DevOps** | Segurança, Infra, Auditoria | RBAC, CI/CD, Observabilidade, Auditoria. |

---

### 4. Riscos Técnicos e Estratégias de Mitigação

1.  **Integridade dos Dados Clínicos:**
    *   *Risco:* Perda de histórico ou inconsistência em prescrições.
    *   *Mitigação:* Uso rigoroso de transações ACID e *Audit Trail* imutável.
2.  **Complexidade do Fluxo de Aprovação:**
    *   *Risco:* Bloqueio de processos vitais por falha na lógica de alçadas.
    *   *Mitigação:* Implementação de "Break-the-Glass" (acesso de emergência) com auditoria reforçada.
3.  **Escalabilidade do Monólito:**
    *   *Risco:* Degradação de performance com o crescimento da base de dados.
    *   *Mitigação:* Particionamento de tabelas (ex: logs de auditoria por mês) e uso de réplicas de leitura para relatórios.
4.  **Integração com Equipamentos (HL7/FHIR):**
    *   *Risco:* Incompatibilidade de protocolos com aparelhos de imagiologia.
    *   *Mitigação:* Camada de tradução (Adapter Pattern) isolada no módulo MDT.

---

### 5. Verificação de Conformidade (Checklist de Entrega)
*   [ ] O sistema impede a alta administrativa sem alta médica?
*   [ ] O sistema bloqueia a dispensação de fármacos sem prescrição ativa?
*   [ ] Existe rasto de auditoria para todas as ações de nível 1 e 2?
*   [ ] As alçadas de aprovação financeira estão parametrizadas conforme a hierarquia?
*   [ ] Os logs estão centralizados e em formato JSON?

---

## qa

_Modelo: gemini-3.5-flash_

# Plano de Garantia de Qualidade (QA): Sistema de Gestão Hospitalar Pública (HIS)

Este documento define a estratégia de testes unitários, de integração e de aceitação para o Sistema de Gestão Hospitalar Pública (HIS), garantindo a integridade transacional, a rastreabilidade total de acessos, a segregação de funções (SoD) e a estabilidade das operações assistenciais e administrativas.

---

## 1. Âmbito e Estratégia de Testes

A estratégia de validação cobre os fluxos críticos identificados na arquitetura e especificação funcional:
* **Fluxos Assistenciais:** Urgência (Triagem de Manchester, Paciente Desconhecido), Internamento/Bloco (ciclo de leitos, prescrição 24h) e MDT (Farmácia, Exames).
* **Fluxos Administrativos e Financeiros:** Alçadas de aprovação de compras, orçamentação e requisições de material.
* **Segurança e Conformidade:** Matriz RBAC/ABAC, auditoria imutável (*Audit Trail*) e mecanismo *Break-the-Glass*.

---

## 2. Plano de Testes Unitários

### 2.1. Foco e Cobertura
* **Validação de Máquinas de Estado:** Transições válidas e inválidas nos episódios clínicos (`AGUARDANDO_TRIAGEM` $\rightarrow$ `EM_TRIAGEM` $\rightarrow$ `EM_ATENDIMENTO`, etc.).
* **Regras de Negócio Isoladas:** Cálculo de prioridade na triagem, validação de doses de medicação, expiração de prescrições médicas (24h) e cálculo de alçadas de aprovação financeira.
* **Segurança (RBAC Local):** Verificação de anotações de segurança e guardas nos serviços de domínio.

### 2.2. Casos de Teste Unitários Principais

| ID | Domínio | Componente / Classe | Cenário de Teste | Resultado Esperado |
| :--- | :--- | :--- | :--- | :--- |
| **UT-01** | Urgência | `TriagemService` | Atribuir risco com sinais vitais críticos. | Definir prioridade "Vermelho" ou "Laranja" corretamente. |
| **UT-02** | Urgência | `EpisodioUrgenciaStateMachine` | Tentar passar episódio de `AGUARDANDO_TRIAGEM` diretamente para `ALTA`. | Lançar exceção `InvalidStateTransitionException`. |
| **UT-03** | Internamento | `PrescricaoMedica` | Validar prescrição com mais de 24 horas decorridas. | Método `isValida()` deve retornar `false`. |
| **UT-04** | Logística / ERP | `AprovacaoOrcamentariaService` | Processar compra acima da Alçada 1 sem parecer jurídico/auditoria. | Bloquear aprovação e exigir pareceres obrigatórios. |
| **UT-05** | MDT / Farmácia | `DispensacaoFisiologicaService` | Tentar dispensar psicotrópico sem prescrição médica associada. | Lançar exceção `PrescricaoAusenteException`. |

### 2.3. Comandos Concretos para Execução de Testes Unitários

* **Stack Java 21 / Spring Boot (Maven):**
  ```bash
  # Execução exclusiva de testes unitários (isolados de base de dados e mensageria)
  ./mvnw test -Dtest=*UnitTest -DfailIfNoTests=false
  ```

* **Stack Node.js / NestJS (Jest):**
  ```bash
  # Execução de testes unitários com relatório de cobertura
  npm run test:unit -- --coverage --testPathIgnorePatterns=integration
  ```

---

## 3. Plano de Testes de Integração

### 3.1. Foco e Cobertura
* **Persistência de Dados e Transacionalidade (PostgreSQL):** Garantir concorrência de acessos em alocação de leitos (bloqueio otimista/pessimista).
* **Publicação e Consumo de Eventos (RabbitMQ / Transactional Outbox):** Verificar emissão de eventos do domínio (ex.: `AltaMedicaRegistada` $\rightarrow$ evento enviado para `HigienizacaoLeito` e `AltaAdministrativa`).
* **Trilha de Auditoria (Audit Trail):** Confirmar se interceptadores/listeners persistem registos imutáveis com `utilizador_id`, `perfil_ativo`, `acao` e `timestamp`.
* **Mapeamento de APIs REST:** Validação de contratos REST, serialização JSONB e tratamento de exceções HTTP (400, 401, 403, 409, 500).

### 3.2. Casos de Teste de Integração Principais

| ID | Domínio / Componente | Cenário de Integração | Resultado Esperado |
| :--- | :--- | :--- | :--- |
| **IT-01** | `LeitoRepository` + PostgreSQL | Tentar alocar simultaneamente dois pacientes na mesma cama livre via concorrência. | Uma transação sucede; a segunda falha com erro de conflito (`409 Conflict` ou `OptimisticLockingFailureException`). |
| **IT-02** | `AltaMedica` $\rightarrow$ RabbitMQ | Registar alta médica via REST API. | Episódio atualizado na base de dados e mensagem `AltaMedicaEvent` entregue na fila de higienização de leitos. |
| **IT-03** | Interceptador de Auditoria | Atualizar ficha de paciente ou alterar prescrição. | Registo inserido na tabela `logs_auditoria` com `dados_anteriores` e `dados_novos`. |
| **IT-04** | Farmácia + Stock Setorial | Confirmar dispensação de item do stock central para a Urgência. | Baixa no stock central e subida no stock do setor numa transação atómica. |
| **IT-05** | Leito / Higienização | Tentar alocar paciente num leito com estado `AGUARDANDO_HIGIENIZACAO`. | API recusa alocação (`HTTP 422 Unprocessable Entity`). |

### 3.3. Comandos Concretos para Execução de Testes de Integração

* **Stack Java / Spring Boot (Testcontainers + PostgreSQL + RabbitMQ):**
  ```bash
  # Execução de testes de integração integrados com contentores temporários
  ./mvnw verify -P integration-tests -Dtest=*IT
  ```

* **Stack Node.js / NestJS (Jest + Docker Compose Test Environment):**
  ```bash
  # Levantar dependências de teste e executar suite de integração
  docker-compose -f docker-compose.test.yml up -d
  npm run test:e2e -- --detectOpenHandles
  docker-compose -f docker-compose.test.yml down -v
  ```

---

## 4. Plano de Testes de Aceitação / Critérios de Aceitação (Scrum Master)

Estes cenários validam se as histórias de utilizador cumprem os requisitos do negócio hospitalar e regras RBAC/ABAC.

### 4.1. Cenário 1: Entrada de Paciente Indocumentado / Emergência
* **Critério de Aceitação:** Permitir abertura de ficha provisória ("Paciente Desconhecido") para atendimento imediato, garantindo fusão posterior com o prontuário definitivo.
* **Passos de Validação:**
  1. Utilizador com perfil `Rececionista` cria episódio de urgência sem número de documento.
  2. Sistema gera identificador temporário único.
  3. Médico prescreve atendimento sob o id temporário.
  4. Utilizador `Rececionista` executa a funcionalidade "Unificar Prontuário" após identificação.
* **Resultado Esperado:** Histórico de atendimento, exames e prescrições do ID temporário passam a constar no histórico do prontuário definitivo.

### 4.2. Cenário 2: Segregação de Funções (SoD) na Cadeia de Medicamentos e Compras
* **Critério de Aceitação:** O utilizador que prescreve não pode dispensar no stock; o utilizador que solicita a compra não pode aprovar a ordem de pagamento.
* **Passos de Validação:**
  1. Utilizador com perfil `Médico` prescreve um fármaco.
  2. Tentar autenticar o mesmo `Médico` no endpoint de dispensação da Farmácia $\rightarrow$ **Bloqueado (`HTTP 403 Forbidden`)**.
  3. Utilizador com perfil `Compras` cria uma requisição de compra de grande porte (Alçada 2).
  4. Tentar aprovar a compra com o mesmo perfil `Compras` $\rightarrow$ **Bloqueado (`HTTP 403 Forbidden`)**.

### 4.3. Cenário 3: Mecanismo de Emergência "Break-the-Glass"
* **Critério de Aceitação:** Permitir acesso excecional a prontuários restritos na Urgência/UCI mediante justificativa obrigatória, acionando auditoria imediata.
* **Passos de Validação:**
  1. `Médico` tenta aceder a prontuário confidencial sem atribuição direta de leito.
  2. Sistema exige confirmação de ativação de *Break-the-Glass* e motivo detalhado (mínimo 20 caracteres).
  3. Acesso é concedido temporariamente.
* **Resultado Esperado:** Notificação/alerta enviado à Auditoria Interna e Comissão de Ética; registo imutável gravado em log de auditoria com flag `BREAK_THE_GLASS_ATIVADO`.

### 4.4. Cenário 4: Ciclo de Alta e Higienização de Leito
* **Critério de Aceitação:** O leito só pode ser libertado para novo internamento após registo de Alta Médica, Alta Administrativa e Higienização Terminal.
* **Passos de Validação:**
  1. `Médico` regista Alta Médica $\rightarrow$ Estado do leito muda para `AGUARDANDO_HIGIENIZACAO`.
  2. `Enfermeiro-Chefe` tenta alocar novo paciente $\rightarrow$ Sistema bloqueia a operação.
  3. `Serviços Gerais (Limpeza)` regista encerramento da higienização no sistema $\rightarrow$ Estado do leito muda para `LIVRE`.
  4. Alocação do novo paciente é permitida.

---

## 5. Procedimento de Reporte de Bugs e Falhas Pré-Produção

Qualquer desvio detetado durante a execução dos planos deve ser reportado antes do envio para produção utilizando a seguinte estrutura de reporte.

### 5.1. Matriz de Severidade de Bugs

| Severidade | Definição | Ação Necessária |
| :--- | :--- | :--- |
| **Bloqueador (P1)** | Riscos para a vida do paciente, perda de dados sensíveis, falha total de RBAC ou paragem de módulo crítico (Urgência/Bloco). | Bloqueia *deploy* para produção imediatamente. Resolução em < 4 horas. |
| **Crítico (P2)** | Falha em transições de estado, falha em integrações assíncronas ou violação parcial de regras de alçada financeira. | Bloqueia *deploy* para produção. Resolução em < 24 horas. |
| **Moderado (P3)** | Erro funcional com alternativa de contorno disponível ou inconsistência visual em formulários. | Pode ser corrigido na iteração seguinte caso haja aprovação do PO. |
| **Baixo (P4)** | Pequenos desvios de layout ou erros ortográficos em ecrãs operacionais. | Corrigido em fluxo normal de manutenção. |

### 5.2. Modelo de Relatório de Bug (Bug Report Template)

```markdown
### [BUG-ID] Título Claro e Resumido do Erro

* **Módulo Afetado:** [ex.: Urgência / Farmácia / Leitos]
* **Severidade:** [P1 - Bloqueador | P2 - Crítico | P3 - Moderado | P4 - Baixo]
* **Ambiente:** [Staging / QA]
* **Versão/Commit:** [ex.: v1.2.0-rc3 / commit sha]

#### Descrição do Problema
[Descrição clara e objetiva do comportamento incorreto observável]

#### Passos para Reproduzir
1. Autenticar com o perfil X...
2. Navegar até o menu Y...
3. Submeter o formulário Z com os valores...
4. Observar o erro...

#### Comportamento Esperado
[O que deveria acontecer segundo os requisitos/documentação]

#### Comportamento Observado
[O que realmente aconteceu, incluindo código HTTP ou mensagem de erro]

#### Evidências / Logs
- **Payload/Erro REST:** `HTTP 500 - NullPointerException em PrescricaoService.java:142`
- **Correlation-ID:** `req-9843a12f-41b2`
```

---

## 6. Critérios Globais de Conclusão (Definition of Done - QA)

Um incremento de software é considerado **aprovado pela Garantia de Qualidade (QA)** apenas quando:

1. **Testes Unitários:** Cobertura de código de regras de negócio $\ge 85\%$, com $100\%$ de aprovação na execução das suites unitárias.
2. **Testes de Integração:** $100\%$ das suítes de integração executadas com sucesso, cobrindo persistência relacional, concorrência e publicação de eventos.
3. **Critérios de Aceitação:** Todos os cenários descritos pelo Scrum Master/Product Owner validados sem falhas de severidade P1 ou P2.
4. **Auditoria e Segurança:** Verificação confirmada de registos no *Audit Trail* para todas as ações mutativas e ausência de atalhos de permissão (RBAC integralmente respeitado).
5. **Relatório de Erros Limpo:** Nenhum bug de severidade P1 (Bloqueador) ou P2 (Crítico) aberto no backlog da release.

---

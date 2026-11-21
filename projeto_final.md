# Fabrica de IA Autonoma - Relatorio Final

**Ideia:** Sistema de Gestão Hospitalar Pública (HIS)

## scrum_master

_Modelo: gemini-3.1-flash-lite_

Como Scrum Master, organizei o Backlog da **Versão 0.1 (MVP - Fundação Operacional)** do Sistema de Gestão Hospitalar (HIS). O foco desta versão é garantir a base de autenticação, o registo de pacientes e o fluxo crítico de triagem na urgência, respeitando a arquitetura modular definida.

---

### Sprint 1: Infraestrutura Base e Identidade (2 semanas)
*Objetivo: Estabelecer o ambiente de desenvolvimento, segurança e gestão de utilizadores.*

1. **US01 - Autenticação e RBAC (Controlo de Acesso)**
   - **Prioridade:** Alta
   - **Critérios de Aceitação:**
     - O utilizador deve autenticar-se via JWT.
     - O sistema deve validar permissões (RBAC) baseadas nos perfis (Médico, Enfermeiro, Admin, etc.).
     - Logs de auditoria devem registar cada tentativa de login (sucesso/falha).

2. **US02 - Registo de Unidades Organizacionais**
   - **Prioridade:** Média
   - **Critérios de Aceitação:**
     - CRUD de unidades (Urgência, UCI, Enfermarias, etc.).
     - Hierarquia de departamentos configurável.

---

### Sprint 2: Ciclo Assistencial de Urgência (3 semanas)
*Objetivo: Implementar o fluxo de entrada do paciente e triagem de risco.*

3. **US03 - Admissão de Paciente (Urgência)**
   - **Prioridade:** Alta
   - **Critérios de Aceitação:**
     - Registo de paciente com dados básicos ou "Paciente Desconhecido".
     - Geração de número de episódio único.
     - Validação: Não permitir dois episódios ativos para o mesmo paciente.

4. **US04 - Triagem de Manchester (Enfermagem)**
   - **Prioridade:** Alta
   - **Critérios de Aceitação:**
     - Registo de sinais vitais e queixa principal.
     - Atribuição automática de cor de risco (Triagem).
     - O sistema deve ordenar a fila de espera médica por prioridade de risco.

---

### Sprint 3: Gestão de Fluxo e Auditoria (3 semanas)
*Objetivo: Garantir a integridade dos dados e o acompanhamento do paciente.*

5. **US05 - Máquina de Estado do Episódio Clínico**
   - **Prioridade:** Alta
   - **Critérios de Aceitação:**
     - Transições obrigatórias: `ADMITIDO` -> `TRIAGEM` -> `AGUARDANDO_MEDICO` -> `EM_ATENDIMENTO`.
     - Bloqueio de transições inválidas (ex: não permitir `ALTA` sem registo de desfecho).

6. **US06 - Trilha de Auditoria (Audit Trail)**
   - **Prioridade:** Alta
   - **Critérios de Aceitação:**
     - Interceptador que grava em tabela imutável: `quem`, `o quê`, `quando` e `onde` (IP/Setor).
     - Visualização de histórico de alterações para utilizadores com perfil de Auditoria.

---

### Resumo do Backlog (Versão 0.1)

| ID | História de Utilizador | Prioridade | Sprint |
| :--- | :--- | :--- | :--- |
| US01 | Autenticação e RBAC | Crítica | 1 |
| US02 | Gestão de Unidades | Média | 1 |
| US03 | Admissão de Paciente | Crítica | 2 |
| US04 | Triagem de Manchester | Crítica | 2 |
| US05 | Máquina de Estados | Alta | 3 |
| US06 | Trilha de Auditoria | Alta | 3 |

---

### Notas do Scrum Master:
* **Critérios de Aceitação:** Todos os critérios acima são verificáveis através de testes de integração (Spring Boot/JUnit) e testes de interface (Angular/Cypress).
* **Comunicação:** As equipas de Backend e Frontend devem alinhar os contratos de API (Swagger/OpenAPI) antes do início de cada Sprint.
* **Qualidade:** Nenhuma funcionalidade será considerada "Done" sem o registo de auditoria correspondente e a validação do fluxo de estados.

---

## arquiteto

_Modelo: gemini-3.1-flash-lite_

Como Arquiteto de Software, apresento a proposta de arquitetura para o Sistema de Gestão Hospitalar (HIS), focada em modularidade, integridade transacional e escalabilidade, seguindo rigorosamente a stack recomendada.

---

### 1. Stack Tecnológica (Proporcional e Robusta)

Para garantir a manutenção preventiva e a análise crítica, a stack foi selecionada para equilibrar o rigor clínico com a agilidade operacional:

*   **Backend:** Java 21 + Spring Boot (Modular Monolith).
*   **Frontend:** Angular (TypeScript) para interfaces clínicas complexas.
*   **Banco de Dados Relacional (Core):** Supabase (PostgreSQL) para consistência ACID em prontuários, escalas e movimentos de stock.
*   **Banco de Dados NoSQL/Logs:** MongoDB Atlas para trilha de auditoria (Audit Trail) e logs de eventos.
*   **Cache/Mensageria:** Redis (Sessões/Painéis) + RabbitMQ (Eventos de domínio/Integrações).
*   **Observabilidade:** Prometheus + Grafana.

---

### 2. Arquitetura em Camadas (Modular Monolith)

A estrutura organiza-se em **Bounded Contexts** (Módulos) independentes dentro de um único deploy, facilitando a comunicação interna e a futura extração para microsserviços.

#### A. Camada de Apresentação (Frontend)
*   **Angular SPA:** Componentes reutilizáveis para formulários clínicos, dashboards de triagem (Manchester) e gestão de leitos.
*   **Comunicação:** API Gateway (Nginx) roteando requisições para os módulos específicos.

#### B. Camada de Aplicação (Backend - Spring Boot)
*   **Módulos (Bounded Contexts):**
    *   `Urgencia/Ambulatorio`: Gestão de episódios e triagem.
    *   `Internamento/Bloco`: Gestão de camas e escalas cirúrgicas.
    *   `MDT`: Integração com laboratório e farmácia.
    *   `ERP`: RH, Finanças e Compras.
    *   `Governacao`: Auditoria e Compliance.
*   **Padrão de Comunicação:** Eventos de domínio (ex: `AltaMedicaRegistada` dispara `HigienizacaoLeito`).

#### C. Camada de Persistência (Híbrida)
*   **Supabase (PostgreSQL):** Dados transacionais (pacientes, prescrições, escalas, stocks). Uso intensivo de *JSONB* para formulários clínicos dinâmicos.
*   **MongoDB Atlas:** Armazenamento de logs estruturados de auditoria (quem, quando, o quê) e logs de sistema, garantindo que o banco relacional não sofra degradação de performance por tabelas de auditoria gigantescas.

---

### 3. Limites e Regras de Segurança (RBAC/ABAC)

Para garantir a integridade e a segregação de funções (SoD):

1.  **Isolamento de Domínio:** O módulo de `Finanças` não acede diretamente a dados clínicos sensíveis (Prontuário), apenas a metadados para faturação.
2.  **Trilha de Auditoria:** Qualquer alteração em dados críticos (prescrições, movimentos de stock) é enviada via *Transactional Outbox* para o MongoDB, garantindo que a auditoria seja imutável.
3.  **Break-the-Glass:** Implementado como um *Interceptor* no Spring Security que, ao detetar acesso a dados restritos em emergência, dispara um evento assíncrono para a `Auditoria Interna` e `Comissão de Ética`.

---

### 4. Estratégia de Escalabilidade e Observabilidade

*   **Stateless:** A aplicação não mantém estado local; sessões são geridas via Redis.
*   **Jobs/Cron:** Rotinas agendadas (Spring Batch) para manutenção preventiva (ex: verificação de validade de medicamentos, alertas de stock mínimo).
*   **Monitoramento:** Logs em formato JSON centralizados, com `correlation_id` para rastrear o percurso de um paciente desde a triagem até à alta, permitindo identificar gargalos operacionais via Grafana.

---

### 5. Checklist de Implementação (Resumo)

| Componente | Tecnologia | Função Crítica |
| :--- | :--- | :--- |
| **Core Transacional** | PostgreSQL (Supabase) | ACID, integridade de leitos e escalas. |
| **Audit Trail** | MongoDB Atlas | Logs imutáveis de auditoria e conformidade. |
| **Orquestração** | Spring Boot | Máquinas de estado para fluxos clínicos. |
| **Mensageria** | RabbitMQ | Desacoplamento entre setores (ex: Farmácia/Enfermagem). |
| **Interface** | Angular | Formulários reativos e alta performance. |

Esta arquitetura garante que o sistema hospitalar seja resiliente, auditável e capaz de crescer conforme as necessidades da unidade hospitalar, mantendo a separação clara entre a lógica de negócio clínica e a gestão administrativa.

---

## programador

_Modelo: gemini-3.1-flash-lite_

Este plano de implementação organiza a construção do Sistema de Gestão Hospitalar (HIS) seguindo a arquitetura de **Monólito Modular** com foco em resiliência, auditoria e conformidade clínica.

---

### 1. Estrutura de Diretórios (Modular Monolith)
A estrutura reflete a separação por *Bounded Contexts* para facilitar a futura extração para microsserviços.

```text
/src
  /modules
    /urgencia          # Triagem, Fluxo de Manchester, Admissão
    /ambulatorio       # Agendamento, Consultas
    /internamento      # Gestão de Leitos, Bloco Operatório, UCI
    /mdt               # Laboratório, Imagiologia, Farmácia
    /administrativo    # RH, Financeiro, Compras, Logística
    /governanca        # Auditoria, Jurídico, Ética
  /shared
    /infrastructure    # Database, Redis, RabbitMQ, Logger
    /security          # RBAC/ABAC, JWT, Audit Trail
    /utils             # Validações, Formatação HL7/FHIR
```

---

### 2. Plano de Implementação (Fases)

#### Fase 1: Fundação e Segurança (Sprint 1-2)
*   **Setup:** Inicialização do projeto (NestJS/TypeScript ou Spring Boot).
*   **Core Security:** Implementação do middleware de **RBAC/ABAC** e do **Audit Trail Imutável** (interceptador que captura `user_id`, `action`, `payload_before`, `payload_after`).
*   **Database:** Configuração do PostgreSQL com particionamento para tabelas de logs e auditoria.

#### Fase 2: Ciclo Assistencial (Sprint 3-6)
*   **Módulo Urgência:** Implementação da Máquina de Estado do Paciente (`ADMITIDO` $\rightarrow$ `TRIAGEM` $\rightarrow$ `ATENDIMENTO`).
*   **Prontuário:** Estruturação de formulários clínicos dinâmicos utilizando `JSONB` no PostgreSQL.
*   **Integração MDT:** Criação de *endpoints* para pedidos de exames e retorno de laudos via mensageria (RabbitMQ).

#### Fase 3: Gestão e Logística (Sprint 7-10)
*   **Gestão de Leitos:** Implementação do fluxo de higienização (bloqueio de alocação até confirmação da limpeza).
*   **Workflow Financeiro:** Implementação do padrão *Outbox* para garantir que pedidos de compra e aprovações orçamentais sejam transacionais.
*   **Escalas:** Motor de validação de escalas de turnos (conflitos de horário e alçadas).

#### Fase 4: Observabilidade e BI (Sprint 11+)
*   **Monitoramento:** Integração Prometheus/Grafana para métricas de latência e saúde do sistema.
*   **Analytics:** Configuração do *Data Mart* (leitura) para o Apache Superset, garantindo que relatórios não afetem a performance do transacional.

---

### 3. Responsabilidades por Perfil (Matriz de Acesso)
A implementação deve validar estas regras via *decorators* ou *guards* no código:

| Perfil | Responsabilidade Técnica | Restrição Crítica |
| :--- | :--- | :--- |
| **Médico** | Escrita em Prontuário, Prescrição | Bloqueado: Gestão Financeira/RH |
| **Enfermeiro** | Triagem, Administração, Escalas | Bloqueado: Alta Médica, Compras |
| **Admin/Financeiro** | Compras, RH, Logística | Bloqueado: Prontuário Clínico |
| **Auditor** | Leitura de Logs de Auditoria | Bloqueado: Escrita/Edição |

---

### 4. Riscos Técnicos e Mitigação

1.  **Risco: Inconsistência em Transações Financeiras/Clínicas.**
    *   *Mitigação:* Uso rigoroso de transações ACID no PostgreSQL e padrão *Transactional Outbox* para comunicação entre módulos.
2.  **Risco: Performance em Consultas de Relatórios (BI).**
    *   *Mitigação:* Uso de réplicas de leitura e separação física entre o banco transacional e o *Data Mart*.
3.  **Risco: Falha na Auditoria (Audit Trail).**
    *   *Mitigação:* Implementação de *decorators* globais em todos os serviços de escrita, tornando a auditoria obrigatória por design (não opcional).
4.  **Risco: Indisponibilidade em Emergências.**
    *   *Mitigação:* Implementação do protocolo "Break-the-Glass" (acesso de emergência) com registo imediato e notificação de alta prioridade para a Auditoria Interna.

---

### 5. Checklist de Verificação (Definition of Done)
*   [ ] O log de auditoria capturou a alteração?
*   [ ] O utilizador tem permissão (RBAC) para esta ação específica?
*   [ ] A transação foi confirmada (ACID)?
*   [ ] O evento foi disparado para a fila (RabbitMQ/Outbox)?
*   [ ] O estado do paciente/leito foi atualizado corretamente na máquina de estados?

---

## qa

_Modelo: gemini-3.1-flash-lite_

Como responsável pela Garantia de Qualidade (QA), apresento o plano de testes estruturado para o Sistema de Gestão Hospitalar (HIS), focado na integridade transacional, conformidade com as regras de negócio (RBAC) e segurança clínica.

---

### 1. Testes Unitários (Nível de Componente)
**Objetivo:** Validar a lógica de negócio isolada (serviços, validadores e máquinas de estado).

*   **Comandos de Execução:** `mvn test` (Java/Spring) ou `npm test` (Node.js/Jest).
*   **Escopo:**
    *   **Máquinas de Estado:** Validar transições proibidas (ex: `ALTA_MEDICA` $\rightarrow$ `EM_TRIAGEM` deve falhar).
    *   **Regras de RBAC:** Testar se métodos protegidos lançam `AccessDeniedException` quando chamados por perfis sem autorização.
    *   **Cálculos Clínicos:** Validar algoritmos de triagem (Manchester) e dosagem de medicamentos.
*   **Critérios de Conclusão:** Cobertura de código mínima de 85% e 100% de sucesso nos testes de lógica de transição de estados.

---

### 2. Testes de Integração (Nível de Módulo)
**Objetivo:** Validar a comunicação entre módulos, persistência de dados e mensageria.

*   **Comandos de Execução:** `mvn verify` (com perfil `integration-test`) ou `docker-compose -f docker-compose.test.yml up --build`.
*   **Escopo:**
    *   **Persistência (PostgreSQL):** Validar transações ACID em alocação de leitos (evitar *race conditions* na ocupação).
    *   **Mensageria (RabbitMQ/Kafka):** Verificar se o evento `AltaMedicaRegistada` dispara corretamente as tarefas de `HigienizacaoLeito`.
    *   **Audit Trail:** Confirmar que cada operação de escrita gera um registo imutável na tabela de auditoria com os metadados exigidos (`user_id`, `ip`, `timestamp`).
*   **Critérios de Conclusão:** 100% de sucesso na comunicação entre serviços e integridade dos dados após falha simulada na rede (testes de resiliência).

---

### 3. Testes de Aceitação (Critérios do Scrum Master)
**Objetivo:** Validar se o sistema cumpre os requisitos funcionais e fluxos de trabalho do hospital.

*   **Comandos de Execução:** Execução de suítes de BDD (Cucumber/Cypress): `npx cypress run` ou `mvn verify -P acceptance-tests`.
*   **Fluxos Críticos de Validação:**
    1.  **Fluxo de Urgência:** Simular admissão de "Paciente Desconhecido" $\rightarrow$ Triagem $\rightarrow$ Prescrição $\rightarrow$ Alta.
    2.  **Fluxo de Compras (SoD):** Validar que o utilizador que solicita a compra **não consegue** aprovar o pagamento.
    3.  **Break-the-Glass:** Validar se o acesso a prontuário restrito em emergência gera o alerta obrigatório para a Auditoria Interna.
*   **Critérios de Conclusão:**
    *   Fluxos clínicos concluídos sem erros de bloqueio.
    *   Segregação de funções (SoD) validada: tentativas de acesso cruzado bloqueadas.
    *   Logs de auditoria gerados para 100% das ações sensíveis.

---

### 4. Relatório de Bugs e Falhas
**Procedimento de Reporte:**
Qualquer falha detetada deve ser reportada no sistema de gestão de *issues* (ex: Jira/GitHub Issues) contendo:
1.  **ID do Caso de Teste** e **Ambiente**.
2.  **Passos para reprodução** (com dados de entrada).
3.  **Resultado esperado vs. Resultado obtido**.
4.  **Nível de Severidade:**
    *   *Crítico:* Bloqueia o fluxo assistencial ou financeiro (ex: falha na prescrição, erro de stock).
    *   *Alto:* Funcionalidade essencial com *workaround* difícil.
    *   *Médio/Baixo:* Problemas de UI ou funções não essenciais.

**Nota:** Nenhuma *feature* será enviada para produção sem a evidência de sucesso nos testes de integração e a validação do *checklist* de conformidade (RBAC + Auditoria).

---

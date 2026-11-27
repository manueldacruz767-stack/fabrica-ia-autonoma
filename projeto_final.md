# Fabrica de IA Autonoma - Relatorio Final

**Ideia:** Sistema de Gestão Hospitalar Pública (HIS)

## scrum_master

_Modelo: gemini-3.1-flash-lite_

Como Scrum Master, organizei o backlog da **Versão 0.1 (MVP)** do Sistema de Gestão Hospitalar (HIS). O foco desta versão é garantir a base operacional: **Identificação do Paciente, Triagem de Urgência e Gestão de Leitos**, assegurando a rastreabilidade (Audit Trail) desde o primeiro dia.

---

### Sprint 1: Fundação e Identificação (Duração: 2 semanas)
*Foco: Infraestrutura base, segurança e admissão de pacientes.*

1. **US01 - Registo de Paciente (Admissão)**
   - **Prioridade:** Alta
   - **Critérios de Aceitação:**
     - Permitir registo de paciente com dados básicos (Nome, Data Nascimento, ID/NIF).
     - Permitir criação de "Paciente Desconhecido" para emergências.
     - O sistema deve gerar um ID único de prontuário.
     - Registo obrigatório de `utilizador_id` e `timestamp` na trilha de auditoria.

2. **US02 - Autenticação e RBAC (Controlo de Acesso)**
   - **Prioridade:** Alta
   - **Critérios de Aceitação:**
     - Implementar login com perfis: Rececionista, Médico, Enfermeiro.
     - Bloqueio de acesso a módulos não autorizados (ex: Rececionista não acede a prontuário clínico).
     - Validação de sessão via JWT/Redis.

---

### Sprint 2: Fluxo de Urgência e Triagem (Duração: 2 semanas)
*Foco: Jornada do paciente na Urgência.*

3. **US03 - Triagem de Manchester**
   - **Prioridade:** Alta
   - **Critérios de Aceitação:**
     - Enfermeiro deve registar sinais vitais e queixa principal.
     - Sistema deve atribuir cor de prioridade (Vermelho, Laranja, Amarelo, Verde, Azul).
     - Ordenação automática da fila de espera médica baseada na prioridade.

4. **US04 - Atendimento Médico (Prontuário)**
   - **Prioridade:** Alta
   - **Critérios de Aceitação:**
     - Médico deve conseguir visualizar o histórico da triagem.
     - Campo de texto livre para anamnese e hipótese diagnóstica.
     - Botão para "Encerrar Episódio" com desfecho (Alta, Internamento, Transferência).

---

### Sprint 3: Gestão de Internamento e Auditoria (Duração: 2 semanas)
*Foco: Gestão de recursos físicos e conformidade.*

5. **US05 - Gestão de Leitos**
   - **Prioridade:** Média
   - **Critérios de Aceitação:**
     - Visualização de mapa de leitos (Livre, Ocupado, Higienização).
     - Bloqueio de alocação em leitos com estado "Higienização".
     - Alerta automático para equipa de limpeza ao registar "Alta Médica".

6. **US06 - Trilha de Auditoria (Audit Trail)**
   - **Prioridade:** Alta
   - **Critérios de Aceitação:**
     - Toda alteração de estado clínico deve gerar um registo imutável (JSON).
     - O log deve conter: `utilizador_id`, `perfil`, `acao`, `dados_anteriores`, `dados_novos` e `ip_origem`.
     - Auditoria deve ser consultável por perfis com permissão de "Auditor".

---

### Resumo do Backlog (Versão 0.1)

| ID | Sprint | História de Utilizador | Prioridade |
| :--- | :--- | :--- | :--- |
| US01 | 1 | Registo de Paciente | Alta |
| US02 | 1 | Autenticação (RBAC) | Alta |
| US03 | 2 | Triagem de Manchester | Alta |
| US04 | 2 | Atendimento Médico | Alta |
| US05 | 3 | Gestão de Leitos | Média |
| US06 | 3 | Trilha de Auditoria | Alta |

---

### Notas do Scrum Master:
* **Critérios de Aceitação:** Todos os critérios acima são verificáveis através de testes funcionais (UI) ou testes de integração (API).
* **Comunicação:** As equipas de Backend (Java/Spring) e Frontend (Angular) devem alinhar os contratos de API (JSON) antes do início da Sprint 1 para garantir a fluidez da integração.
* **Próximos Passos:** Após a V0.1, o backlog da V0.2 focará em "MDT (Laboratório/Imagiologia)" e "Gestão de Stock/Farmácia".

---

## arquiteto

_Modelo: gemini-3.1-flash-lite_

Como Arquiteto de Software, apresento a proposta de arquitetura para o Sistema de Gestão Hospitalar (HIS), focada em modularidade, integridade transacional e escalabilidade, seguindo rigorosamente a stack recomendada.

---

### 1. Stack Tecnológica (Proporcional e Robusta)

*   **Backend:** Java 21 + Spring Boot (Modular Monolith).
*   **Frontend:** Angular (TypeScript) para interfaces complexas e formulários clínicos.
*   **Persistência Relacional:** **Supabase (PostgreSQL)** para dados transacionais (ACID), prontuários e auditoria.
*   **Persistência NoSQL/Logs:** **MongoDB Atlas** para logs de auditoria imutáveis, telemetria e documentos clínicos semiestruturados (JSONB).
*   **Cache/Filas:** Redis (Sessões e Painéis de Senhas) + RabbitMQ (Eventos de domínio e integrações).
*   **Infraestrutura:** Docker + Nginx (Load Balancer) + GitHub Actions (CI/CD).

---

### 2. Arquitetura em Camadas (Modular Monolith)

A arquitetura é organizada por **Bounded Contexts** (Módulos), garantindo que a lógica de negócio esteja isolada e desacoplada.

#### A. Camada de Apresentação (Frontend)
*   **Angular:** SPA com *Lazy Loading* por módulo (Urgência, Internamento, Administrativo).
*   **Comunicação:** API Gateway (Nginx) roteando requisições para o backend.

#### B. Camada de Aplicação e Domínio (Backend)
*   **Modular Monolith:** Cada módulo (ex: `urgencia`, `internamento`, `financeiro`) possui seu próprio pacote, regras de negócio e máquinas de estado.
*   **Event-Driven:** Utiliza eventos internos do Spring (`ApplicationEventPublisher`) ou RabbitMQ para comunicação assíncrona entre módulos (ex: `AltaMedicaRegistada` -> `HigienizacaoLeito`).
*   **Segurança:** Spring Security com RBAC/ABAC integrado ao Redis para validação de permissões em tempo real.

#### C. Camada de Persistência (Híbrida)
*   **PostgreSQL (Supabase):**
    *   Tabelas transacionais (Pacientes, Prescrições, Escalas).
    *   Particionamento para tabelas de alto volume (ex: `sinais_vitais`).
*   **MongoDB Atlas:**
    *   Armazenamento de logs de auditoria (trilha imutável).
    *   Documentos clínicos dinâmicos que não exigem esquema rígido.

---

### 3. Limites e Regras de Segurança (SoD)

Para garantir a integridade exigida no contexto de um Hospital Público:

1.  **Segregação de Funções (SoD):** A camada de serviço do backend implementa *Interceptors* que validam o perfil do utilizador (RBAC) antes de qualquer transação financeira ou clínica.
2.  **Audit Trail:** Qualquer alteração em dados sensíveis é interceptada e gravada no MongoDB com `correlation_id`, `user_id` e `timestamp`.
3.  **Break-the-Glass:** Endpoint específico com *middleware* de auditoria que permite acesso emergencial, disparando um alerta imediato para a Auditoria Interna.
4.  **Consistência:** O uso de transações distribuídas é evitado em favor do padrão **Transactional Outbox** no PostgreSQL, garantindo que eventos de negócio sejam disparados apenas se a transação for confirmada.

---

### 4. Diagrama de Fluxo de Dados (Resumo)

1.  **Entrada:** Profissional autentica via Angular.
2.  **Processamento:** Spring Boot valida a permissão (Redis) e executa a lógica (Máquina de Estado).
3.  **Persistência:**
    *   Dados críticos -> **PostgreSQL**.
    *   Eventos/Logs -> **MongoDB**.
4.  **Notificação:** RabbitMQ dispara alertas para outros módulos (ex: Limpeza/Manutenção).
5.  **Observabilidade:** Prometheus/Grafana monitoriza a saúde da API e latência das consultas ao banco.

Esta arquitetura permite que o sistema cresça de forma sustentável, mantendo a conformidade com as normas de um hospital público e garantindo alta disponibilidade para os serviços críticos.

---

## programador

_Modelo: gemini-3.1-flash-lite_

Este plano de implementação organiza o desenvolvimento do Sistema de Gestão Hospitalar (HIS) em fases lógicas, respeitando a arquitetura de **Monólito Modular** e as regras de **Segregação de Funções (SoD)**.

---

### 1. Estrutura de Diretórios (Modular Monolith)
A estrutura deve garantir o desacoplamento por domínios (Bounded Contexts):

```text
/src
  /modules
    /urgencia        # Fluxo de Triagem e Emergência
    /ambulatorio     # Consultas e Agendamentos
    /internamento    # Gestão de Leitos, Bloco e UCI
    /mdt             # Laboratório, Farmácia e Imagiologia
    /erp             # RH, Finanças, Compras e Logística
    /governance      # Auditoria, Jurídico e Ética
  /shared            # Kernel: Auth, Logging, EventBus, AuditTrail
  /infrastructure    # Configuração DB, Redis, RabbitMQ
```

---

### 2. Plano de Implementação (Fases)

#### Fase 1: Fundação e Governação (Core)
* **Objetivo:** Estabelecer a infraestrutura de segurança e auditoria.
* **Tarefas:**
    1. Implementar RBAC/ABAC (Middleware de autorização).
    2. Criar o serviço de `AuditTrail` (Intercetores para registo imutável de ações).
    3. Configurar o `EventBus` (RabbitMQ) para comunicação entre módulos.
* **Risco:** Falha na trilha de auditoria compromete a conformidade legal.

#### Fase 2: Ciclo Assistencial (Core Clínico)
* **Objetivo:** Operacionalizar a jornada do paciente.
* **Tarefas:**
    1. **Módulo Urgência:** Máquina de estados para triagem (Manchester).
    2. **Módulo Internamento:** Gestão de leitos e estado de higienização.
    3. **Prontuário:** Estrutura de dados dinâmica (JSONB) para evolução clínica.
* **Risco:** Concorrência na alocação de leitos (resolver com transações ACID no PostgreSQL).

#### Fase 3: Ciclo de Suporte (ERP Hospitalar)
* **Objetivo:** Gestão de recursos e aprovações.
* **Tarefas:**
    1. **Workflow de Compras:** Implementar a lógica de alçadas (Direção Administrativa vs. Direção Geral).
    2. **Integração Farmácia/Logística:** Baixa automática de stock via eventos de prescrição médica.
* **Risco:** Quebra na segregação de funções (SoD). Garantir que quem solicita não aprova.

---

### 3. Matriz de Responsabilidades Técnicas

| Módulo | Responsável Técnico | Dependência Principal |
| :--- | :--- | :--- |
| **Auth/Audit** | Arquiteto de Software | PostgreSQL (Audit Logs) |
| **Clínico** | Dev Backend (Python/FastAPI) | Redis (Cache de Permissões) |
| **ERP/Financeiro** | Dev Backend (Node.js/NestJS) | RabbitMQ (Eventos de Aprovação) |
| **Frontend** | Dev Frontend (Angular) | API Gateway |

---

### 4. Riscos Técnicos e Mitigação

1. **Integridade de Dados (ACID):**
    * *Risco:* Inconsistência em alocação de leitos ou stock.
    * *Mitigação:* Uso estrito de transações PostgreSQL e bloqueios otimistas (`versioning` em tabelas críticas).

2. **Performance em Consultas Pesadas:**
    * *Risco:* Relatórios de BI impactando o atendimento clínico.
    * *Mitigação:* Implementar **CQRS** (Command Query Responsibility Segregation) com réplica de leitura para o Data Mart analítico.

3. **Disponibilidade (Break-the-Glass):**
    * *Risco:* Bloqueio de acesso em emergências.
    * *Mitigação:* Implementar endpoint de emergência com log de auditoria forçado e notificação imediata à Auditoria Interna.

4. **Escalabilidade:**
    * *Risco:* Sobrecarga no monólito.
    * *Mitigação:* Desenhar módulos para serem "extraíveis". Manter a API *stateless* (JWT + Redis) desde o primeiro dia.

---

### 5. Checklist de Verificação (Definition of Done)
* [ ] **Audit Trail:** Cada alteração em dados sensíveis gera um log com `user_id`, `timestamp` e `ip`.
* [ ] **SoD:** O sistema impede que o mesmo utilizador inicie e aprove o mesmo processo de compra.
* [ ] **Observabilidade:** Logs estruturados em JSON e métricas de latência disponíveis no Grafana.
* [ ] **Contingência:** O sistema permite acesso de emergência com registo de justificativa.

---

## qa

_Modelo: gemini-3.1-flash-lite_

Como responsável pela Garantia de Qualidade (QA), apresento o plano de testes estruturado para o Sistema de Gestão Hospitalar (HIS), focado na integridade transacional e na conformidade com as regras de negócio definidas.

---

### 1. Plano de Testes Unitários (Backend - Spring Boot/Node.js)
**Objetivo:** Validar a lógica de negócio isolada, especialmente as Máquinas de Estado e regras de alçada.

*   **Comandos de Execução:**
    *   `mvn test` (Java) ou `npm run test` (Node.js).
*   **Escopo:**
    *   **Máquinas de Estado:** Testar transições (ex: `AGUARDANDO_TRIAGEM` -> `EM_ATENDIMENTO`). Validar que estados inválidos (ex: `ALTA_MEDICA` -> `EM_TRIAGEM`) lancem exceções.
    *   **Regras de Alçada:** Validar se o motor de aprovação bloqueia compras sem dotação orçamental ou sem parecer jurídico (quando valor > X).
    *   **Cálculos:** Validar lógica de triagem (Manchester) e aprazamento de medicação.
*   **Critério de Conclusão:** 100% de sucesso nos testes unitários e cobertura de código (Code Coverage) superior a 85%.

---

### 2. Plano de Testes de Integração
**Objetivo:** Validar a comunicação entre módulos (Bounded Contexts) e a persistência de dados.

*   **Comandos de Execução:**
    *   `mvn verify` (com perfis de teste integrados ao Testcontainers/PostgreSQL).
*   **Escopo:**
    *   **Fluxo de Eventos:** Validar se o evento `AltaMedicaRegistada` dispara corretamente a notificação para o módulo de `HigienizacaoLeito` via RabbitMQ/Kafka.
    *   **Integridade ACID:** Simular concorrência na alocação de leitos para garantir que dois pacientes não ocupem a mesma cama simultaneamente.
    *   **Trilha de Auditoria:** Verificar se cada operação de escrita (POST/PUT/DELETE) gera um registo imutável na tabela de `AuditTrail` com os dados `antes/depois`.
*   **Critério de Conclusão:** Sucesso na comunicação assíncrona entre módulos e integridade dos dados após rollback de transações complexas.

---

### 3. Plano de Testes de Aceitação (UAT)
**Objetivo:** Validar se o sistema cumpre os critérios do Scrum Master e as necessidades dos stakeholders hospitalares.

*   **Cenários de Teste:**
    1.  **Break-the-Glass:** Médico acede a prontuário restrito em emergência. *Critério:* Sistema deve permitir acesso e disparar alerta imediato para Auditoria.
    2.  **Segregação de Funções (SoD):** Tentar aprovar um pagamento sendo o mesmo utilizador que solicitou a compra. *Critério:* Sistema deve bloquear a ação.
    3.  **Fluxo de Alta:** Tentar dar alta administrativa sem alta médica. *Critério:* Sistema deve impedir a conclusão do processo.
    4.  **Usabilidade Clínica:** Realizar uma prescrição completa em menos de 5 cliques (conforme diretriz de UI/UX).
*   **Critério de Conclusão:** Aprovação formal do Scrum Master e dos representantes das Direções Executivas (Clínica, Enfermagem e Administrativa).

---

### 4. Protocolo de Reporte de Bugs
Qualquer falha detetada deve ser reportada seguindo o padrão:

1.  **ID do Bug:** [HIS-XXX]
2.  **Severidade:** (Crítica/Alta/Média/Baixa)
3.  **Descrição:** O que ocorreu vs. O que era esperado.
4.  **Passos para Reprodução:** Lista numerada.
5.  **Evidência:** Logs JSON (correlation_id) ou print da interface.
6.  **Status:** (Aberto/Em Correção/Pronto para QA).

---

### 5. Critérios de Aceitação Gerais
*   **Segurança:** Nenhum utilizador deve aceder a dados fora do seu perfil (RBAC validado).
*   **Performance:** Tempo de resposta da API < 200ms para operações críticas (triagem/prescrição).
*   **Observabilidade:** Todos os erros 5xx devem estar centralizados no Grafana com logs estruturados.
*   **Conformidade:** A trilha de auditoria deve ser imutável e conter o `IP_Origem` e `Timestamp`.

---

# Fabrica de IA Autonoma - Relatorio Final

**Ideia:** Sistema de Gestão Hospitalar Pública (HIS)

## scrum_master

_Modelo: gemini-3.1-flash-lite_

Como Scrum Master, organizei o backlog da **Versão 0.1 (MVP)** do Sistema de Gestão Hospitalar (HIS). O foco desta versão é garantir a base de autenticação, o fluxo de admissão de pacientes na urgência e a gestão de leitos, pilares críticos para a operação hospitalar.

---

### Sprint 1: Infraestrutura Base e Identidade (Duração: 2 semanas)
*Objetivo: Estabelecer o ambiente de desenvolvimento, segurança e gestão de utilizadores.*

1. **US01 - Autenticação e RBAC (Alta Prioridade)**
   - **História:** Como administrador, quero gerir perfis de utilizadores para que cada profissional aceda apenas às funcionalidades do seu cargo.
   - **Critérios de Aceitação:**
     - Login com encriptação de password (BCrypt).
     - Implementação de RBAC (Role-Based Access Control) para perfis: Médico, Enfermeiro, Rececionista, Direção.
     - Logout funcional e expiração de sessão via Redis.

2. **US02 - Configuração de Auditoria (Alta Prioridade)**
   - **História:** Como auditor, quero que todas as ações críticas sejam registadas para garantir a conformidade legal.
   - **Critérios de Aceitação:**
     - Interceptor de logs que grava: `user_id`, `action`, `timestamp`, `ip` e `entity_id`.
     - Logs estruturados em JSON para fácil integração com ELK/Grafana.

---

### Sprint 2: Fluxo de Urgência / Emergência (Duração: 3 semanas)
*Objetivo: Permitir o atendimento de pacientes desde a receção até à triagem.*

3. **US03 - Admissão de Pacientes (Alta Prioridade)**
   - **História:** Como rececionista, quero admitir pacientes na urgência para iniciar o episódio clínico.
   - **Critérios de Aceitação:**
     - Registo de paciente com dados básicos (Nome, ID, Data Nascimento).
     - Funcionalidade "Paciente Desconhecido" para casos críticos.
     - Geração de número de episódio único.

4. **US04 - Triagem de Manchester (Alta Prioridade)**
   - **História:** Como enfermeiro, quero classificar o risco do paciente para definir a prioridade de atendimento médico.
   - **Critérios de Aceitação:**
     - Formulário de sinais vitais e queixa principal.
     - Atribuição automática de cor de prioridade (Manchester).
     - Atualização do estado do episódio para `AGUARDANDO_MEDICO`.

---

### Sprint 3: Internamento e Gestão de Leitos (Duração: 3 semanas)
*Objetivo: Controlar a ocupação hospitalar e garantir a higienização.*

5. **US05 - Gestão de Leitos (Média Prioridade)**
   - **História:** Como enfermeiro-chefe, quero alocar um paciente a um leito para organizar o internamento.
   - **Critérios de Aceitação:**
     - Visualização do mapa de leitos (Livre, Ocupado, Higienização).
     - Bloqueio de alocação em leitos com estado `AGUARDANDO_HIGIENIZACAO`.
     - Atualização automática de estado do leito ao dar alta.

6. **US06 - Alta Médica e Administrativa (Alta Prioridade)**
   - **História:** Como médico, quero registar a alta clínica para libertar o paciente e o leito.
   - **Critérios de Aceitação:**
     - Validação: Só permite alta se houver sumário clínico preenchido.
     - Disparo de evento `AltaMedicaRegistada` para o módulo de `HigienizacaoLeito`.
     - Bloqueio de novas prescrições após a alta.

---

### Resumo do Backlog (Versão 0.1)

| ID | História | Prioridade | Sprint |
| :--- | :--- | :--- | :--- |
| US01 | Autenticação e RBAC | Crítica | 1 |
| US02 | Trilha de Auditoria | Crítica | 1 |
| US03 | Admissão de Pacientes | Alta | 2 |
| US04 | Triagem de Risco | Alta | 2 |
| US05 | Gestão de Leitos | Média | 3 |
| US06 | Fluxo de Alta | Alta | 3 |

**Notas do Scrum Master:**
- **Comunicação:** As equipas de Backend (Java/Spring) e Frontend (Angular) devem alinhar os contratos de API (Swagger/OpenAPI) antes de iniciar a Sprint 2.
- **Qualidade:** Nenhum critério de aceitação será dado como concluído sem a passagem nos testes unitários e de integração automatizados.
- **Riscos:** A integração com equipamentos de sinais vitais (IoT) foi movida para a Versão 0.2 para garantir a estabilidade do fluxo de dados manual nesta fase.

---

## arquiteto

_Modelo: gemini-3.1-flash-lite_

Como Arquiteto de Software, apresento a proposta de arquitetura para o Sistema de Gestão Hospitalar (HIS), focada em modularidade, resiliência e conformidade com as exigências de um hospital público.

---

### 1. Stack Tecnológica Recomendada
A escolha prioriza a robustez do ecossistema Java e a flexibilidade do Frontend moderno, garantindo escalabilidade e facilidade de manutenção.

*   **Backend:** Java 21 + Spring Boot 3.x (Arquitetura Modular Monolith).
*   **Frontend:** Angular 17+ (Ideal para formulários complexos e tipagem forte).
*   **Banco de Dados Principal:** **Supabase (PostgreSQL)** para dados transacionais (ACID), auditoria e gestão de utilizadores.
*   **Banco de Dados NoSQL/Logs:** **MongoDB Atlas** para logs de auditoria imutáveis, sinais vitais e documentos clínicos não estruturados (JSONB).
*   **Cache/Mensageria:** Redis (Sessões/Dashboards) + RabbitMQ (Eventos de domínio/Integração).
*   **Infraestrutura:** Docker + Kubernetes (K8s) para orquestração.

---

### 2. Arquitetura em Camadas (Modular Monolith)

A estrutura é organizada por **Bounded Contexts** (Domínios), garantindo que a lógica de negócio de cada setor seja isolada, embora partilhem o mesmo *runtime*.

#### A. Camada de Apresentação (Frontend)
*   **SPA (Single Page Application):** Angular com *Lazy Loading* por módulo (ex: Módulo de Urgência, Módulo Administrativo).
*   **UI Kit:** Componentes reutilizáveis focados em acessibilidade e alta performance (ex: tabelas de triagem, formulários de prontuário).

#### B. Camada de Aplicação (API Gateway / BFF)
*   **API Gateway:** Ponto único de entrada (Nginx ou Spring Cloud Gateway) para autenticação (JWT) e *Rate Limiting*.
*   **Orquestração:** Gestão de permissões (RBAC/ABAC) integrada ao Supabase Auth.

#### C. Camada de Domínio (Backend - Spring Boot)
*   **Módulos de Negócio:**
    *   `Core-Clinico`: Urgência, Internamento, Bloco.
    *   `Core-Suporte`: Logística, Farmácia, Manutenção.
    *   `Core-Gestao`: RH, Financeiro, Auditoria.
*   **Padrão de Comunicação:** Eventos de domínio (ex: `AltaMedicaRegistada` dispara `HigienizacaoLeito`).

#### D. Camada de Persistência (Híbrida)
*   **PostgreSQL (Supabase):** Tabelas relacionais (Pacientes, Médicos, Escalas, Prescrições, Faturas).
*   **MongoDB:** Logs de auditoria (trilha de acesso), telemetria de equipamentos e prontuários dinâmicos.

---

### 3. Limites e Regras de Segurança

Para garantir a integridade do sistema hospitalar, definimos os seguintes limites:

1.  **Segregação de Funções (SoD):** O código de negócio deve validar que o `User_ID` que solicita uma compra não é o mesmo que a aprova (verificação via *Interceptor* no Spring Security).
2.  **Audit Trail:** Toda alteração em dados sensíveis (prescrições, prontuários, finanças) é escrita simultaneamente no PostgreSQL (estado atual) e no MongoDB (histórico imutável de auditoria).
3.  **Contingência "Break-the-Glass":** Endpoint específico que permite acesso a dados restritos em emergências, disparando um evento assíncrono para a Auditoria Interna via RabbitMQ.
4.  **Isolamento de Leitura:** Relatórios de BI (Apache Superset) conectam-se apenas a uma **Réplica de Leitura** do PostgreSQL, garantindo que consultas pesadas não afetem a performance do atendimento clínico.

---

### 4. Checklist de Implementação

| Camada | Componente | Responsabilidade |
| :--- | :--- | :--- |
| **Interface** | Angular | UX Clínica, formulários reativos, dashboards. |
| **Segurança** | Spring Security | RBAC/ABAC, JWT, Auditoria de Acessos. |
| **Negócio** | Spring Boot | Máquinas de estado (fluxos de paciente/financeiro). |
| **Dados** | PostgreSQL | Consistência ACID, transações financeiras/clínicas. |
| **Logs/Docs** | MongoDB | Auditoria imutável, formulários clínicos dinâmicos. |
| **Integração** | RabbitMQ | Eventos assíncronos (ex: Alerta de rutura de stock). |

Esta arquitetura garante que o hospital tenha um sistema estável hoje, com a capacidade de extrair módulos para microsserviços individuais no futuro, caso a carga de um departamento específico (ex: Urgência) exija escalabilidade isolada.

---

## programador

_Modelo: gemini-3.1-flash-lite_

Este plano de implementação organiza o desenvolvimento do Sistema de Gestão Hospitalar (HIS) numa abordagem de **Monólito Modular**, garantindo a conformidade com as regras de negócio e a segregação de funções (SoD) exigidas.

---

### 1. Estrutura de Diretórios (Modular Monolith)
A estrutura segue o padrão de domínios (Bounded Contexts) para garantir desacoplamento lógico:

```text
/src
  /modules
    /urgencia       # Triagem, Admissão, Fluxo de Paciente
    /internamento   # Gestão de Leitos, Prescrição, Bloco Operatório
    /mdt            # Laboratório, Imagiologia, Farmácia
    /administrativo # RH, Financeiro, Compras, Logística
    /governanca     # Auditoria, Pareceres Jurídicos, Dashboards
  /shared           # Kernel: Auth, Logging, EventBus, AuditTrail
  /infrastructure   # Configuração DB, Redis, RabbitMQ
```

---

### 2. Plano de Implementação (Fases)

#### Fase 1: Fundação e Segurança (Core)
*   **Ficheiros:** `auth.service.ts`, `audit.interceptor.ts`, `rbac.guard.ts`.
*   **Objetivo:** Implementar o sistema de autenticação (JWT) e o middleware de auditoria imutável.
*   **Regra:** Toda requisição deve injetar `user_id`, `perfil_ativo` e `unidade_hospitalar` no contexto de execução.

#### Fase 2: Ciclo Assistencial (Core Clínico)
*   **Ficheiros:** `patient.entity.ts`, `triage.service.ts`, `prescription.service.ts`.
*   **Objetivo:** Implementar a jornada do paciente: Admissão $\rightarrow$ Triagem $\rightarrow$ Prescrição.
*   **Regra:** Implementar a Máquina de Estado para o `EpisodioClinico`. Bloquear prescrições sem validação de médico ativo.

#### Fase 3: Logística e Suporte (Core de Apoio)
*   **Ficheiros:** `inventory.service.ts`, `procurement.workflow.ts`.
*   **Objetivo:** Fluxo de requisição de materiais e medicamentos.
*   **Regra:** Aplicar a Segregação de Funções (SoD). O utilizador que solicita não pode ser o que aprova a compra.

#### Fase 4: Governação e Observabilidade
*   **Ficheiros:** `audit.log.repository.ts`, `health.check.ts`.
*   **Objetivo:** Dashboards de BI (Superset) e trilha de auditoria para conformidade legal.

---

### 3. Responsabilidades por Camada (Stack)

| Camada | Responsabilidade | Tecnologia |
| :--- | :--- | :--- |
| **API/Backend** | Regras de negócio, Máquinas de Estado, SoD | Node.js (Fastify/NestJS) |
| **Persistência** | Integridade ACID, Particionamento de logs | PostgreSQL |
| **Mensageria** | Eventos de domínio (ex: `AltaRegistada`) | RabbitMQ |
| **Frontend** | Dashboards, Formulários, Atalhos | Angular (TypeScript) |

---

### 4. Riscos Técnicos e Mitigação

1.  **Risco: Concorrência na Alocação de Leitos**
    *   *Mitigação:* Utilizar transações `SERIALIZABLE` no PostgreSQL e bloqueio otimista (versionamento de registo) para evitar que dois pacientes sejam alocados na mesma cama.
2.  **Risco: Falha na Auditoria (Audit Trail)**
    *   *Mitigação:* Implementar um padrão de *Transactional Outbox*. O registo de auditoria deve ser gravado na mesma transação que a alteração do dado clínico.
3.  **Risco: Gargalo de Performance em Consultas Complexas**
    *   *Mitigação:* Utilizar uma **Réplica de Leitura** para relatórios de BI e estatísticas, isolando o tráfego transacional do analítico.
4.  **Risco: Acesso Indevido (Privilégios)**
    *   *Mitigação:* Implementar **ABAC (Attribute-Based Access Control)** sobre o RBAC. O acesso a dados clínicos deve validar não apenas o perfil, mas também a relação direta do médico/enfermeiro com o paciente ou setor.

---

### 5. Checklist de Verificação (Definition of Done)
*   [ ] O log de auditoria captura `dados_anteriores` e `dados_novos`?
*   [ ] O fluxo de "Break-the-Glass" dispara alerta para a Auditoria Interna?
*   [ ] A segregação de funções impede que o mesmo utilizador aprove e execute uma compra?
*   [ ] O sistema impede a alta administrativa sem a respetiva alta clínica?
*   [ ] Todos os serviços estão stateless e delegam sessão ao Redis?

---

## qa

_Modelo: gemini-3.1-flash-lite_

Como Agente de Garantia de Qualidade (QA), apresento o plano de testes estruturado para o Sistema de Gestão Hospitalar (HIS), focado na integridade, conformidade e segurança exigidas pelo contexto hospitalar.

---

### 1. Testes Unitários (Nível de Componente)
**Objetivo:** Validar a lógica de negócio isolada (especialmente Máquinas de Estado e Regras de Negócio).

*   **Comandos/Ações:**
    *   Executar `mvn test` (Java/Spring) ou `npm run test` (NestJS) com cobertura mínima de 80%.
    *   Validar transições de estados (ex: `AGUARDANDO_TRIAGEM` -> `EM_ATENDIMENTO`).
    *   Validar cálculos de dosagem e regras de validação de prescrição.
*   **Critérios de Conclusão:**
    *   100% de sucesso nos testes de lógica de transição de estados.
    *   Zero falhas em testes de regras de validação de formulários clínicos.

### 2. Testes de Integração (Nível de Módulo)
**Objetivo:** Validar a comunicação entre os domínios (Bounded Contexts) e a persistência.

*   **Comandos/Ações:**
    *   **Fluxo de Stock:** Simular `RequisiçãoInterna` -> `VerificaçãoStock` -> `BaixaFarmácia`.
    *   **Fluxo de Auditoria:** Validar se cada ação crítica (ex: `AltaMedica`) gera o registo na tabela de auditoria com `correlation_id`.
    *   **Fluxo de Mensageria:** Verificar se o evento `AltaMedicaRegistada` dispara a notificação para `HigienizacaoLeito` via RabbitMQ.
*   **Critérios de Conclusão:**
    *   Consistência ACID verificada no PostgreSQL em transações de alocação de leitos.
    *   Confirmação de que eventos assíncronos são processados sem perda de mensagens.

### 3. Testes de Aceitação (Critérios do Scrum Master)
**Objetivo:** Validar se o sistema cumpre a jornada do utilizador e as regras de segurança (RBAC/ABAC).

*   **Comandos/Ações:**
    *   **Teste de Segregação de Funções (SoD):** Tentar realizar uma compra de alto valor com perfil de `Médico` (deve ser bloqueado).
    *   **Teste de "Break-the-Glass":** Realizar acesso a prontuário restrito com perfil de `Médico` em urgência e validar se o log de auditoria foi gerado com a justificativa.
    *   **Teste de Fluxo Clínico:** Executar a jornada completa: `Admissão` -> `Triagem` -> `Prescrição` -> `Alta`.
*   **Critérios de Conclusão:**
    *   O sistema bloqueia estritamente ações fora do perfil (RBAC).
    *   A trilha de auditoria é imutável e contém todos os metadados exigidos (ID, Timestamp, IP).
    *   O fluxo de "Break-the-Glass" dispara alerta automático para a Auditoria Interna.

---

### 4. Checklist de Reporte de Bugs
Qualquer falha detetada deve ser reportada seguindo o padrão:
1.  **Título:** [Módulo] - Descrição curta do erro.
2.  **Passos para Reproduzir:** Lista numerada.
3.  **Resultado Esperado:** O que deveria ocorrer segundo a especificação.
4.  **Resultado Obtido:** O que ocorreu.
5.  **Severidade:** (Crítica/Alta/Média/Baixa). *Nota: Falhas em fluxos assistenciais ou de auditoria são sempre "Críticas".*

---

### 5. Estratégia de Observabilidade (QA Proativo)
*   **Monitorização:** Validar se os logs estruturados (JSON) contêm o `correlation_id` em todos os ambientes.
*   **Healthchecks:** Verificar se o endpoint `/health` retorna status 200 para o PostgreSQL, Redis e RabbitMQ antes de qualquer deploy.

**Nota:** Este plano deve ser executado em ambiente de *Staging* espelhado (Docker Compose) antes de qualquer aprovação para produção.

---

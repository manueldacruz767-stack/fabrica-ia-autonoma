# Fabrica de IA Autonoma - Relatorio Final

**Ideia:** Sistema de Gestão Hospitalar Pública (HIS)

## scrum_master

_Modelo: gemini-3.1-flash-lite_

Como Scrum Master, organizei o Backlog da **Versão 0.1 (MVP - Fundação Operacional)** do Sistema de Gestão Hospitalar (HIS). O foco desta versão é garantir a base de autenticação, o fluxo de admissão de pacientes e a infraestrutura de auditoria, essenciais para a operação clínica e conformidade legal.

---

### Sprint 1: Fundação, Segurança e Identidade
**Objetivo:** Estabelecer o ambiente de desenvolvimento, autenticação RBAC e gestão de utilizadores.

*   **US01: Autenticação e Autorização (RBAC)**
    *   *Prioridade:* Alta
    *   *Critérios de Aceitação:* O sistema deve permitir login via JWT; o acesso deve ser bloqueado por perfil (Médico, Enfermeiro, Admin); tentativas de acesso a funcionalidades não autorizadas devem retornar erro 403.
*   **US02: Gestão de Utilizadores e Unidades Organizacionais**
    *   *Prioridade:* Alta
    *   *Critérios de Aceitação:* CRUD de utilizadores vinculado a um departamento/unidade (ex: Urgência, Farmácia); registo de perfil de acesso (RBAC).

---

### Sprint 2: Ciclo Assistencial - Admissão e Triagem
**Objetivo:** Permitir a entrada do paciente no sistema e a classificação de risco.

*   **US03: Admissão de Paciente (Urgência)**
    *   *Prioridade:* Alta
    *   *Critérios de Aceitação:* Criar ficha de episódio de urgência; permitir registo de "Paciente Desconhecido" para casos críticos; gerar `ID_Episodio` único.
*   **US04: Triagem de Manchester (Enfermagem)**
    *   *Prioridade:* Alta
    *   *Critérios de Aceitação:* Registo de sinais vitais e queixa principal; atribuição automática de cor de risco; o sistema deve listar pacientes na fila de espera ordenados por prioridade.

---

### Sprint 3: Auditoria e Integridade (Core Técnico)
**Objetivo:** Garantir a imutabilidade dos dados clínicos e logs de sistema.

*   **US05: Trilha de Auditoria (Audit Trail)**
    *   *Prioridade:* Alta
    *   *Critérios de Aceitação:* Toda alteração em dados de prontuário deve registar: `utilizador_id`, `timestamp`, `acao`, `dados_anteriores` e `dados_novos` numa tabela imutável.
*   **US06: Máquina de Estados do Episódio**
    *   *Prioridade:* Média
    *   *Critérios de Aceitação:* O sistema deve impedir transições inválidas (ex: `AGUARDANDO_TRIAGEM` -> `ALTA_MEDICA` sem passar por `EM_ATENDIMENTO`).

---

### Sprint 4: Prescrição e MDT (Mínimo Viável)
**Objetivo:** Permitir que o médico prescreva e o MDT valide.

*   **US07: Prescrição Médica Simples**
    *   *Prioridade:* Alta
    *   *Critérios de Aceitação:* Médico deve conseguir prescrever medicação associada a um episódio; a prescrição deve exigir assinatura digital (token); bloqueio de edição após 24h.
*   **US08: Visualização de Resultados de Exames (MDT)**
    *   *Prioridade:* Média
    *   *Critérios de Aceitação:* Técnico de MDT deve conseguir anexar laudo técnico a um pedido de exame; médico deve receber notificação de "Resultado Disponível".

---

### Resumo do Backlog (Versão 0.1)

| ID | História de Utilizador | Prioridade | Sprint |
| :--- | :--- | :--- | :--- |
| US01 | Autenticação e RBAC | Alta | 1 |
| US02 | Gestão de Utilizadores | Alta | 1 |
| US03 | Admissão de Paciente | Alta | 2 |
| US04 | Triagem de Risco | Alta | 2 |
| US05 | Trilha de Auditoria | Alta | 3 |
| US06 | Máquina de Estados | Média | 3 |
| US07 | Prescrição Médica | Alta | 4 |
| US08 | Laudos de Exames | Média | 4 |

---

### Notas para a Equipa de Desenvolvimento
1.  **Critérios de Aceitação Transversais:** Qualquer funcionalidade que envolva dados sensíveis deve respeitar o *Audit Trail* (US05).
2.  **Comunicação:** Utilize o *correlation_id* em todas as chamadas entre módulos para facilitar o rastreio via logs estruturados (JSON).
3.  **Segregação de Funções (SoD):** Durante a implementação das US07 e US08, garantir que o médico que prescreve não é o mesmo utilizador que valida a dispensação técnica (se aplicável).

---

## arquiteto

_Modelo: gemini-3.1-flash-lite_

Como Arquiteto de Software, apresento a proposta de arquitetura para o Sistema de Gestão Hospitalar (HIS), focada em modularidade, integridade transacional e escalabilidade, seguindo as diretrizes de arquitetura híbrida e modular.

---

### 1. Stack Tecnológica Recomendada
A escolha prioriza a robustez do ecossistema Java e a flexibilidade do PostgreSQL para um ambiente hospitalar crítico.

*   **Backend:** Java 21 + Spring Boot (Arquitetura de Monólito Modular).
*   **Banco de Dados Relacional (Core):** **Supabase (PostgreSQL)** para gestão de prontuários, escalas, estoques e transações financeiras (garantia ACID).
*   **Banco de Dados NoSQL (Logs/Eventos):** **MongoDB Atlas** para armazenamento de logs de auditoria, telemetria de dispositivos médicos e histórico de sinais vitais de alta frequência.
*   **Cache/Filas:** Redis (Sessões e Rate Limiting).
*   **Frontend:** Angular (TypeScript) para interfaces complexas e formulários clínicos.
*   **Infraestrutura:** Docker + Kubernetes (Orquestração) + GitHub Actions (CI/CD).

---

### 2. Arquitetura em Camadas (Modular Monolith)

A estrutura é organizada por **Bounded Contexts** (Domínios), garantindo que a lógica de negócio de um módulo não contamine o outro.

#### A. Camada de Apresentação (Frontend)
*   **SPA (Single Page Application):** Angular com *State Management* (NgRx) para manter a consistência dos dados do paciente durante a navegação.
*   **UI Kit:** Design System baseado em componentes reutilizáveis para garantir a padronização visual (ex: cores de triagem de Manchester).

#### B. Camada de Aplicação (API Gateway / BFF)
*   **API Gateway:** Ponto único de entrada para autenticação (JWT) e roteamento.
*   **Serviços de Domínio:** Módulos isolados (Urgência, Internamento, Administrativo, MDT).
*   **Comunicação:** Síncrona via REST/gRPC para operações críticas; Assíncrona via **Eventos de Domínio** (ex: `AltaMedicaRegistada`) para processos de suporte (limpeza, faturação).

#### C. Camada de Domínio (Business Logic)
*   **Máquinas de Estado:** Implementação rigorosa de transições (ex: `AGUARDANDO_TRIAGEM` → `EM_ATENDIMENTO`).
*   **RBAC/ABAC:** Motor de autorização centralizado para validar permissões de utilizadores (médicos, enfermeiros, administrativos) antes de qualquer operação.

#### D. Camada de Persistência (Data Layer)
*   **PostgreSQL (Supabase):** Tabelas particionadas para dados transacionais e históricos clínicos.
*   **MongoDB Atlas:** Coleções de documentos para logs de auditoria imutáveis e dados não estruturados (laudos de exames, telemetria).
*   **Transactional Outbox:** Padrão para garantir que eventos de negócio sejam publicados apenas se a transação no banco relacional for bem-sucedida.

---

### 3. Limites e Segregação de Responsabilidades

Para garantir a segurança e a conformidade (SoD - Segregation of Duties):

1.  **Isolamento de Contexto:** O módulo de "Compras/Financeiro" não tem acesso direto às tabelas de "Prontuário Clínico". A comunicação ocorre estritamente via eventos ou APIs de leitura anonimizada.
2.  **Trilha de Auditoria:** Qualquer alteração em dados sensíveis é interceptada por um *Aspect* (AOP no Spring) que envia o log para o **MongoDB**, garantindo que a auditoria seja imutável e separada do banco transacional.
3.  **Break-the-Glass:** Implementação de um *Interceptor* de segurança que, ao detetar acesso a prontuários fora da alçada do utilizador, exige uma "Justificação de Emergência" e dispara um alerta imediato para a Auditoria Interna.

---

### 4. Checklist de Escalabilidade e Performance
*   **Leitura:** Uso de réplicas de leitura (Read Replicas) no PostgreSQL para relatórios de BI (Apache Superset), evitando impacto no atendimento clínico.
*   **Disponibilidade:** Backend *stateless* permitindo o escalonamento horizontal de instâncias conforme a carga de utilizadores.
*   **Observabilidade:** Logs estruturados (JSON) centralizados, com `correlation_id` para rastreio de ponta a ponta em todo o fluxo hospitalar.

---

## programador

_Modelo: gemini-3.1-flash-lite_

Para implementar o Sistema de Gestão Hospitalar (HIS), adotaremos uma estratégia de **Monólito Modular** com separação estrita de domínios. O foco inicial é a integridade transacional e a rastreabilidade.

---

### 1. Plano de Implementação (Fases)

#### Fase 1: Fundação e Core (Semanas 1-4)
*   **Objetivo:** Estabelecer a infraestrutura de base, autenticação (RBAC) e auditoria.
*   **Entregáveis:**
    *   Setup do projeto (NestJS/Fastify com TypeScript).
    *   Configuração do PostgreSQL com suporte a `JSONB` e `UUID`.
    *   Implementação do módulo de `Auth` e `RBAC` (Middleware de controlo de acesso).
    *   Criação do serviço de `Audit Trail` (Interceptor global para registo de ações).

#### Fase 2: Módulos Assistenciais (Semanas 5-12)
*   **Objetivo:** Fluxo de paciente (Urgência e Internamento).
*   **Entregáveis:**
    *   Módulo de Admissão e Triagem (Manchester).
    *   Máquina de Estados para o ciclo de vida do episódio.
    *   Gestão de Leitos e Enfermarias.

#### Fase 3: Logística e Suporte (Semanas 13-20)
*   **Objetivo:** Gestão de recursos e aprovações.
*   **Entregáveis:**
    *   Módulo de Farmácia e Stock (integração com prescrição).
    *   Workflow de Compras e Aprovações (Alçadas).
    *   Módulo de Manutenção Preventiva de Ativos.

---

### 2. Estrutura de Ficheiros (Modular Monolith)

```text
src/
├── modules/
│   ├── auth/           # RBAC, JWT, Sessões (Redis)
│   ├── audit/          # Interceptors de auditoria imutável
│   ├── urgencia/       # Triagem, Episódios, Fluxo de Manchester
│   ├── internamento/   # Gestão de leitos, Prescrição contínua
│   ├── mdt/            # Laboratório, Imagiologia, Farmácia
│   ├── administrativo/ # Compras, RH, Financeiro
│   └── manutencao/     # Gestão de ativos e calibração
├── shared/
│   ├── database/       # Configuração PostgreSQL/TypeORM
│   ├── messaging/      # RabbitMQ (Event-Driven)
│   └── utils/          # Validações e formatadores
└── main.ts             # Entry point
```

---

### 3. Responsabilidades por Camada

| Camada | Tecnologia | Responsabilidade |
| :--- | :--- | :--- |
| **API Gateway** | Fastify | Rate limiting, CORS, Validação de JWT. |
| **Business Logic** | NestJS (Services) | Regras de negócio, Máquinas de Estado, Validação de SoD. |
| **Persistence** | PostgreSQL | Transações ACID, Particionamento de logs. |
| **Cache/Eventos** | Redis / RabbitMQ | Sessões, filas de alertas críticos, eventos de domínio. |

---

### 4. Riscos Técnicos e Mitigação

1.  **Risco: Concorrência na Alocação de Leitos**
    *   *Mitigação:* Utilizar bloqueios otimistas (*Optimistic Locking*) no PostgreSQL para garantir que dois enfermeiros não aloquem o mesmo leito simultaneamente.
2.  **Risco: Gargalo de Performance em Relatórios**
    *   *Mitigação:* Implementar a estratégia de **CQRS (Command Query Responsibility Segregation)**, utilizando uma réplica de leitura para o Apache Superset/BI.
3.  **Risco: Falha de Integridade na Auditoria**
    *   *Mitigação:* A tabela de auditoria deve ser *append-only* com restrições de banco de dados que impedem `UPDATE` ou `DELETE` de registos existentes.
4.  **Risco: Complexidade de Integração HL7/FHIR**
    *   *Mitigação:* Isolar o módulo MDT com adaptadores específicos, garantindo que o core do sistema não dependa do formato de dados de equipamentos externos.

---

### 5. Regras de Verificação (Checklist de Qualidade)

*   **Segregação de Funções (SoD):** Cada endpoint de aprovação financeira deve validar se o `user_id` do solicitante é diferente do `user_id` do aprovador.
*   **Break-the-Glass:** Todo acesso a prontuário restrito deve disparar um evento assíncrono para o módulo de Auditoria, exigindo uma justificação textual obrigatória.
*   **Logs Estruturados:** Todos os logs devem conter `correlation_id` para rastreio de ponta a ponta em caso de falha no fluxo de prescrição/administração.

---

## qa

_Modelo: gemini-3.1-flash-lite_

Como responsável pela Garantia de Qualidade (QA) do sistema HIS, apresento o plano de testes estruturado para garantir a integridade, conformidade e disponibilidade do sistema hospitalar.

---

### 1. Plano de Testes Unitários (Backend - Spring Boot / Node.js)
Focado na lógica de negócio isolada (serviços e máquinas de estado).

*   **Comandos de Execução:**
    *   `mvn test` (Java) ou `npm test` (Node.js).
*   **Escopo:**
    *   **Máquinas de Estado:** Validar transições (ex: `AGUARDANDO_TRIAGEM` -> `EM_ATENDIMENTO`).
    *   **Regras de Negócio:** Cálculo de prioridade (Triagem de Manchester) e validação de permissões RBAC.
    *   **Utilitários:** Validação de formatos de dados clínicos (HL7/FHIR).
*   **Critérios de Conclusão:**
    *   Cobertura de código mínima de 80% (SonarQube).
    *   Zero falhas em testes de lógica de transição de estados.

### 2. Plano de Testes de Integração
Focado na comunicação entre módulos e persistência de dados.

*   **Comandos de Execução:**
    *   `mvn verify -Pintegration-tests` ou `npm run test:integration`.
*   **Escopo:**
    *   **Persistência:** Testar repositórios PostgreSQL (transações ACID em alocação de leitos).
    *   **Mensageria:** Verificar se o evento `AltaMedicaRegistada` dispara a notificação para `HigienizacaoLeito` via RabbitMQ.
    *   **API:** Testar endpoints protegidos por Spring Security/JWT (validação de tokens e roles).
*   **Critérios de Conclusão:**
    *   Sucesso na comunicação entre o módulo de Urgência e o módulo de Logística.
    *   Trilha de auditoria (Audit Trail) gerada corretamente em todas as operações de escrita.

### 3. Plano de Testes de Aceitação (Scrum Master)
Focado no cumprimento das jornadas do utilizador e regras de negócio.

*   **Comandos de Execução:**
    *   `npx cypress run` (Frontend - Angular/React).
*   **Escopo (Cenários Críticos):**
    *   **Fluxo de Emergência:** Admissão de paciente "desconhecido" e triagem de risco.
    *   **Segregação de Funções (SoD):** Tentar realizar uma compra como Médico (deve ser bloqueado).
    *   **Break-the-Glass:** Simular acesso de emergência a prontuário restrito e verificar se o log de auditoria foi disparado.
*   **Critérios de Conclusão:**
    *   Validação de todos os fluxos descritos na seção 4 e 5 da documentação funcional.
    *   Interface responsiva validada em dispositivos móveis (tablets de enfermagem).

---

### 4. Reporte de Bugs e Qualidade
Qualquer falha detetada seguirá o protocolo abaixo:

1.  **Identificação:** Descrição do erro, `correlation_id` (log estruturado) e perfil utilizado.
2.  **Severidade:**
    *   **Bloqueante:** Falha no fluxo assistencial ou financeiro.
    *   **Crítico:** Falha na auditoria ou segurança (RBAC).
    *   **Normal:** Problemas de usabilidade ou UI.
3.  **Critério de Aceite:** O bug só é considerado corrigido após a execução do teste unitário correspondente e a validação do Scrum Master no ambiente de Staging.

---

**Nota de QA:** Este plano deve ser executado em cada *Sprint* de desenvolvimento. A automação via **GitHub Actions** deve impedir o *merge* de qualquer código que não passe nos testes unitários e de integração definidos.

---

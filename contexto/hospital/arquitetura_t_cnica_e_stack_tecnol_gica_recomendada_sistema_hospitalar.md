# Arquitetura Técnica e Stack Tecnológica Recomendada — Sistema de Gestão Hospitalar Pública (HIS)

Este documento detalha as escolhas tecnológicas, padrões de arquitetura, estratégias de observabilidade e diretrizes de escalabilidade recomendadas para construir um sistema hospitalar robusto, focado em **manutenção preventiva**, **análise crítica**, **alta disponibilidade** e **eficiência operacional**.

## 1. Visão Geral da Arquitetura Recomendada

Para equilibrar velocidade de desenvolvimento, facilidade de manutenção e capacidade de crescimento futuro, recomenda-se iniciar com uma **Arquitetura de Monólito Modular orientada a Eventos (Modular Monolith + Event-Driven)**:

* **Separação clara por domínios (Bounded Contexts):** Urgência, Ambulatório, Internamento/Bloco, MDT (Laboratório/Imagiologia/Farmácia), Administrativo/Financeiro/Logística, RH, Manutenção de Ativos e Auditoria/Governação.

* **Comunicação interna desacoplada:** Eventos de domínio (ex.: `AltaMedicaRegistada` dispara automaticamente um evento para `HigienizacaoLeito` e `AltaAdministrativa`).

* **Evolução futura sem reescrita:** Caso um módulo específico (ex.: Urgência ou Laboratório) exija escala independente no futuro, pode ser extraído como microsserviço com baixo impacto.

## 2. Backend e Regras de Negócio (Consistência e Auditoria)

Em sistemas hospitalares, **integridade transacional, controle de acesso granular (RBAC/ABAC) e trilha de auditoria** são requisitos críticos.

### Opções Recomendadas

* **Opção Principal:** **Java 21+ com Spring Boot** (Spring Security, Spring Data JPA, Spring Batch/Scheduler).

* **Opção Alternativa (Ecossistema JS/TS):** **Node.js com TypeScript** utilizando **NestJS** ou **Fastify**.

### Padrões Essenciais no Backend

* **Máquinas de Estado (State Machines):** Controle rigoroso das transições de estados clínicos (ex.: `AGUARDANDO_TRIAGEM` $\rightarrow$ `EM_ATENDIMENTO` $\rightarrow$ `INTERNADO` $\rightarrow$ `ALTA_MEDICA` $\rightarrow$ `ALTA_ADMINISTRATIVA`) e fluxos financeiros/aprovações.

* **Audit Trail (Trilha de Auditoria Imutável):** Interceptadores/Listeners que registam automaticamente em tabela de auditoria: `utilizador_id`, `perfil_ativo`, `unidade_hospitalar`, `acao`, `dados_anteriores`, `dados_novos`, `timestamp` e `ip_origem`.

* **Mensageria / Transactional Outbox:** Uso de **RabbitMQ** ou **Apache Kafka** (ou padrão *Outbox* no banco relacional) para processamento assíncrono confiável de notificações, alertas críticos, integração com equipamentos laboratoriais (HL7/FHIR) e geração de relatórios.

## 3. Persistência de Dados e Cache

### Banco de Dados Relacional Principal

* **PostgreSQL:**

  * Garante propriedades **ACID** rigorosas, essenciais para evitar conflitos na alocação de camas/leitos, movimentação de medicamentos controlados, escalas de turno e aprovações orçamentais.

  * Suporte nativo a **particionamento de tabelas** (ideal para tabelas de crescimento acelerado como `logs_auditoria`, `sinais_vitais` e `movimentacoes_estoque`), **JSONB** (para formulários clínicos dinâmicos por especialidade) e índices avançados.

### Cache e Filas Rápidas

* **Redis:**

  * Armazenamento em cache de permissões de utilizadores (RBAC), catálogos de medicamentos (CID-10, tabelas de procedimentos), painéis de chamadas/senhas da urgência em tempo real e controle de sessões/*rate limiting*.

## 4. Frontend (Eficiência Operacional e Usabilidade Clínica)

O ambiente hospitalar exige interfaces rápidas, previsíveis e com baixa carga cognitiva para profissionais sob pressão em turnos longos.

### Opções Recomendadas

* **Angular (TypeScript):** Excelente para sistemas corporativos de grande porte devido à sua estrutura padronizada, tipagem forte, injeção de dependência e formulários reativos complexos (prontuários, prescrições, matrizes de aprovação).

* **React (TypeScript) + Vite:** Excelente alternativa com ecossistema vasto para dashboards dinâmicos e fluxos interativos rápidos.

### Diretrizes de Interface (UI/UX Hospitalar)

* **Navegação orientada a tarefas e atalhos de teclado:** Reduzir cliques na receção, triagem e prescrição médica.

* **Código visual de prioridade e estado:** Cores padronizadas para classificação de risco (Triagem de Manchester), estados de leitos (Livre, Ocupado, Em Higienização, Manutenção) e alertas de alergia/interação medicamentosa.

* **Design Responsivo / Multi-dispositivo:** Suporte fluido tanto em desktops de consultório quanto em tablets/carrinhos de enfermagem nas enfermarias.

## 5. Manutenção Preventiva, Crítica e Observabilidade

Esta camada atua em duas frentes: **saúde técnica do software** e **manutenção preventiva/crítica dos ativos físicos do hospital**.

### 5.1. Observabilidade e Manutenção Preventiva do Software

* **Logs Estruturados (JSON):** Centralização de logs com `correlation_id` para rastrear qualquer requisição ponta a ponta.

* **Monitoramento e Alertas Proativos:** **Prometheus + Grafana** (ou stack equivalente) para monitorizar latência de APIs, taxa de erros HTTP 5xx, tamanho de filas, uso de CPU/RAM e conexões ao banco de dados, disparando alertas antes que ocorra indisponibilidade.

* **Healthchecks e Rotinas Agendadas (Jobs/Cron):**

  * Verificação automática de integridade de backups e réplicas.

  * Alertas preventivos de expiração de certificados digitais e lotes de medicamentos.

  * Monitoramento de rutura iminente de estoque mínimo nos setores críticos (Urgência, UCI, Bloco Operatório).

### 5.2. Módulo de Manutenção Preventiva e Crítica Hospitalar (Domínio)

* **Gestão de Ativos e Engenharia Clínica:** Cadastro de todos os equipamentos médicos (ventiladores, monitores, aparelhos de raio-x), infraestrutura predial e ativos de TI.

* **Planos Preventivos Automáticos:** Agendamento automático de ordens de serviço preventivas baseadas em calendário (ex.: a cada 90 dias) ou horas de uso, bloqueando ou alertando sobre equipamentos com calibração vencida.

* **Chamados Críticos (SLA):** Fluxo prioritário para falhas em equipamentos vitais (UCI/Bloco), com escalonamento automático para a Direção Administrativa e Engenharia Clínica caso o tempo máximo de resposta (SLA) seja ultrapassado.

## 6. Business Intelligence (BI) e Análise Crítica Gerencial

Para apoiar a Direção Geral, Direções Executivas e Auditoria Interna sem impactar o desempenho do atendimento clínico:

* **Réplica de Leitura / Data Mart Analítico:** Consultas pesadas de relatórios devem correr numa base de leitura separada do banco transacional principal.

* **Ferramentas de Visualização:** **Apache Superset** (open-source) ou **Power BI**.

* **Indicadores Críticos (KPIs) Monitorizados:**

  * Tempo médio de espera entre admissão, triagem e atendimento médico na Urgência.

  * Taxa de ocupação hospitalar, tempo médio de permanência e tempo de giro/higienização de leitos.

  * Gargalos no fluxo de aprovação de compras e consumo de medicamentos por departamento.

  * Relatórios de conformidade, acessos excecionais (*Break-the-Glass*) e trilha de auditoria.

## 7. Infraestrutura, Escalabilidade e CI/CD

* **Containerização:** **Docker** e **Docker Compose** (para desenvolvimento e ambientes locais/on-premise) ou **Kubernetes** (para clusters de alta disponibilidade).

* **Automação (CI/CD):** **Git** com **GitHub Actions** ou **GitLab CI** executando testes unitários, testes de integração, análise estática de código/segurança e *builds* automatizados a cada alteração.

* **Estratégia de Escalabilidade:**

  * **Backend Stateless:** A API não deve guardar estado de sessão em memória local (delegando ao Redis/JWT), permitindo subir múltiplas instâncias atrás de um **Load Balancer (Nginx / Traefik)** conforme o número de utilizadores e hospitais conectados crescer.

  * **Backup e Recuperação de Desastres (Disaster Recovery):** Backups automáticos diários (full) e contínuos (WAL archiving no PostgreSQL) armazenados em local segregado, com testes periódicos de restauração.

## 8. Resumo da Stack Recomendada (Checklist de Implementação)

| Camada | Tecnologia Recomendada | Objetivo Principal | 
| ----- | ----- | ----- | 
| **Backend** | Java + Spring Boot *(ou Node.js + NestJS/TS)* | Regras de negócio rigorosas, máquinas de estado, RBAC e auditoria | 
| **Frontend** | Angular *(ou React + TypeScript)* | Interfaces operacionais rápidas, formulários clínicos e dashboards | 
| **Banco Principal** | PostgreSQL | Consistência ACID, integridade relacional e particionamento histórico | 
| **Cache / Filas Rápidas** | Redis | Baixa latência, sessões, painéis de senha e cache de permissões | 
| **Mensageria** | RabbitMQ *(ou Outbox Pattern)* | Comunicação assíncrona entre módulos e alertas críticos | 
| **Observabilidade** | Prometheus + Grafana + Logs JSON | Manutenção preventiva do sistema, métricas e alertas de falha | 
| **BI & Analytics** | Apache Superset *(ou Power BI)* | Indicadores gerenciais, análise crítica e prestação de contas | 
| **DevOps / Deploy** | Docker + Nginx + GitHub Actions | Padronização de ambiente, CI/CD e escalabilidade horizontal | 
# Fabrica de IA Autonoma - Relatorio Final

**Ideia:** FutPremier - Execucao autonoma 24h

## scrum_master

_Modelo: gemini-3.1-flash-lite_

Como **Scrum Master**, apresento o planeamento da **Versão 0.1** para o **FutPremier**, focado na infraestrutura base para a execução autónoma 24h.

---

### Sprint 1: Fundação e Conectividade (Duração: 1 semana)

| ID | História de Utilizador | Prioridade | Critérios de Aceitação |
| :--- | :--- | :--- | :--- |
| **US01** | Configurar ambiente de execução 24/7 | Alta | Servidor configurado com *uptime* monitorizado; sistema de *logging* ativo. |
| **US02** | Implementar conector de dados (API) | Alta | Leitura bem-sucedida de dados de jogos em tempo real; formato JSON validado. |
| **US03** | Estruturar base de dados local | Alta | Esquema definido para armazenar jogos, odds e resultados históricos. |

---

### Sprint 2: Motor de Decisão e Automação (Duração: 1 semana)

| ID | História de Utilizador | Prioridade | Critérios de Aceitação |
| :--- | :--- | :--- | :--- |
| **US04** | Desenvolver algoritmo de análise | Média | O sistema identifica oportunidades baseadas em odds pré-definidas. |
| **US05** | Implementar motor de execução (Bot) | Média | O sistema é capaz de simular/executar uma ação de "aposta" sem erro de runtime. |
| **US06** | Sistema de alertas e notificações | Baixa | Envio de notificação (ex: Telegram/Log) sempre que uma ação é executada. |

---

### Definição de Pronto (DoD)
Para que qualquer tarefa seja considerada concluída:
1. **Código:** Revisado e sem erros críticos de sintaxe.
2. **Testes:** Teste unitário simples validando a entrada e saída de dados.
3. **Documentação:** Comentários no código explicando a lógica da função.
4. **Verificação:** O output da tarefa corresponde exatamente ao critério de aceitação definido.

---

### Notas de Gestão
* **Comunicação:** Qualquer bloqueio no acesso às APIs de dados deve ser reportado imediatamente para ajuste do *backlog*.
* **Atomicidade:** As tarefas foram desenhadas para serem independentes, permitindo que a equipa de desenvolvimento trabalhe em paralelo na infraestrutura (Sprint 1) e na lógica (Sprint 2).

**Próximo passo:** Aguardo a validação desta estrutura para iniciar a atribuição das tarefas técnicas aos agentes responsáveis pela implementação.

---

## arquiteto

_Modelo: gemini-3.1-flash-lite_

Como Arquiteto de Software, apresento a proposta de arquitetura para o **FutPremier**, focada em autonomia 24h, escalabilidade e separação de preocupações.

### 1. Stack Tecnológica
*   **Linguagem:** TypeScript (Node.js) para consistência e tipagem.
*   **Runtime:** Docker (Containerização para execução em VPS ou Cloud Run).
*   **Banco de Dados Relacional:** Supabase (PostgreSQL) para gestão de utilizadores, carteiras e estados de apostas.
*   **Banco de Dados NoSQL:** MongoDB Atlas para logs de execução, histórico de odds e telemetria de bots.
*   **Orquestração:** BullMQ (Redis) para gestão de filas e tarefas agendadas (cron jobs).

---

### 2. Arquitetura em Camadas

A estrutura segue o padrão de **Clean Architecture**, garantindo que a lógica de negócio seja independente de frameworks externos.

#### A. Camada de Domínio (Core)
*   **Responsabilidade:** Entidades, regras de negócio e interfaces.
*   **Componentes:** Modelos de aposta, lógica de análise de odds, estados do bot.
*   **Isolamento:** Não possui dependências externas.

#### B. Camada de Aplicação (Use Cases)
*   **Responsabilidade:** Orquestração dos fluxos de trabalho.
*   **Componentes:** Serviços de execução, gestão de filas, processadores de eventos.
*   **Integração:** Coordena a comunicação entre o domínio e os adaptadores.

#### C. Camada de Infraestrutura (Adaptadores)
*   **Responsabilidade:** Implementação técnica.
*   **Componentes:**
    *   **Supabase Client:** Persistência de dados transacionais.
    *   **MongoDB Driver:** Armazenamento de logs de alta frequência.
    *   **HTTP Clients:** Conexão com APIs de casas de apostas.
    *   **Queue Manager:** Gestão de tarefas 24h via Redis.

---

### 3. Limites e Fluxo de Dados

1.  **Ingestão:** O bot consome dados de APIs externas e armazena logs brutos no **MongoDB**.
2.  **Processamento:** A lógica de decisão (Domain) avalia as odds. Se uma aposta é validada, o estado é persistido no **Supabase** (transação financeira/status).
3.  **Execução:** O **BullMQ** garante que o ciclo de vida do bot seja contínuo, processando tarefas em background sem bloquear a thread principal.
4.  **Segurança:** A comunicação com o Supabase utiliza *Row Level Security* (RLS) e chaves de API restritas, enquanto o MongoDB isola os logs de auditoria dos dados críticos de utilizador.

### 4. Verificação de Escalabilidade
*   **Modularidade:** A separação entre o processamento de dados (NoSQL) e a gestão de estado (SQL) permite que o sistema escale a leitura de logs sem degradar a performance das transações financeiras.
*   **Autonomia:** O uso de filas (Redis) permite que o sistema retome tarefas automaticamente após falhas, garantindo a execução 24h exigida.

---

## programador

_Modelo: gemini-3.1-flash-lite_

Como Programador Full-Stack Sénior, apresento o plano de implementação para o **FutPremier**, estruturado para garantir escalabilidade, resiliência e execução autónoma 24/7.

---

### 1. Arquitetura do Sistema
O sistema será dividido em três pilares:
*   **Core (Python/FastAPI):** Lógica de análise de dados, integração com APIs de apostas e modelos preditivos (Pandas).
*   **Gateway (Node.js/Fastify):** Gestão de estado, WebSockets para eventos em tempo real e interface de controlo.
*   **Infraestrutura:** Redis (fila de tarefas), PostgreSQL (logs/histórico) e Docker (orquestração).

---

### 2. Plano de Implementação (Fases)

#### Fase 1: Fundação e Conectividade
*   **`src/core/client.py`**: Cliente assíncrono para interagir com a API de dados desportivos.
*   **`src/core/processor.py`**: Módulo de limpeza e normalização de dados (Pandas).
*   **`src/gateway/server.js`**: Servidor Fastify para monitorização de saúde do sistema.

#### Fase 2: Motor de Decisão e Automação
*   **`src/core/engine.py`**: Algoritmo de decisão baseado em thresholds definidos.
*   **`src/core/scheduler.py`**: Gestor de tarefas agendadas (APScheduler) para garantir execução 24/7.
*   **`src/gateway/socket.js`**: Emissor de eventos para dashboard de controlo.

#### Fase 3: Persistência e Segurança
*   **`src/db/models.py`**: Definição de schemas (SQLAlchemy) para auditoria de operações.
*   **`src/utils/logger.py`**: Sistema de logs estruturados com alertas de falha (integração com Telegram/Slack).

---

### 3. Responsabilidades por Módulo

| Módulo | Tecnologia | Responsabilidade |
| :--- | :--- | :--- |
| **Ingestão** | Python | Captura de dados, normalização e validação. |
| **Análise** | Python | Cálculo de probabilidades e execução de modelos. |
| **Orquestração** | Node.js | Gestão de conexões, WebSockets e API de controlo. |
| **Persistência** | PostgreSQL | Armazenamento de histórico e logs de execução. |

---

### 4. Riscos Técnicos e Mitigação

1.  **Latência de API:**
    *   *Risco:* Atrasos na resposta da API de dados podem invalidar a aposta.
    *   *Mitigação:* Implementação de *circuit breakers* e cache local (Redis) para dados estáticos.
2.  **Falhas de Conexão (24/7):**
    *   *Risco:* Perda de conectividade interrompe o ciclo de execução.
    *   *Mitigação:* Implementação de *watchdog* no Node.js que reinicia o processo Python em caso de *hang*.
3.  **Inconsistência de Dados:**
    *   *Risco:* Dados corrompidos levam a decisões erradas.
    *   *Mitigação:* Validação estrita de schemas (Pydantic) em todas as entradas de dados.
4.  **Limites de Taxa (Rate Limiting):**
    *   *Risco:* Bloqueio por excesso de requisições.
    *   *Mitigação:* Implementação de *token bucket algorithm* para controlar o fluxo de saída.

---

### 5. Próximos Passos (Verificáveis)
1.  Configurar o ambiente Docker com `docker-compose.yml`.
2.  Estabelecer a conexão autenticada com a API de dados.
3.  Validar o fluxo de dados entre o `processor.py` e o `engine.py` com testes unitários (`pytest`).

---

## qa

_Modelo: gemini-3.1-flash-lite_

Como agente de Garantia de Qualidade (QA) para o projeto **FutPremier**, apresento o plano de testes estruturado para assegurar a fiabilidade da execução autónoma 24h.

---

### 1. Plano de Testes Unitários
Focados na lógica isolada dos módulos de decisão e comunicação.

*   **Comandos de Teste:**
    *   `npm test -- --coverage` (ou equivalente no stack do projeto).
*   **Critérios de Conclusão:**
    *   Cobertura de código mínima de 80%.
    *   Zero falhas em funções de cálculo de odds e análise de mercado.
    *   Validação de mocks para APIs externas (ex: fornecedores de dados de futebol).

### 2. Plano de Testes de Integração
Focados na comunicação entre os módulos de análise, execução de ordens e gestão de banca.

*   **Comandos de Teste:**
    *   `npm run test:integration` (simulação de fluxo completo).
*   **Critérios de Conclusão:**
    *   Sucesso na persistência de dados entre o módulo de análise e o módulo de execução.
    *   Tratamento correto de erros de latência de rede.
    *   Verificação de que a banca nunca é excedida (limites de segurança).

### 3. Plano de Testes de Aceitação (UAT)
Validação dos critérios definidos pelo Scrum Master para o funcionamento autónomo.

*   **Comandos de Teste:**
    *   `npm run test:acceptance -- --env=staging`
*   **Critérios de Conclusão:**
    *   **Autonomia:** O sistema deve operar 24h sem intervenção manual (verificar logs de uptime).
    *   **Precisão:** As ordens executadas devem corresponder exatamente aos critérios de entrada definidos na estratégia.
    *   **Fail-safe:** O sistema deve entrar em modo "pausa" se a API de dados falhar ou se a banca atingir o *stop-loss* configurado.

---

### 4. Protocolo de Reporte de Bugs
Qualquer falha detetada durante a execução dos testes acima deve ser reportada seguindo o formato:

1.  **ID do Bug:** [Breve descrição]
2.  **Severidade:** (Crítica/Alta/Média/Baixa)
3.  **Passos para Reproduzir:** (Comandos exatos)
4.  **Resultado Esperado:**
5.  **Resultado Obtido:**

---

**Nota de QA:** Este plano deve ser executado em ambiente de *staging* antes de qualquer *merge* para a *branch* de produção. Aguardo a disponibilização do ambiente para iniciar a execução dos testes.

---

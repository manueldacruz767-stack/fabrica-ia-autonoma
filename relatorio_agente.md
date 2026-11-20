### Plano de Automação: Validação Final da Fábrica de IA

Este plano estabelece o fluxo de trabalho para garantir que a "Validação final do agente" seja integrada de forma segura e automatizada no ciclo de vida da nossa infraestrutura.

---

#### 1. Estrutura de Repositório (CLI `gh`)
Para garantir a rastreabilidade, a validação será tratada como uma *feature branch*.
*   **Ação:** Criar repositório ou branch via `gh repo create` ou `gh branch`.
*   **Verificação:** Confirmar que o `remote` está configurado para o GitHub e que as permissões de escrita estão restritas ao utilizador autenticado.

#### 2. Pipeline de CI/CD (GitHub Actions)
A validação será disparada automaticamente em cada *push* para a branch `main` ou *pull request*.
*   **Workflow:**
    1.  **Linting:** Verificação de sintaxe do código do agente.
    2.  **Security Scan:** Execução de `gitleaks` para garantir que nenhuma credencial foi exposta no código.
    3.  **Testes de Integração:** Simulação da resposta do agente num ambiente isolado.
*   **Segurança:** Utilização de `secrets` do GitHub para injetar variáveis de ambiente (API Keys) sem exposição direta no código.

#### 3. Gestão de Deploy (Vercel/Render)
A validação final só será promovida para produção após o sucesso dos testes.
*   **Vercel:** Utilização de *Preview Deployments* para validar o comportamento do agente em ambiente de staging.
*   **Render:** Monitorização de logs de build via CLI para garantir que o serviço de backend (se aplicável) subiu sem erros de configuração.
*   **Rollback:** Em caso de falha na validação, o sistema deve manter a versão anterior estável (estratégia de *blue-green deployment*).

#### 4. Sincronização e Auditoria (Fedora)
*   **Ambiente Local:** Manter o ambiente Fedora sincronizado via `git pull --rebase` antes de qualquer alteração.
*   **Auditoria:** Todos os comandos de infraestrutura executados localmente devem ser registados no histórico do shell (`.bash_history` ou `.zsh_history`) para revisão posterior.
*   **Validação:** O estado final da "Fábrica de IA" será confirmado através de um *status check* no GitHub, garantindo que o agente passou em todos os testes de segurança e performance antes do merge final.

---
*Nota: Este plano está pronto para implementação. Aguardo a confirmação do ambiente para iniciar a execução dos comandos de infraestrutura.*
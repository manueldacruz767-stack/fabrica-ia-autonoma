### Plano de Automação: Validação com Ações Externas

Para integrar validações externas na fábrica de IA, o foco será garantir que o pipeline de CI/CD não apenas compile o código, mas verifique a integridade dos modelos e respostas através de *endpoints* de teste.

---

#### 1. Estrutura de Validação (Pipeline)
A automação será dividida em três camadas de verificação dentro do `GitHub Actions`:
*   **Camada de Linting:** Verificação estática de código e segurança (`bandit` para Python, `eslint` para JS).
*   **Camada de Integração:** Execução de testes que consultam APIs externas (mockadas ou *staging*) para validar a lógica de negócio.
*   **Camada de *Smoke Test*:** Após o deploy na Vercel/Render, um *job* final verifica se o serviço responde com `HTTP 200`.

#### 2. Segurança e Gestão de Segredos
*   **Variáveis de Ambiente:** Nenhuma chave de API será codificada. Utilizaremos o `GitHub Secrets` para injetar credenciais em tempo de execução.
*   **Princípio do Menor Privilégio:** Os *tokens* de deploy (Vercel/Render) terão permissão apenas para o escopo necessário, sem acesso total à conta.
*   **Validação de Inputs:** Qualquer dado vindo de fontes externas será sanitizado antes de ser processado pelos modelos de IA.

#### 3. Fluxo de Trabalho (Workflow)
O ficheiro `.github/workflows/main.yml` seguirá este padrão:
1.  **Checkout:** Sincronização do repositório local (Fedora) com a nuvem.
2.  **Setup:** Instalação de dependências e configuração do ambiente.
3.  **Testes:** Execução de scripts de validação externa.
4.  **Deploy:** Se os testes passarem, o comando de deploy é disparado.
5.  **Notificação:** Feedback automático sobre o sucesso ou falha da validação.

#### 4. Verificação de Integridade
Para garantir a sincronização entre o ambiente local e a nuvem:
*   **Comando de Verificação:** `gh workflow run` será utilizado para disparar testes manuais de validação antes de qualquer *merge*.
*   **Monitorização:** Logs de erro serão centralizados no GitHub Actions para auditoria rápida.

---
*Nota: Este plano está pronto para implementação. Recomendo a criação de um ficheiro `tests/external_validation.py` para definir os critérios de sucesso das ações externas antes de integrar no pipeline.*
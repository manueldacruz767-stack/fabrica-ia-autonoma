# 🤖 Fábrica de IA Autónoma (GitHub Actions + CrewAI + Gemini)

Uma "Fábrica de Software" totalmente automatizada que utiliza agentes de IA (Arquiteto, Desenvolvedor Backend, Desenvolvedor Frontend e QA) orquestrados pelo CrewAI e alimentados pelo Google Gemini para desenhar e arquitetar projetos diretamente na nuvem através do GitHub Actions.

## 🚀 Como Funciona
1. O fluxo é acionado manualmente no GitHub Actions (aba **Actions**).
2. O script `orquestrador.py` inicializa a equipa de agentes com base na ideia fornecida.
3. A IA processa o planeamento e gera a documentação/código final (`projeto_final.md`).
4. O repositório é atualizado automaticamente e recebe uma notificação por e-mail.

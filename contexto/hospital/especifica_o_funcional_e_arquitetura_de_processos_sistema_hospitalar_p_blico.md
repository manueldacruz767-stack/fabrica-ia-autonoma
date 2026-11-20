# Especificação Funcional e Arquitetura de Processos — Sistema de Gestão Hospitalar Pública (HIS)

Este documento reúne toda a estrutura organizacional, fluxos operacionais, jornadas de pacientes, regras de negócio, dependências, matriz de permissões (RBAC) e assinatura documental de um Hospital Público, estruturado para servir como **base completa para levantamento de requisitos, modelagem de banco de dados e desenvolvimento de software**.

---

## 1. Macroarquitetura e Módulos do Sistema

Um Hospital Público divide-se em **4 grandes áreas assistenciais** e **2 grandes eixos de gestão/apoio**, que devem refletir os módulos principais do software:

1. **Módulo de Urgência / Emergência:** Acolhimento, triagem de risco, estabilização, observação e desfecho rápido.
2. **Módulo Ambulatorial / Consultas Externas:** Agendamento, receção, pré-consulta, atendimento médico programado e retornos.
3. **Módulo de Internamento, Bloco Operatório e UCI:** Gestão de camas/leitos, prescrição contínua, cuidados de enfermagem, agendamento cirúrgico, central de esterilização e alta hospitalar.
4. **Módulo de Meios Complementares de Diagnóstico e Terapêutica (MDT):** Laboratório de análises clínicas, imagiologia/radiologia, farmácia hospitalar e reabilitação/fisioterapia.
5. **Módulo Administrativo, Financeiro e Logístico (ERP Hospitalar):** Recursos Humanos (RH), Finanças e Contabilidade, Compras e Aprovisionamento, Armazém/Logística, Transportes (Ambulâncias), Serviços Gerais (Manutenção, Limpeza, Nutrição, Segurança) e Gestão de TI.
6. **Módulo de Governação, Direção e Consultoria:** Direção Geral / Conselho de Administração, Direções Executivas (Clínica, Enfermagem, Administrativa), Assessoria Jurídica, Auditoria Interna, Relações Públicas e Comissão de Ética.

---

## 2. Organograma Hierárquico (Estrutura de Unidades Organizacionais)

Para modelagem da tabela de `UnidadesOrganizacionais` e hierarquia de aprovação:

### Nível 1: Órgão de Gestão Máxima e Consultoria
* **Direção Geral / Conselho de Administração**
* **Serviços de Apoio e Consultoria (Staff da Direção Geral):**
  * Assessoria Jurídica
  * Auditoria Interna
  * Relações Públicas
  * Comissão de Ética

### Nível 2: Direções Executivas
* **Direção Clínica**
* **Direção de Enfermagem**
* **Direção Administrativa e Financeira**
* *(Opcional - Hospitais de Ensino)* **Direção Pedagógica e Científica**

### Nível 3: Departamentos e Serviços Assistenciais
* **Subordinados à Direção Clínica:**
  * Serviço de Urgência / Emergência
  * Departamento de Medicina (Medicina Interna, Pediatria, etc.)
  * Departamento de Cirurgia (Cirurgia Geral, Ortopedia, Obstetrícia, etc.)
  * Bloco Operatório
  * Unidade de Cuidados Intensivos (UCI)
  * Meios Complementares de Diagnóstico e Terapêutica (Laboratório, Imagiologia, Farmácia, Fisioterapia)
  * Consultas Externas (Ambulatório)
* **Subordinados à Direção de Enfermagem:**
  * Supervisão de Enfermagem
  * Enfermeiros-Chefes (por unidade/ala)
  * Equipas de Enfermagem (Enfermeiros e Técnicos de Enfermagem)
  * Central de Esterilização

### Nível 4: Serviços de Apoio Geral e Logístico
* **Subordinados à Direção Administrativa e Financeira:**
  * Recursos Humanos (RH)
  * Finanças e Contabilidade
  * Compras e Aprovisionamento
  * Logística e Transportes (Armazém Central e Frota de Ambulâncias)
  * Serviços Gerais (Manutenção Predial/Clínica, Limpeza/Higienização, Lavandaria, Nutrição/Cozinha, Segurança Patrimonial)
  * Gestão de Informação (TI) e Estatística/Arquivo Clínico

---

## 3. Ciclos Operacionais do Hospital (Visão Sistémica)

O software deve suportar e interligar **3 grandes ciclos**:

1. **Ciclo Assistencial (Core Clínico):**
   `Admissão/Registo -> Triagem -> Consulta/Avaliação -> Pedidos de Exames/Prescrição -> Execução (MDT/Enfermagem/Farmácia) -> Reavaliação -> Desfecho (Alta, Internamento, Cirurgia, Transferência ou Óbito) -> Arquivo Clínico.`
2. **Ciclo Administrativo, Logístico e Financeiro (Core de Suporte):**
   `Identificação de Necessidade -> Requisição Interna -> Validação Técnica -> Verificação Orçamental -> Cotação/Concurso -> Parecer Jurídico/Auditoria (se aplicável) -> Aprovação -> Empenho/Pagamento -> Compra -> Receção no Armazém -> Distribuição Interna.`
3. **Ciclo de Governação, RH e Controlo:**
   `Planeamento Estratégico -> Gestão de Escalas/Turnos -> Execução e Registo de Ponto/Ocorrências -> Consolidação de Indicadores -> Auditoria -> Prestação de Contas ao Ministério da Saúde.`

---

## 4. Máquinas de Estado e Fluxos do Paciente (Jornada Clínica)

### 4.1. Fluxo A: Urgência / Emergência (Casos Agudos)
* **Estados do Episódio:** `ADMITIDO` $\rightarrow$ `AGUARDANDO_TRIAGEM` $\rightarrow$ `EM_TRIAGEM` $\rightarrow$ `AGUARDANDO_MEDICO` $\rightarrow$ `EM_ATENDIMENTO` $\rightarrow$ `AGUARDANDO_EXAMES_OU_MEDICACAO` $\rightarrow$ `EM_OBSERVACAO` $\rightarrow$ `ENCERRADO (ALTA / INTERNADO / CIRURGIA / TRANSFERIDO / OBITO)`.
* **Passo a Passo:**
  1. **Admissão/Receção:** Abertura de episódio de urgência. *Regra de negócio:* Permitir abertura de ficha provisória ("Paciente Desconhecido / Indocumentado") em casos críticos inconscientes, com posterior fusão de prontuário.
  2. **Triagem (Enfermagem):** Registo de queixa principal, sinais vitais e classificação de risco (define prioridade na fila médica).
  3. **Atendimento Médico:** Anamnese, hipótese diagnóstica, prescrição de medicação de urgência e solicitação de exames (Laboratório/Imagiologia).
  4. **Execução Assistencial:** Enfermagem administra fármacos (com baixa automática na farmácia/stock do setor); MDT processa exames e devolve laudos.
  5. **Desfecho Médico:**
     * *Alta:* Geração de receita externa e resumo de alta.
     * *Internamento:* Geração de guia de internamento e reserva de cama/leito.
     * *Bloco Operatório:* Pedido cirúrgico de emergência.
     * *Transferência:* Guia de transferência inter-hospitalar + solicitação de transporte (ambulância).

### 4.2. Fluxo B: Consultas Externas / Ambulatório (Programado)
* **Estados do Episódio:** `AGENDADO` $\rightarrow$ `CHECK_IN_REALIZADO` $\rightarrow$ `PRE_CONSULTA` $\rightarrow$ `EM_CONSULTA` $\rightarrow$ `FINALIZADO` (ou `FALTOU` / `CANCELADO`).
* **Passo a Passo:**
  1. **Agendamento e Check-in:** Validação de vaga por especialidade/médico e confirmação de presença na receção.
  2. **Pré-consulta (Enfermagem):** Aferição de dados antropométricos e sinais vitais.
  3. **Consulta Médica:** Evolução clínica no prontuário eletrónico, emissão de receitas, pedidos de exames futuros ou agendamento de retorno.
  4. **Pós-consulta:** Levantamento de medicamentos na farmácia ambulatorial ou marcação de exames/fisioterapia.

### 4.3. Fluxo C: Internamento, Bloco Operatório e Alta
* **Estados do Internamento:** `SOLICITADO` $\rightarrow$ `LEITO_ALOCADO` $\rightarrow$ `INTERNADO_ATIVO` $\rightarrow$ `EM_CIRURGIA` (opcional) $\rightarrow$ `ALTA_MEDICA_DADA` $\rightarrow$ `ALTA_ADMINISTRATIVA_CONCLUIDA` (ou `OBITO`).
* **Passo a Passo:**
  1. **Alocação de Leito:** Enfermeiro-Chefe/Gestão de Leitos atribui enfermaria e cama conforme especialidade, sexo e isolamento.
  2. **Rotina Diária:**
     * *Médico:* Visita diária, evolução e atualização da prescrição médica (validade padrão de 24h).
     * *Enfermagem:* Aprazamento de horários, checagem de administração de medicamentos, balanço hídrico, sinais vitais e evolução de enfermagem.
     * *Nutrição:* Recebe dieta prescrita pelo médico para produção/entrega.
     * *Bloco Operatório (se aplicável):* Checklist de cirurgia segura, pedido de kits à Central de Esterilização, descrição cirúrgica e recobro/UCI.
  3. **Alta Hospitalar:**
     * Médico regista a **Alta Clínica** (bloqueia novas prescrições e gera sumário de alta/receita).
     * Administração/Faturação (quando aplicável) conclui a **Alta Administrativa**.
     * Serviços Gerais (Limpeza) recebem alerta automático de **"Leito Sujo / Higienização Terminal"** antes de liberar a cama para novo paciente.

---

## 5. Fluxos Internos de Gestão, Aprovação e Dependência

### 5.1. Fluxo de Requisição de Materiais e Medicamentos (Consumo Interno)
1. **Solicitação:** `Enfermeiro-Chefe` ou `Chefe de Serviço Médico` cria requisição no sistema para reposição de stock do setor.
2. **Verificação de Stock Central:**
   * *Se disponível:* `Farmácia` ou `Logística (Armazém Central)` separa, dá baixa no stock central e transfere para o stock do setor solicitante (com confirmação de receção).
   * *Se indisponível / rutura:* O pedido é encaminhado para aprovação técnica da `Direção Clínica` (medicamentos/equipamentos médicos) ou `Direção de Enfermagem` (insumos de enfermagem).
3. **Encaminhamento para Compra:** Após validação técnica, o pedido segue automaticamente para a `Direção Administrativa e Financeira`.

### 5.2. Fluxo de Compras, Contratações e Pagamentos (Workflow Financeiro)
1. **Orçamentação:** `Compras e Aprovisionamento` insere cotações/propostas; `Finanças e Contabilidade` verifica dotação/cabimento orçamental.
2. **Roteamento por Alçada (Regra de Negócio Configurável):**
   * *Alçada 1 (Rotina / Baixo Valor):* Aprovado pela `Direção Administrativa e Financeira`.
   * *Alçada 2 (Alto Valor / Contratos / Concursos):* Sobe para `Direção Geral / Conselho de Administração`.
3. **Conformidade (Obrigatório na Alçada 2):** Antes da assinatura final da Direção Geral, o processo passa por parecer da `Assessoria Jurídica` (legalidade) e `Auditoria Interna` (controlo).
4. **Execução:** `Direção Geral` aprova $\rightarrow$ `Finanças` emite ordem de pagamento/empenho $\rightarrow$ `Compras` emite ordem de fornecimento $\rightarrow$ `Logística` recebe a mercadoria (conferência física vs. nota fiscal) $\rightarrow$ Distribuição ao setor solicitante.

### 5.3. Fluxo de Recursos Humanos (Férias, Faltas, Trocas de Turno)
1. **Pedido:** `Funcionário` submete pedido (férias, dispensa, troca de turno) no portal interno.
2. **Aprovação Operacional (Chefia Direta):** `Enfermeiro-Chefe` ou `Chefe de Serviço` valida o impacto na escala do setor.
3. **Validação Executiva:** A respetiva `Direção Executiva` (Clínica, Enfermagem ou Administrativa) homologa.
4. **Registo e Folha:** `Recursos Humanos (RH)` regista no cadastro funcional e processa impactos na folha salarial.

### 5.4. Fluxo de Manutenção e Esterilização
* **Manutenção:** Setor abre chamado $\rightarrow$ `Serviços Gerais / Engenharia Clínica` avalia $\rightarrow$ Conserta internamente ou aciona compra de peça/serviço externo $\rightarrow$ Setor solicitante assina encerramento do chamado.
* **Esterilização:** Bloco/Urgência envia material contaminado $\rightarrow$ `Central de Esterilização` regista lote, lava, esteriliza, valida indicadores biológicos e devolve kits estéreis rastreados.

---

## 6. Perfis de Utilizadores, Responsabilidades e Limites (Regras RBAC)

Cada perfil abaixo define exatamente o escopo de ações permitidas e bloqueadas no software.

### 6.1. Diretor Geral / Conselho de Administração
* **Função:** Comando estratégico, gestão orçamental e representação institucional.
* **O que FAZ:** Visualiza dashboards executivos globais, aprova planos anuais, gerencia metas, supervisiona direções e presta contas à tutela.
* **O que NÃO FAZ:** Não acede para edição a prontuários clínicos, não realiza consultas, não prescreve fármacos nem executa lançamentos operacionais de balcão/contabilidade.
* **O que AUTORIZA:** Despesas de alto valor, concursos públicos, contratações/nomeações, regulamentos internos e acordos institucionais.
* **O que NÃO AUTORIZA:** Condutas clínicas contra protocolos médicos; gastos sem cabimento orçamental ou sem parecer jurídico/auditoria obrigatório.
* **De quem DEPENDE:** Relatórios das Direções Executivas, pareceres da Assessoria Jurídica e Auditoria Interna.
* **De quem NÃO DEPENDE:** Não possui superior hierárquico interno (subordinado apenas ao Ministério da Saúde/Tutela).
* **O que ASSINA:** Portarias/ordens de serviço, contratos, atos de RH aprovados, autorizações de despesa de topo e relatórios oficiais.
* **O que NÃO ASSINA:** Receitas médicas, atestados clínicos, laudos de exames ou evoluções de pacientes.

### 6.2. Diretor Clínico
* **Função:** Liderança técnica e organizacional do corpo médico e serviços de diagnóstico.
* **O que FAZ:** Gere departamentos médicos, aprova protocolos clínicos, monitoriza indicadores assistenciais (mortalidade, infeção, tempo de espera) e valida escalas médicas.
* **O que NÃO FAZ:** Não gere orçamento global do hospital, folha salarial administrativa, compras comerciais ou manutenção predial.
* **O que AUTORIZA:** Escalas médicas, protocolos clínicos, pareceres técnicos de necessidade de medicamentos/equipamentos médicos e transferências clínicas complexas.
* **O que NÃO AUTORIZA:** Pagamentos a fornecedores, contratações administrativas sem Direção Geral/RH ou alterações financeiras.
* **De quem DEPENDE:** Chefes de Serviço/Departamento (dados operacionais) e Direção Administrativa (disponibilização de recursos).
* **De quem NÃO DEPENDE:** Enfermeiros-chefes, técnicos administrativos ou fornecedores.
* **O que ASSINA:** Pareceres técnicos clínicos, escalas médicas homologadas e relatórios da Direção Clínica.
* **O que NÃO ASSINA:** Ordens de pagamento, contratos comerciais ou atestados clínicos de pacientes que não assistiu diretamente.

### 6.3. Médico (Especialista / Clínico Geral)
* **Função:** Diagnóstico, prescrição terapêutica, procedimentos cirúrgicos e decisão de internamento/alta.
* **O que FAZ:** Regista anamnese e evolução clínica, solicita exames (MDT), prescreve medicamentos e dietas, realiza cirurgias e emite relatórios clínicos.
* **O que NÃO FAZ:** Não executa checagem rotineira de administração de enfermagem, não movimenta stock central de armazém e não aprova férias administrativas.
* **O que AUTORIZA:** Internamento, procedimentos/cirurgias, prescrições medicamentosas, pedidos de exames e **Alta Médica**.
* **O que NÃO AUTORIZA:** Dispensa de regras de faturação administrativa, compras externas ou saída de paciente contra indicação sem termo de responsabilidade registado.
* **De quem DEPENDE:** Resultados de exames (MDT), disponibilidade de fármacos (Farmácia) e execução de cuidados (Enfermagem).
* **De quem NÃO DEPENDE:** Rececionistas, seguranças ou pessoal administrativo para decidir diagnóstico ou prescrição.
* **O que ASSINA:** Prontuário/evolução médica, receitas médicas, pedidos de exames, atestados médicos, declarações de óbito e sumários de alta.
* **O que NÃO ASSINA:** Empenhos financeiros, contratos de fornecedores ou folhas de ponto de outras equipas.

### 6.4. Diretor de Enfermagem / Enfermeiro-Chefe
* **Função:** Gestão da assistência de enfermagem, equipas de turnos e logística setorial de cuidados.
* **O que FAZ:** Elabora e aprova escalas de enfermagem, supervisiona cuidados nas enfermarias/urgência/UCI, gere leitos e controla o stock mínimo de consumíveis do setor.
* **O que NÃO FAZ:** Não realiza diagnóstico médico, não prescreve medicamentos restritos a médicos e não gere contabilidade geral.
* **O que AUTORIZA:** Escalas e trocas de turno de enfermagem, requisições internas de materiais de enfermagem e alocação/transferência interna de leitos.
* **O que NÃO AUTORIZA:** Alta médica hospitalar, prescrição médica ou compras financeiras externas.
* **De quem DEPENDE:** Prescrição médica (base para cuidados), Armazém/Farmácia (fornecimento de insumos) e Direção Administrativa.
* **De quem NÃO DEPENDE:** Médicos para organizar a escala de turnos ou metodologia técnica de enfermagem.
* **O que ASSINA:** Escalas de enfermagem, requisições internas de material, relatórios de ocorrência do setor e mapas de supervisão.
* **O que NÃO ASSINA:** Receitas médicas, atestados de incapacidade/doença ou ordens de pagamento.

### 6.5. Enfermeiro / Técnico de Enfermagem
* **Função:** Triagem de risco, cuidados diretos contínuos e execução de prescrições médicas.
* **O que FAZ:** Realiza classificação de risco na triagem, aferição de sinais vitais, administração de medicamentos prescritos, curativos, preparação pré-operatória e evolução de enfermagem.
* **O que NÃO FAZ:** Não faz diagnóstico médico definitivo, não prescreve tratamento médico autônomo e não dá alta hospitalar.
* **O que AUTORIZA:** Priorização de atendimento na triagem (segundo protocolo validado) e acionamento de emergência clínica.
* **O que NÃO AUTORIZA:** Suspensão arbitrária de medicação prescrita, alta/saída de paciente ou dispensa de fármacos sem prescrição.
* **De quem DEPENDE:** Prescrição médica, supervisão do Enfermeiro-Chefe e insumos da Farmácia/Central de Esterilização.
* **De quem NÃO DEPENDE:** Pessoal de receção, limpeza ou segurança para executar cuidados assistenciais.
* **O que ASSINA:** Evolução e notas de enfermagem, folha de sinais vitais/balanço hídrico, checagem de medicação administrada e termo de receção de insumos do setor.
* **O que NÃO ASSINA:** Receitas médicas, laudos de exames diagnósticos ou guias de internamento/alta médica.

### 6.6. Técnicos de Meios Complementares de Diagnóstico e Terapêutica (MDT)
*(Inclui Farmacêuticos, Técnicos de Laboratório, Técnicos de Imagiologia/Radiologia e Fisioterapeutas)*
* **Função:** Execução de exames diagnósticos, validação/dispensação farmacêutica e reabilitação funcional.
* **O que FAZ:** Recebe pedidos médicos, colhe/processa amostras laboratoriais, realiza exames de imagem, valida e dispensa medicamentos por prescrição, ou realiza sessões de fisioterapia.
* **O que NÃO FAZ:** Não realiza consultas médicas gerais nem define diagnóstico clínico global ou alta hospitalar.
* **O que AUTORIZA:** Liberação técnica de resultados/laudos de exames e dispensação de medicamentos prescritos conforme normas sanitárias.
* **O que NÃO AUTORIZA:** Entrega de psicotrópicos/controlados sem receita válida, alteração de dosagem médica sem validação do prescritor ou alta hospitalar.
* **De quem DEPENDE:** Pedidos/prescrições médicas, manutenção de equipamentos/reagentes e normas da Direção Clínica.
* **De quem NÃO DEPENDE:** Receção ou segurança para validar tecnicamente um exame ou preparação farmacêutica.
* **O que ASSINA:** Laudos técnicos de laboratório/imagem, registos de dispensação farmacêutica, controlo de psicotrópicos e evoluções de fisioterapia.
* **O que NÃO ASSINA:** Receitas médicas de consulta, atestados médicos ou contratos administrativos.

### 6.7. Direção Administrativa e Financeira (e Setores Subordinados)
*(Inclui RH, Finanças/Contabilidade, Compras, Logística/Armazém, Serviços Gerais e TI)*
* **Função:** Gestão financeira, patrimonial, logística, de pessoal, infraestrutura e sistemas de informação.
* **O que FAZ:** Processa folha salarial e ponto (RH), executa contabilidade e pagamentos (Finanças), realiza cotações/compras (Aprovisionamento), gere stocks e ambulâncias (Logística), mantém limpeza/segurança/equipamentos (Serviços Gerais) e administra servidores/redes (TI).
* **O que NÃO FAZ:** Não acede a conteúdo clínico sensível sem perfil de auditoria/estatística anonimizada, não toma decisões clínicas e não prescreve tratamentos.
* **O que AUTORIZA:** Pagamentos dentro da alçada orçamental, saídas de stock central para setores, compras de rotina e ordens de manutenção/TI.
* **O que NÃO AUTORIZA:** Alta médica de pacientes, bloqueio de atendimento de emergência por motivos burocráticos ou compras sem dotação orçamental.
* **De quem DEPENDE:** Requisições das áreas assistenciais (para saber demandas) e aprovações superiores da Direção Geral.
* **De quem NÃO DEPENDE:** Médicos ou enfermeiros para gerir rotinas financeiras, contábeis, de RH ou de TI.
* **O que ASSINA:** Empenhos e ordens de pagamento (na alçada), ordens de compra, guias de remessa/stock, contratos de rotina e termos de manutenção.
* **O que NÃO ASSINA:** Prontuários clínicos, receitas médicas, laudos diagnósticos ou atestados de saúde.

### 6.8. Serviços de Apoio e Consultoria (Jurídico, Auditoria Interna, Relações Públicas, Comissão de Ética)
* **Função:** Conformidade legal, auditoria/controlo interno, comunicação institucional/utente e análise ética.
* **O que FAZ:** Analisa contratos/concursos (Jurídico), audita contas/stocks/processos (Auditoria), gere reclamações/ouvidoria e comunicação (Relações Públicas) e avalia dilemas éticos/ensaios clínicos (Comissão de Ética).
* **O que NÃO FAZ:** Não presta assistência médica/enfermagem direta e não executa gestão operacional diária de setores.
* **O que AUTORIZA:** Emite **pareceres vinculativos ou consultivos** de conformidade (não executa compras nem interna pacientes).
* **O que NÃO AUTORIZA:** Tratamentos médicos, movimentação de leitos ou pagamentos financeiros diretos.
* **De quem DEPENDE:** Acesso irrestrito a documentos e logs de auditoria do sistema; reporta à Direção Geral.
* **De quem NÃO DEPENDE:** Direções executivas ou chefias de serviço (devem possuir independência técnica de análise).
* **O que ASSINA:** Pareceres jurídicos, relatórios de auditoria interna, atas/pareceres da Comissão de Ética e respostas oficiais de ouvidoria.
* **O que NÃO ASSINA:** Prescrições médicas, evoluções clínicas ou ordens de compra.

---

## 7. Matriz Consolidada de Permissões, Assinaturas e Documentos

Esta tabela serve como guia direto para implementação da camada de **Autorização (RBAC/ABAC)** e **Assinatura Digital/Eletrónica** no software:

| Documento / Ação no Sistema | Perfil Iniciador | Perfil Validador / Aprovador | Perfil Assinante Final | Bloqueado Para (Exemplos) |
| :--- | :--- | :--- | :--- | :--- |
| **Ficha de Admissão / Triagem** | Rececionista / Enfermeiro | Enfermeiro (Triagem) | Rececionista / Enfermeiro | Finanças, Compras, Jurídico |
| **Prescrição Médica / Receita** | Médico | Médico (Farmacêutico valida dose/interação) | Médico | Enfermagem, Administrativo, Direção Geral |
| **Administração de Medicação** | Enfermeiro / Téc. Enfermagem | Prescrição Médica Ativa (Sistema bloqueia sem prescrição) | Enfermeiro / Téc. Enfermagem | Receção, Administrativo, MDT |
| **Pedido e Laudo de Exame (MDT)** | Médico (Pedido) | Técnico/Especialista MDT (Laudo) | Médico (Pedido) / Responsável MDT (Laudo) | Enfermagem, RH, Finanças |
| **Internamento e Alta Médica** | Médico | Médico | Médico | Direção Administrativa, Enfermagem, Direção Geral |
| **Alocação / Higienização de Leito** | Enfermeiro-Chefe / Gestão Leitos | Enfermeiro-Chefe | Enfermeiro-Chefe / Serviços Gerais (Limpeza) | Finanças, Jurídico |
| **Escala de Turnos (Enfermagem)** | Enfermeiro-Chefe | Diretor de Enfermagem | Diretor de Enfermagem / RH | Médicos, Finanças |
| **Escala de Turnos (Médica)** | Chefe de Serviço Médico | Diretor Clínico | Diretor Clínico / RH | Enfermagem, Finanças |
| **Requisição Interna de Stock** | Enfermeiro-Chefe / Chefe Serviço | Farmácia / Logística (se há stock) ou Direção Técnica | Solicitante + Entregador (Armazém/Farmácia) | Receção, Relações Públicas |
| **Compra de Alto Valor / Contrato** | Compras e Aprovisionamento | Finanças + Jurídico + Auditoria Interna | Diretor Geral / Conselho de Administração | Médicos, Enfermeiros, Chefes de Setor |
| **Ordem de Pagamento / Empenho** | Finanças e Contabilidade | Diretor Administrativo e Financeiro / Diretor Geral | Diretor Administrativo / Diretor Geral | Direção Clínica, Direção Enfermagem |
| **Parecer Jurídico / Auditoria / Ética** | Direção Geral / Processo Interno | Instância Competente | Assessor Jurídico / Auditor / Comissão Ética | Operacionais de Atendimento |

---

## 8. Requisitos Não-Funcionais Críticos Derivados dos Processos

Para que o software reflita fielmente a realidade de um Hospital Público:

1. **Rastreabilidade Total (Audit Trail):** Toda criação, alteração, aprovação ou assinatura de documento (clínico ou financeiro) deve gravar `ID_Utilizador`, `Perfil_Ativo`, `Setor`, `Timestamp` e `IP/Dispositivo`.
2. **Segregação de Funções (SoD - Segregation of Duties):**
   * Quem solicita uma compra **não pode** ser o mesmo utilizador que aprova o orçamento nem o mesmo que confirma a receção física no armazém.
   * Quem prescreve um medicamento controlado **não deve** ser o mesmo utilizador que dispensa no stock da farmácia.
3. **Contingência de Emergência ("Break-the-Glass"):** Em casos de risco iminente de morte na Urgência ou UCI, o sistema deve permitir que um médico aceda a histórico clínico restrito mediante justificação obrigatória, gerando alerta automático para a Auditoria Interna e Comissão de Ética.
4. **Bloqueios Condicionais de Fluxo:**
   * Impedir alta administrativa sem antes existir registo de `Alta Médica` ou `Óbito`.
   * Impedir alocação de novo paciente numa cama com estado `AGUARDANDO_HIGIENIZACAO`.
   * Impedir dispensação de medicamentos controlados sem prescrição médica válida e assinada.
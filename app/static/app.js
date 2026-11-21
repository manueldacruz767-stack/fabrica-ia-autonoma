const estado = { token: localStorage.getItem("his_token"), usuario: null };

function escapeHtml(valor) {
  return String(valor ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function api(caminho, opcoes = {}) {
  const cabecalhos = { "Content-Type": "application/json" };
  if (estado.token) cabecalhos.Authorization = `Bearer ${estado.token}`;
  const resposta = await fetch(caminho, { ...opcoes, headers: { ...cabecalhos, ...(opcoes.headers || {}) } });
  let corpo = {};
  try { corpo = await resposta.json(); } catch (_) { corpo = {}; }
  if (!resposta.ok) throw new Error(corpo.detail || `Erro ${resposta.status}`);
  return corpo;
}

function mensagem(texto, erro = false) {
  const alvo = document.getElementById("mensagem");
  alvo.textContent = texto;
  alvo.className = erro ? "mensagem erro" : "mensagem";
}

function renderizar(id, colunas, linhas) {
  const alvo = document.getElementById(id);
  if (!linhas || !linhas.length) {
    alvo.innerHTML = "<p class='vazio'>Sem dados para apresentar.</p>";
    return;
  }
  const cabecalho = colunas.map((coluna) => `<th>${escapeHtml(coluna.titulo)}</th>`).join("");
  const corpo = linhas.map((linha) => (
    "<tr>" + colunas.map((coluna) => `<td>${escapeHtml(linha[coluna.chave])}</td>`).join("") + "</tr>"
  )).join("");
  alvo.innerHTML = `<table><thead><tr>${cabecalho}</tr></thead><tbody>${corpo}</tbody></table>`;
}

function preencherSelect(id, linhas, valor, texto, placeholder) {
  const seletor = document.getElementById(id);
  seletor.innerHTML = `<option value="">${placeholder}</option>` + linhas.map((linha) => (
    `<option value="${escapeHtml(linha[valor])}">${escapeHtml(linha[texto])}</option>`
  )).join("");
}

async function atualizarPropostas() {
  const cotacao = document.getElementById("selCotacao").value;
  const seletor = document.getElementById("selProposta");
  if (!seletor) return;
  if (!cotacao) {
    seletor.innerHTML = "<option value=''>Sem cotacao selecionada</option>";
    return;
  }
  try {
    const propostas = await api(`/api/cotacoes/${cotacao}/propostas`);
    seletor.innerHTML = propostas.map((proposta) => (
      `<option value="${escapeHtml(proposta.id)}">${escapeHtml(proposta.fornecedor)} - ${escapeHtml(proposta.valor)}</option>`
    )).join("") || "<option value=''>Sem propostas</option>";
  } catch (erro) {
    seletor.innerHTML = "<option value=''>Sem propostas</option>";
  }
}

function mostrarSecao(nome) {
  document.querySelectorAll(".secao").forEach((secao) => { secao.hidden = secao.id !== nome; });
  document.querySelectorAll("#navegacao button[data-secao]").forEach((botao) => {
    botao.classList.toggle("ativo", botao.dataset.secao === nome);
  });
}

async function carregar() {
  try {
    const [dashboard, pacientes, episodios, fila, leitos, stock, alertas] = await Promise.all([
      api("/api/dashboard"),
      api("/api/pacientes"),
      api("/api/episodios"),
      api("/api/fila"),
      api("/api/leitos"),
      api("/api/stock"),
      api("/api/alertas"),
    ]);

    document.getElementById("dashboard").innerHTML = Object.entries(dashboard).map(([chave, valor]) => (
      `<div class="cartao-metrica"><strong>${escapeHtml(valor)}</strong><span>${escapeHtml(chave.replaceAll("_", " "))}</span></div>`
    )).join("");

    renderizar("tabelaPacientes", [
      { titulo: "ID", chave: "id" },
      { titulo: "Nome", chave: "nome" },
      { titulo: "Documento", chave: "documento" },
      { titulo: "Desconhecido", chave: "desconhecido" },
    ], pacientes);

    renderizar("tabelaEpisodios", [
      { titulo: "ID", chave: "id" },
      { titulo: "Paciente", chave: "paciente_nome" },
      { titulo: "Tipo", chave: "tipo" },
      { titulo: "Estado", chave: "estado" },
      { titulo: "Cor", chave: "cor" },
    ], episodios);

    renderizar("tabelaFila", [
      { titulo: "Prioridade", chave: "prioridade" },
      { titulo: "Cor", chave: "cor" },
      { titulo: "Paciente", chave: "paciente_nome" },
      { titulo: "Estado", chave: "estado" },
      { titulo: "Triagem", chave: "triagem_em" },
    ], fila);

    renderizar("tabelaLeitos", [
      { titulo: "Codigo", chave: "codigo" },
      { titulo: "Unidade", chave: "unidade" },
      { titulo: "Estado", chave: "estado" },
      { titulo: "Episodio", chave: "episodio_id" },
    ], leitos);

    renderizar("tabelaStock", [
      { titulo: "Medicamento", chave: "medicamento" },
      { titulo: "Quantidade", chave: "quantidade" },
      { titulo: "Minimo", chave: "minimo" },
    ], stock);

    renderizar("listaAlertas", [
      { titulo: "Nivel", chave: "nivel" },
      { titulo: "Mensagem", chave: "mensagem" },
      { titulo: "Quando", chave: "criado_em" },
    ], alertas);

    const episodiosAbertos = episodios.filter((episodio) => ![
      "ALTA_ADMINISTRATIVA_CONCLUIDA", "FINALIZADO", "CANCELADO", "FALTOU", "TRANSFERIDO", "OBITO"
    ].includes(episodio.estado));

    preencherSelect("episPaciente", pacientes, "id", "nome", "Seleciona o paciente");
    for (const id of ["triEpisodio", "ateEpisodio", "preEpisodio", "acaoEpisodio", "aloEpisodio"]) {
      preencherSelect(id, episodiosAbertos, "id", "paciente_nome", "Seleciona o episodio");
    }
    preencherSelect("aloLeito", leitos.filter((leito) => leito.estado === "LIVRE"), "id", "codigo", "Seleciona o leito livre");

    const higienizacao = await api("/api/higienizacao").catch(() => []);
    renderizar("listaHigienizacao", [
      { titulo: "Tarefa", chave: "id" },
      { titulo: "Leito", chave: "codigo" },
      { titulo: "Estado", chave: "estado" },
    ], higienizacao);
    document.getElementById("listaHigienizacao").insertAdjacentHTML(
      "beforeend",
      higienizacao.filter((tarefa) => tarefa.estado === "PENDENTE").map((tarefa) => (
        `<button data-higienizacao="${escapeHtml(tarefa.id)}">Concluir higienizacao</button>`
      )).join("")
    );

    const prescricoes = await api("/api/prescricoes/pendentes").catch(() => []);
    renderizar("listaPrescricoes", [
      { titulo: "ID", chave: "id" },
      { titulo: "Medicamento", chave: "medicamento" },
      { titulo: "Dose", chave: "dose" },
    ], prescricoes);
    document.getElementById("listaPrescricoes").insertAdjacentHTML(
      "beforeend",
      prescricoes.map((prescricao) => (
        `<button data-dispensar="${escapeHtml(prescricao.id)}">Dispensar</button>`
      )).join("")
    );

    const [funcionarios, escalas, pedidosRh, requisicoes, empenhos, pedidosMdt, cirurgias, esterilizacoes, equipamentos, chamados] = await Promise.all([
      api("/api/rh/funcionarios").catch(() => []),
      api("/api/rh/escalas").catch(() => []),
      api("/api/rh/pedidos").catch(() => []),
      api("/api/compras/requisicoes").catch(() => []),
      api("/api/financeiro/empenhos").catch(() => []),
      api("/api/mdt/pedidos").catch(() => []),
      api("/api/cirurgias").catch(() => []),
      api("/api/esterilizacoes").catch(() => []),
      api("/api/equipamentos").catch(() => []),
      api("/api/manutencao/chamados").catch(() => []),
    ]);

    renderizar("tabelaFuncionarios", [
      { titulo: "ID", chave: "id" },
      { titulo: "Nome", chave: "nome" },
      { titulo: "Perfil", chave: "perfil_funcional" },
      { titulo: "Unidade", chave: "unidade" },
    ], funcionarios);

    renderizar("tabelaEscalas", [
      { titulo: "Data", chave: "data" },
      { titulo: "Funcionario", chave: "funcionario_nome" },
      { titulo: "Turno", chave: "turno" },
      { titulo: "Unidade", chave: "unidade" },
    ], escalas);

    renderizar("tabelaPedidosRh", [
      { titulo: "ID", chave: "id" },
      { titulo: "Funcionario", chave: "funcionario_nome" },
      { titulo: "Tipo", chave: "tipo" },
      { titulo: "Estado", chave: "estado" },
    ], pedidosRh);

    renderizar("tabelaRequisicoes", [
      { titulo: "ID", chave: "id" },
      { titulo: "Descricao", chave: "descricao" },
      { titulo: "Valor", chave: "valor" },
      { titulo: "Estado", chave: "estado" },
    ], requisicoes);

    renderizar("tabelaEmpenhos", [
      { titulo: "ID", chave: "id" },
      { titulo: "Descricao", chave: "descricao" },
      { titulo: "Valor", chave: "valor" },
      { titulo: "Estado", chave: "estado" },
    ], empenhos);

    renderizar("tabelaPedidosMdt", [
      { titulo: "ID", chave: "id" },
      { titulo: "Tipo", chave: "tipo" },
      { titulo: "Descricao", chave: "descricao" },
      { titulo: "Estado", chave: "estado" },
      { titulo: "Resultado", chave: "resultado" },
    ], pedidosMdt);

    renderizar("tabelaCirurgias", [
      { titulo: "ID", chave: "id" },
      { titulo: "Procedimento", chave: "descricao" },
      { titulo: "Estado", chave: "estado" },
    ], cirurgias);

    renderizar("tabelaEsterilizacoes", [
      { titulo: "Lote", chave: "lote" },
      { titulo: "Material", chave: "descricao" },
      { titulo: "Validade", chave: "validade" },
      { titulo: "Indicador", chave: "indicador_biologico" },
    ], esterilizacoes);

    renderizar("tabelaChamados", [
      { titulo: "ID", chave: "id" },
      { titulo: "Equipamento", chave: "equipamento_id" },
      { titulo: "Prioridade", chave: "prioridade" },
      { titulo: "Estado", chave: "estado" },
      { titulo: "SLA", chave: "sla" },
    ], chamados);

    preencherSelect("ambEpisodio", episodios.filter((episodio) => (
      episodio.tipo === "AMBULATORIO"
      && ["AGENDADO", "CHECK_IN_REALIZADO", "PRE_CONSULTA", "EM_CONSULTA"].includes(episodio.estado)
    )), "id", "paciente_nome", "Seleciona o episodio ambulatorial");
    preencherSelect("cirEpisodio", episodios.filter((episodio) => episodio.estado === "INTERNADO_ATIVO"), "id", "paciente_nome", "Seleciona o internamento");
    preencherSelect("cirSelecionada", cirurgias.filter((cirurgia) => cirurgia.estado === "EM_CIRURGIA"), "id", "descricao", "Seleciona a cirurgia");
    preencherSelect("cirEquipamento", equipamentos.filter((equipamento) => equipamento.estado === "ATIVO"), "id", "codigo", "Seleciona o equipamento");
    preencherSelect("manEquipamento", equipamentos, "id", "codigo", "Seleciona o equipamento");

    preencherSelect("escFuncionario", funcionarios, "id", "nome", "Seleciona o funcionario");
    preencherSelect("rhFuncionario", funcionarios, "id", "nome", "Seleciona o funcionario");
    preencherSelect("rhPedido", pedidosRh, "id", "id", "Seleciona o pedido");
    preencherSelect("reqSelecionada", requisicoes, "id", "descricao", "Seleciona a requisicao");
    preencherSelect("mdtPedido", pedidosMdt, "id", "id", "Seleciona o pedido MDT");
    preencherSelect("mdtEpisodio", episodiosAbertos, "id", "paciente_nome", "Seleciona o episodio");

    const [consultas, unidades, documentos, stockSetorial, contratos, cotacoes, folhas, pontos] = await Promise.all([
      api("/api/consultas").catch(() => []),
      api("/api/unidades").catch(() => []),
      api("/api/documentos/assinados").catch(() => []),
      api("/api/stock-setorial").catch(() => []),
      api("/api/contratos").catch(() => []),
      api("/api/cotacoes").catch(() => []),
      api("/api/rh/folhas-salario").catch(() => []),
      api("/api/rh/ponto").catch(() => []),
    ]);

    renderizar("tabelaConsultas", [
      { titulo: "ID", chave: "id" },
      { titulo: "Paciente", chave: "paciente" },
      { titulo: "Especialidade", chave: "especialidade" },
      { titulo: "Data", chave: "data_hora" },
      { titulo: "Estado", chave: "estado" },
    ], consultas);

    renderizar("tabelaUnidades", [
      { titulo: "Codigo", chave: "codigo" },
      { titulo: "Nome", chave: "nome" },
      { titulo: "Nivel", chave: "nivel" },
      { titulo: "Unidade pai", chave: "unidade_pai_codigo" },
    ], unidades);

    renderizar("tabelaDocumentos", [
      { titulo: "ID", chave: "id" },
      { titulo: "Tipo", chave: "tipo_documento" },
      { titulo: "Referencia", chave: "referencia_id" },
      { titulo: "Perfil", chave: "perfil_ativo" },
      { titulo: "Unidade", chave: "unidade_codigo" },
    ], documentos);

    renderizar("tabelaStockSetorial", [
      { titulo: "Unidade", chave: "unidade_codigo" },
      { titulo: "Item", chave: "item" },
      { titulo: "Quantidade", chave: "quantidade" },
      { titulo: "Minimo", chave: "minimo" },
    ], stockSetorial);

    renderizar("tabelaContratos", [
      { titulo: "ID", chave: "id" },
      { titulo: "Fornecedor", chave: "fornecedor" },
      { titulo: "Objeto", chave: "objeto" },
      { titulo: "Valor", chave: "valor" },
      { titulo: "Estado", chave: "estado" },
    ], contratos);

    renderizar("tabelaCotacoes", [
      { titulo: "ID", chave: "id" },
      { titulo: "Descricao", chave: "descricao" },
      { titulo: "Quantidade", chave: "quantidade" },
      { titulo: "Estimativa", chave: "estimativa" },
      { titulo: "Estado", chave: "estado" },
    ], cotacoes);

    renderizar("tabelaFolhas", [
      { titulo: "ID", chave: "id" },
      { titulo: "Funcionario", chave: "funcionario" },
      { titulo: "Mes", chave: "mes" },
      { titulo: "Liquido", chave: "liquido" },
      { titulo: "Estado", chave: "estado" },
    ], folhas);

    renderizar("tabelaPonto", [
      { titulo: "Funcionario", chave: "funcionario" },
      { titulo: "Data", chave: "data" },
      { titulo: "Entrada", chave: "entrada" },
      { titulo: "Saida", chave: "saida" },
    ], pontos);

    preencherSelect("agePaciente", pacientes, "id", "nome", "Seleciona o paciente");
    preencherSelect("ageConsulta", consultas.filter((consulta) => consulta.estado === "AGENDADO"), "id", "paciente", "Seleciona a consulta");
    preencherSelect("cuiEpisodio", episodiosAbertos, "id", "paciente_nome", "Seleciona o episodio");
    preencherSelect("propCotacao", cotacoes.filter((cotacao) => cotacao.estado !== "ADJUDICADA"), "id", "descricao", "Seleciona a cotacao");
    preencherSelect("selCotacao", cotacoes.filter((cotacao) => cotacao.estado !== "ADJUDICADA"), "id", "descricao", "Seleciona a cotacao");
    await atualizarPropostas();

    try {
      const saude = await fetch("/health").then((resposta) => resposta.json());
      document.getElementById("estadoSaude").textContent = `Servico ${saude.estado} - base ${saude.db} - versao ${saude.versao}`;
      const textoMetricas = await fetch("/metrics").then((resposta) => resposta.text());
      document.getElementById("metricasResumo").textContent = textoMetricas;
    } catch (_) {
      document.getElementById("estadoSaude").textContent = "Metricas indisponiveis";
    }

    const relatorioFinanceiro = await api("/api/financeiro/relatorio").catch(() => null);
    if (relatorioFinanceiro) {
      document.getElementById("resumoOrcamento").innerHTML = `
        <div class="grade-cartoes">
          <div class="cartao-metrica"><strong>${escapeHtml(relatorioFinanceiro.total)}</strong><span>Total</span></div>
          <div class="cartao-metrica"><strong>${escapeHtml(relatorioFinanceiro.executado)}</strong><span>Executado</span></div>
          <div class="cartao-metrica"><strong>${escapeHtml(relatorioFinanceiro.disponivel)}</strong><span>Disponivel</span></div>
          <div class="cartao-metrica"><strong>${escapeHtml(relatorioFinanceiro.valor_empenhado)}</strong><span>Empenhado</span></div>
        </div>`;
    }

    if (["auditoria", "administrador"].includes(estado.usuario.perfil)) {
      const [auditoria, eventos] = await Promise.all([api("/api/auditoria"), api("/api/eventos")]);
      renderizar("tabelaAuditoria", [
        { titulo: "Quando", chave: "criado_em" },
        { titulo: "Utilizador", chave: "user_id" },
        { titulo: "Acao", chave: "acao" },
        { titulo: "Alvo", chave: "alvo" },
        { titulo: "Hash", chave: "hash" },
      ], auditoria);
      renderizar("tabelaEventos", [
        { titulo: "Evento", chave: "evento" },
        { titulo: "Payload", chave: "payload" },
        { titulo: "Estado", chave: "estado" },
      ], eventos);
    }
  } catch (erro) {
    mensagem(erro.message, true);
  }
}

function iniciarSessao(dados) {
  estado.token = dados.token;
  estado.usuario = dados;
  localStorage.setItem("his_token", dados.token);
  document.getElementById("loginView").hidden = true;
  document.getElementById("appView").hidden = false;
  document.getElementById("sessao").textContent = `${dados.nome} (${dados.perfil})`;
  document.querySelectorAll("#navegacao button[data-perfis]").forEach((botao) => {
    const perfis = botao.dataset.perfis.split(",");
    botao.hidden = dados.perfil !== "administrador" && !perfis.includes(dados.perfil);
  });
  mostrarSecao("painel");
  carregar();
}

document.getElementById("formLogin").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  try {
    const dados = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: document.getElementById("loginUsername").value,
        password: document.getElementById("loginPassword").value,
      }),
    });
    document.getElementById("erroLogin").textContent = "";
    iniciarSessao(dados);
  } catch (erro) {
    document.getElementById("erroLogin").textContent = erro.message;
  }
});

document.querySelectorAll("#navegacao button[data-secao]").forEach((botao) => {
  botao.addEventListener("click", () => mostrarSecao(botao.dataset.secao));
});

document.getElementById("botaoSair").addEventListener("click", () => {
  localStorage.removeItem("his_token");
  location.reload();
});

const acoes = [
  ["formPaciente", "/api/pacientes", () => ({
    nome: document.getElementById("pacNome").value,
    documento: document.getElementById("pacDocumento").value || null,
    data_nascimento: document.getElementById("pacNascimento").value || null,
    desconhecido: document.getElementById("pacDesconhecido").checked,
  })],
  ["formEpisodio", "/api/episodios", () => ({
    paciente_id: document.getElementById("episPaciente").value,
    tipo: document.getElementById("episTipo").value,
  })],
  ["formTriagem", null, () => null],
  ["formAtendimento", null, () => null],
  ["formPrescricao", null, () => null],
  ["formAlocar", null, () => null],
  ["formStock", "/api/stock", () => ({
    medicamento: document.getElementById("stkMedicamento").value,
    quantidade: Number(document.getElementById("stkQuantidade").value),
    minimo: Number(document.getElementById("stkMinimo").value),
  })],
  ["formFuncionario", "/api/rh/funcionarios", () => ({
    nome: document.getElementById("funNome").value,
    perfil_funcional: document.getElementById("funPerfil").value,
    unidade: document.getElementById("funUnidade").value,
  })],
  ["formEscala", "/api/rh/escalas", () => ({
    staff_id: document.getElementById("escFuncionario").value,
    data: document.getElementById("escData").value,
    turno: document.getElementById("escTurno").value,
    unidade: document.getElementById("escUnidade").value,
  })],
  ["formPedidoRh", "/api/rh/pedidos", () => ({
    staff_id: document.getElementById("rhFuncionario").value,
    tipo: document.getElementById("rhTipo").value,
    inicio: document.getElementById("rhInicio").value,
    fim: document.getElementById("rhFim").value,
    justificacao: document.getElementById("rhJustificacao").value || null,
  })],
  ["formRequisicao", "/api/compras/requisicoes", () => ({
    descricao: document.getElementById("reqDescricao").value,
    quantidade: Number(document.getElementById("reqQuantidade").value),
    valor: Number(document.getElementById("reqValor").value),
    unidade: document.getElementById("reqUnidade").value,
  })],
  ["formOrcamento", "/api/financeiro/orcamento", () => ({
    total: Number(document.getElementById("orcTotal").value),
  })],
  ["formPedidoMdt", "/api/mdt/pedidos", () => ({
    episodio_id: document.getElementById("mdtEpisodio").value,
    tipo: document.getElementById("mdtTipo").value,
    descricao: document.getElementById("mdtDescricao").value,
  })],
  ["formPreConsulta", null, () => null],
  ["formCirurgia", null, () => null],
  ["formEsterilizacao", "/api/esterilizacoes", () => ({
    lote: document.getElementById("estLote").value,
    descricao: document.getElementById("estDescricao").value,
    esterilizado_em: document.getElementById("estData").value,
    validade: document.getElementById("estValidade").value,
    indicador_biologico: document.getElementById("estIndicador").value,
  })],
  ["formEquipamento", "/api/equipamentos", () => ({
    codigo: document.getElementById("eqCodigo").value,
    descricao: document.getElementById("eqDescricao").value,
    unidade: document.getElementById("eqUnidade").value,
    proxima_manutencao: document.getElementById("eqManutencao").value,
  })],
  ["formChamado", "/api/manutencao/chamados", () => ({
    equipamento_id: document.getElementById("manEquipamento").value,
    descricao: document.getElementById("manDescricao").value,
    prioridade: document.getElementById("manPrioridade").value,
  })],
  ["formAgenda", "/api/consultas", () => ({
    patient_id: document.getElementById("agePaciente").value,
    especialidade: document.getElementById("ageEspecialidade").value,
    medico_id: document.getElementById("ageMedico").value || null,
    data_hora: document.getElementById("ageData").value + ":00",
  })],
  ["formEvolucao", null, () => null],
  ["formBalanco", null, () => null],
  ["formSumario", null, () => null],
  ["formTransferencia", null, () => null],
  ["formObito", null, () => null],
  ["formMovimento", "/api/stock-setorial/movimentos", () => ({
    unidade_codigo: document.getElementById("movUnidade").value,
    item: document.getElementById("movItem").value,
    tipo: document.getElementById("movTipo").value,
    quantidade: Number(document.getElementById("movQuantidade").value),
    destino: document.getElementById("movDestino").value || null,
  })],
  ["formContrato", "/api/contratos", () => ({
    fornecedor: document.getElementById("ctrFornecedor").value,
    objeto: document.getElementById("ctrObjeto").value,
    valor: Number(document.getElementById("ctrValor").value),
    inicio: document.getElementById("ctrInicio").value,
    fim: document.getElementById("ctrFim").value,
  })],
  ["formCotacao", "/api/cotacoes", () => ({
    descricao: document.getElementById("cotDescricao").value,
    quantidade: Number(document.getElementById("cotQuantidade").value),
    estimativa: Number(document.getElementById("cotEstimativa").value),
  })],
  ["formProposta", null, () => null],
  ["formFolha", "/api/rh/folhas-salario", () => ({
    funcionario: document.getElementById("folFuncionario").value,
    mes: document.getElementById("folMes").value,
    salario_base: Number(document.getElementById("folBase").value),
    descontos: Number(document.getElementById("folDescontos").value),
  })],
  ["formPonto", "/api/rh/ponto", () => ({
    funcionario: document.getElementById("ptoFuncionario").value,
    data: document.getElementById("ptoData").value,
    entrada: document.getElementById("ptoEntrada").value,
    saida: document.getElementById("ptoSaida").value || null,
  })],
  ["formAssinatura", "/api/documentos/assinar", () => ({
    tipo_documento: document.getElementById("assTipo").value,
    referencia_id: document.getElementById("assReferencia").value,
    conteudo: document.getElementById("assConteudo").value,
  })],
];

for (const [idFormulario, caminho, corpo] of acoes) {
  document.getElementById(idFormulario).addEventListener("submit", async (evento) => {
    evento.preventDefault();
    try {
      if (caminho) {
        await api(caminho, { method: "POST", body: JSON.stringify(corpo()) });
      } else if (idFormulario === "formTriagem") {
        await api(`/api/episodios/${document.getElementById("triEpisodio").value}/triagem`, {
          method: "POST",
          body: JSON.stringify({
            queixa: document.getElementById("triQueixa").value,
            sinais_vitais: document.getElementById("triSinais").value,
            cor: document.getElementById("triCor").value,
          }),
        });
      } else if (idFormulario === "formAtendimento") {
        await api(`/api/episodios/${document.getElementById("ateEpisodio").value}/atendimento`, {
          method: "POST",
          body: JSON.stringify({
            anamnese: document.getElementById("ateAnamnese").value,
            hipotese: document.getElementById("ateHipotese").value,
          }),
        });
      } else if (idFormulario === "formPrescricao") {
        await api(`/api/episodios/${document.getElementById("preEpisodio").value}/prescricoes`, {
          method: "POST",
          body: JSON.stringify({
            medicamento: document.getElementById("preMedicamento").value,
            dose: document.getElementById("preDose").value,
          }),
        });
      } else if (idFormulario === "formAlocar") {
        await api(`/api/leitos/${document.getElementById("aloLeito").value}/alocar`, {
          method: "POST",
          body: JSON.stringify({ episodio_id: document.getElementById("aloEpisodio").value }),
        });
      } else if (idFormulario === "formPreConsulta") {
        await api(`/api/episodios/${document.getElementById("ambEpisodio").value}/pre-consulta`, {
          method: "POST",
          body: JSON.stringify({
            sinais_vitais: document.getElementById("preSinais").value,
            observacao: document.getElementById("preObs").value || null,
          }),
        });
      } else if (idFormulario === "formCirurgia") {
        await api(`/api/cirurgias?episodio_id=${document.getElementById("cirEpisodio").value}`, {
          method: "POST",
          body: JSON.stringify({
            descricao: document.getElementById("cirDescricao").value,
            checklist: document.getElementById("cirChecklist").value,
            equipamento_id: document.getElementById("cirEquipamento").value || null,
          }),
        });
      } else if (idFormulario === "formEvolucao") {
        await api(`/api/episodios/${document.getElementById("cuiEpisodio").value}/evolucoes`, {
          method: "POST",
          body: JSON.stringify({
            nota: document.getElementById("evoNota").value,
            conduta: document.getElementById("evoConduta").value,
            proxima_avaliacao: document.getElementById("evoProxima").value + ":00",
          }),
        });
      } else if (idFormulario === "formBalanco") {
        await api(`/api/episodios/${document.getElementById("cuiEpisodio").value}/balanco-hidrico`, {
          method: "POST",
          body: JSON.stringify({
            entradas_ml: Number(document.getElementById("balEntradas").value),
            saidas_ml: Number(document.getElementById("balSaidas").value),
            dieta: document.getElementById("balDieta").value,
            turno: document.getElementById("balTurno").value,
          }),
        });
      } else if (idFormulario === "formSumario") {
        await api(`/api/episodios/${document.getElementById("cuiEpisodio").value}/sumario-alta`, {
          method: "POST",
          body: JSON.stringify({
            diagnostico: document.getElementById("sumDiagnostico").value,
            evolucao: document.getElementById("sumEvolucao").value,
            orientacoes: document.getElementById("sumOrientacoes").value,
            medicamentos: document.getElementById("sumMedicamentos").value,
          }),
        });
      } else if (idFormulario === "formTransferencia") {
        await api(`/api/episodios/${document.getElementById("cuiEpisodio").value}/transferencia`, {
          method: "POST",
          body: JSON.stringify({
            destino: document.getElementById("transDestino").value,
            motivo: document.getElementById("transMotivo").value,
            veiculo: document.getElementById("transVeiculo").value,
          }),
        });
      } else if (idFormulario === "formObito") {
        await api(`/api/episodios/${document.getElementById("cuiEpisodio").value}/obito`, {
          method: "POST",
          body: JSON.stringify({
            causa: document.getElementById("obiCausa").value,
            data_obito: document.getElementById("obiData").value + ":00",
          }),
        });
      } else if (idFormulario === "formProposta") {
        await api(`/api/cotacoes/${document.getElementById("propCotacao").value}/propostas`, {
          method: "POST",
          body: JSON.stringify({
            fornecedor: document.getElementById("propFornecedor").value,
            valor: Number(document.getElementById("propValor").value),
            prazo: document.getElementById("propPrazo").value,
          }),
        });
      }
      evento.target.reset();
      mensagem("Acao registada com sucesso.");
      await carregar();
    } catch (erro) {
      mensagem(erro.message, true);
    }
  });
}

document.getElementById("botaoAlta").addEventListener("click", async () => {
  try {
    await api(`/api/episodios/${document.getElementById("acaoEpisodio").value}/alta-medica`, { method: "POST" });
    mensagem("Alta medica registada.");
    await carregar();
  } catch (erro) { mensagem(erro.message, true); }
});

document.getElementById("botaoAltaAdm").addEventListener("click", async () => {
  try {
    await api(`/api/episodios/${document.getElementById("acaoEpisodio").value}/alta-administrativa`, { method: "POST" });
    mensagem("Alta administrativa concluida.");
    await carregar();
  } catch (erro) { mensagem(erro.message, true); }
});

document.getElementById("botaoProntuario").addEventListener("click", async () => {
  try {
    const dados = await api(`/api/episodios/${document.getElementById("acaoEpisodio").value}/prontuario`);
    document.getElementById("prontuario").textContent = JSON.stringify(dados, null, 2);
  } catch (erro) { mensagem(erro.message, true); }
});

document.getElementById("botaoBreakGlass").addEventListener("click", async () => {
  try {
    await api("/api/acesso-emergencia", {
      method: "POST",
      body: JSON.stringify({
        episodio_id: document.getElementById("acaoEpisodio").value,
        justificacao: document.getElementById("breakJustificacao").value,
      }),
    });
    mensagem("Acesso de emergencia autorizado e auditado.");
    await carregar();
  } catch (erro) { mensagem(erro.message, true); }
});

document.getElementById("listaHigienizacao").addEventListener("click", async (evento) => {
  const botao = evento.target.closest("button[data-higienizacao]");
  if (!botao) return;
  try {
    await api(`/api/higienizacao/${botao.dataset.higienizacao}/concluir`, { method: "POST" });
    mensagem("Higienizacao concluida.");
    await carregar();
  } catch (erro) { mensagem(erro.message, true); }
});

document.getElementById("listaPrescricoes").addEventListener("click", async (evento) => {
  const botao = evento.target.closest("button[data-dispensar]");
  if (!botao) return;
  try {
    await api(`/api/prescricoes/${botao.dataset.dispensar}/dispensar`, { method: "POST" });
    mensagem("Medicacao dispensada.");
    await carregar();
  } catch (erro) { mensagem(erro.message, true); }
});

async function acaoBotao(id, caminho, corpo, texto) {
  document.getElementById(id).addEventListener("click", async () => {
    try {
      const opcoes = { method: "POST" };
      if (corpo) opcoes.body = JSON.stringify(corpo());
      await api(caminho(), opcoes);
      mensagem(texto);
      await carregar();
    } catch (erro) { mensagem(erro.message, true); }
  });
}

acaoBotao("botaoCheckIn", () => `/api/episodios/${document.getElementById("ambEpisodio").value}/check-in`, () => ({
  observacao: "Check-in registado na interface",
}), "Check-in registado.");

acaoBotao("botaoFinalizarConsulta", () => `/api/episodios/${document.getElementById("ambEpisodio").value}/finalizar`, null, "Consulta finalizada.");

acaoBotao("botaoConcluirCirurgia", () => `/api/cirurgias/${document.getElementById("cirSelecionada").value}/concluir`, () => ({
  destino: document.getElementById("cirDestino").value,
}), "Cirurgia concluida.");

acaoBotao("botaoAprovarRh", () => `/api/rh/pedidos/${document.getElementById("rhPedido").value}/aprovar`, () => ({
  parecer: document.getElementById("rhParecer").value,
  aprovado: true,
}), "Pedido aprovado na chefia.");

acaoBotao("botaoHomologarRh", () => `/api/rh/pedidos/${document.getElementById("rhPedido").value}/homologar`, null, "Pedido homologado no RH.");

acaoBotao("botaoValidarTecnica", () => `/api/compras/requisicoes/${document.getElementById("reqSelecionada").value}/validar-tecnica`, () => ({
  parecer: document.getElementById("reqParecer").value,
  aprovado: true,
}), "Validacao tecnica registada.");

acaoBotao("botaoVerificarOrcamento", () => `/api/compras/requisicoes/${document.getElementById("reqSelecionada").value}/verificar-orcamento`, null, "Cabimento verificado.");

acaoBotao("botaoParecer", () => `/api/compras/requisicoes/${document.getElementById("reqSelecionada").value}/parecer`, () => ({
  parecer: document.getElementById("reqParecer").value,
  aprovado: true,
}), "Parecer de conformidade registado.");

acaoBotao("botaoAprovarCompra", () => `/api/compras/requisicoes/${document.getElementById("reqSelecionada").value}/aprovar`, null, "Requisicao aprovada e empenhada.");

acaoBotao("botaoReceber", () => `/api/compras/requisicoes/${document.getElementById("reqSelecionada").value}/receber`, () => ({
  conferencia: document.getElementById("reqParecer").value || "Conferencia física conforme",
}), "Mercadoria recebida.");

acaoBotao("botaoResultadoMdt", () => `/api/mdt/pedidos/${document.getElementById("mdtPedido").value}/resultado`, () => ({
  resultado: document.getElementById("mdtResultado").value,
}), "Resultado MDT registado.");

acaoBotao("botaoValidarMdt", () => `/api/mdt/pedidos/${document.getElementById("mdtPedido").value}/validar`, null, "Resultado MDT validado.");

acaoBotao("botaoCheckInConsulta", () => `/api/consultas/${document.getElementById("ageConsulta").value}/check-in`, null, "Check-in registado.");

acaoBotao("botaoRetorno", () => `/api/consultas/${document.getElementById("ageConsulta").value}/retorno`, () => ({
  patient_id: "",
  especialidade: document.getElementById("ageEspecialidade").value,
  medico_id: document.getElementById("ageMedico").value || null,
  data_hora: document.getElementById("ageDataRetorno").value + ":00",
}), "Retorno agendado.");

acaoBotao("botaoSelecionarProposta", () => `/api/cotacoes/${document.getElementById("selCotacao").value}/selecionar?proposta_id=${document.getElementById("selProposta").value}`, null, "Proposta selecionada.");

acaoBotao("botaoPublicarEventos", () => "/api/eventos/publicar", null, "Eventos publicados.");

document.getElementById("botaoParecer").addEventListener("click", async () => {
  try {
    await api(`/api/compras/requisicoes/${document.getElementById("reqSelecionada").value}/pareceres`, {
      method: "POST",
      body: JSON.stringify({
        tipo: document.getElementById("reqTipoParecer").value,
        parecer: document.getElementById("reqParecer").value,
        aprovado: true,
      }),
    });
    mensagem("Parecer registado.");
    await carregar();
  } catch (erro) { mensagem(erro.message, true); }
});

document.getElementById("botaoVagas").addEventListener("click", async () => {
  try {
    const especialidade = encodeURIComponent(document.getElementById("ageEspecialidadeVagas").value);
    const data = document.getElementById("ageDataVagas").value;
    const resultado = await api(`/api/consultas/vagas?especialidade=${especialidade}&data=${data}`);
    document.getElementById("vagasConsulta").textContent = `${resultado.vagas} vagas disponiveis`;
  } catch (erro) { mensagem(erro.message, true); }
});

document.getElementById("selCotacao").addEventListener("change", atualizarPropostas);

async function restaurarSessao() {
  if (!estado.token) return;
  try {
    const dados = await api("/api/me");
    iniciarSessao({ ...dados, token: estado.token });
  } catch (_) {
    estado.token = null;
    estado.usuario = null;
    localStorage.removeItem("his_token");
  }
}

restaurarSessao();

const estado = { token: localStorage.getItem("his_token"), usuario: null };
let ultimoFormularioAtivo = null;
let riscoPendente = null;

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
  if (!resposta.ok) {
    const erro = new Error(corpo.detail || `Erro ${resposta.status}`);
    erro.status = resposta.status;
    throw erro;
  }
  return corpo;
}

function mensagem(texto, erro = false) {
  const alvo = document.getElementById("mensagem");
  alvo.textContent = texto;
  alvo.className = erro ? "mensagem erro" : "mensagem";
}

function abrirModalRisco(descricao, pedido) {
  riscoPendente = pedido;
  document.getElementById("descricaoRisco").textContent = descricao;
  document.getElementById("justificacaoRisco").value = "";
  document.getElementById("modalRisco").showModal();
  document.getElementById("justificacaoRisco").focus();
}

function fecharModalRisco(limparFormulario = false) {
  const modal = document.getElementById("modalRisco");
  if (modal && modal.open) modal.close();
  riscoPendente = null;
  if (limparFormulario && ultimoFormularioAtivo) ultimoFormularioAtivo.reset();
}

function preencherEquipamentoPorQr(texto) {
  const conteudo = (texto || "").trim();
  if (!conteudo) return;
  const codigo = conteudo.split(/[:/]/).pop().trim();
  const seletor = document.getElementById("manEquipamento");
  const opcao = Array.from(seletor.options).find((item) => (
    item.value === codigo || item.textContent.trim().toLowerCase() === codigo.toLowerCase()
  ));
  if (opcao) seletor.value = opcao.value;
}

function renderizarStockKanban(linhas) {
  const alvo = document.getElementById("tabelaStock");
  if (!linhas || !linhas.length) {
    alvo.innerHTML = "<p class='vazio'>Sem stock para apresentar.</p>";
    return;
  }
  alvo.innerHTML = linhas.map((item) => {
    const critico = Number(item.quantidade) <= Number(item.minimo);
    return `<article class="cartao-stock${critico ? " critico" : ""}" data-item-stock="${escapeHtml(item.medicamento)}">
      <h4>${escapeHtml(item.medicamento)}</h4>
      <p>Quantidade: <strong>${escapeHtml(item.quantidade)}</strong></p>
      <p>Minimo: ${escapeHtml(item.minimo)}</p>
      <button type="button" data-solicitar-stock="${escapeHtml(item.medicamento)}" data-minimo-stock="${escapeHtml(item.minimo)}">Solicitar</button>
    </article>`;
  }).join("");
}

async function carregarEvolucoes() {
  const episodio = document.getElementById("cuiEpisodio").value;
  const alvo = document.getElementById("listaEvolucoes");
  if (!episodio) {
    alvo.innerHTML = "<p class='vazio'>Seleciona um episodio para ver as evolucoes.</p>";
    return;
  }
  try {
    const evolucoes = await api(`/api/episodios/${encodeURIComponent(episodio)}/evolucoes`);
    alvo.innerHTML = evolucoes.length ? evolucoes.map((evolucao) => (
      `<article class="cartao-evolucao">
        <span class="marcador" aria-hidden="true"></span>
        <h4>${escapeHtml(evolucao.criado_em)}</h4>
        <p><strong>Nota:</strong> ${escapeHtml(evolucao.nota)}</p>
        <p><strong>Conduta:</strong> ${escapeHtml(evolucao.conduta)}</p>
        <p><strong>Proxima avaliacao:</strong> ${escapeHtml(evolucao.proxima_avaliacao)}</p>
        <p class="nota">Registado por ${escapeHtml(evolucao.autor)}</p>
      </article>`
    )).join("") : "<p class='vazio'>Sem evolucoes registadas.</p>";
  } catch (erro) { mensagem(erro.message, true); }
}

function aplicarPerfis(perfil) {
  document.querySelectorAll("#navegacao button[data-perfis]").forEach((botao) => {
    const perfis = botao.dataset.perfis.split(",").map((item) => item.trim()).filter(Boolean);
    botao.hidden = perfil !== "administrador" && !perfis.includes(perfil);
  });
}

function renderizar(id, colunas, linhas) {
  const alvo = document.getElementById(id);
  if (!linhas || !linhas.length) {
    alvo.innerHTML = "<p class='vazio'>Sem dados para apresentar.</p>";
    return;
  }
  const cabecalho = colunas.map((coluna) => `<th>${escapeHtml(coluna.titulo)}</th>`).join("");
  const corpo = linhas.map((linha) => (
    "<tr>" + colunas.map((coluna) => {
      const valor = escapeHtml(linha[coluna.chave]);
      const classe = coluna.classeCss ? ` class="${escapeHtml(coluna.classeCss(linha))}"` : "";
      return `<td${classe}>${valor}</td>`;
    }).join("") + "</tr>"
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

function parsearParametrosMdt(texto) {
  return (texto || "").split(";").map((bloco) => bloco.trim()).filter(Boolean).map((bloco) => {
    const [parametro, valor, unidade, valor_referencia, criticidade] = bloco.split("|").map((parte) => parte.trim());
    return { parametro, valor, unidade: unidade || null, valor_referencia: valor_referencia || null, criticidade: criticidade || "NORMAL" };
  }).filter((parametro) => parametro.parametro && parametro.valor);
}

async function verAprazamentos() {
  const prescricao = document.getElementById("aprPrescricao").value;
  if (!prescricao) {
    document.getElementById("listaAprazamentos").innerHTML = "<p class='vazio'>Sem prescricao selecionada.</p>";
    return;
  }
  try {
    const aprazamentos = await api(`/api/prescricoes/${prescricao}/aprazamentos`);
    renderizar("listaAprazamentos", [
      { titulo: "ID", chave: "id" },
      { titulo: "Horario", chave: "horario" },
      { titulo: "Estado", chave: "estado" },
    ], aprazamentos);
    document.getElementById("listaAprazamentos").insertAdjacentHTML(
      "beforeend",
      aprazamentos.filter((aprazamento) => aprazamento.estado === "PENDENTE").map((aprazamento) => (
        `<button data-administrar="${escapeHtml(aprazamento.id)}">Administrar</button>`
      )).join("")
    );
  } catch (erro) { mensagem(erro.message, true); }
}

async function carregarDietas() {
  const episodio = document.getElementById("cuiEpisodio").value;
  if (!episodio) return;
  try {
    const dietas = await api(`/api/episodios/${episodio}/nutricao`);
    renderizar("tabelaDietas", [
      { titulo: "Dieta", chave: "dieta" },
      { titulo: "Observacao", chave: "observacao" },
      { titulo: "Prescrita por", chave: "prescrita_por" },
    ], dietas);
  } catch (_) { }
}

function mostrarSecao(nome) {
  document.querySelectorAll(".secao").forEach((secao) => { secao.hidden = secao.id !== nome; });
  const botaoAtivo = document.querySelector(`#navegacao button[data-secao="${nome}"]`);
  document.querySelectorAll("#navegacao button[data-secao]").forEach((botao) => {
    const ativo = botao.dataset.secao === nome;
    botao.classList.toggle("ativo", ativo);
    if (ativo) botao.setAttribute("aria-current", "page");
    else botao.removeAttribute("aria-current");
  });
  document.getElementById("breadcrumb").textContent = `HIS > ${botaoAtivo ? botaoAtivo.textContent : nome}`;
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
      { titulo: "Cor", chave: "cor", classeCss: (linha) => `manchester-${linha.cor}` },
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

    renderizarStockKanban(stock);

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
    await carregarEvolucoes();
    preencherSelect("propCotacao", cotacoes.filter((cotacao) => cotacao.estado !== "ADJUDICADA"), "id", "descricao", "Seleciona a cotacao");
    preencherSelect("selCotacao", cotacoes.filter((cotacao) => cotacao.estado !== "ADJUDICADA"), "id", "descricao", "Seleciona a cotacao");
    await atualizarPropostas();

    const [guias, concursos, ordensFornecimento, ordensPagamento, contratosTrabalho, servicos, senhas] = await Promise.all([
      api("/api/logistica/guias-remessa").catch(() => []),
      api("/api/compras/concursos").catch(() => []),
      api("/api/compras/ordens-fornecimento").catch(() => []),
      api("/api/financeiro/ordens-pagamento").catch(() => []),
      api("/api/rh/contratos-trabalho").catch(() => []),
      api("/api/servicos-gerais").catch(() => []),
      api("/api/painel/senhas").catch(() => []),
    ]);

    renderizar("tabelaGuias", [
      { titulo: "ID", chave: "id" },
      { titulo: "Origem", chave: "unidade_origem" },
      { titulo: "Destino", chave: "unidade_destino" },
      { titulo: "Item", chave: "item" },
      { titulo: "Estado", chave: "estado" },
    ], guias);

    renderizar("tabelaConcursos", [
      { titulo: "ID", chave: "id" },
      { titulo: "Numero", chave: "numero" },
      { titulo: "Cotacao", chave: "cotacao_id" },
      { titulo: "Estado", chave: "estado" },
    ], concursos);

    renderizar("tabelaOrdensFornecimento", [
      { titulo: "ID", chave: "id" },
      { titulo: "Fornecedor", chave: "fornecedor" },
      { titulo: "Descricao", chave: "descricao" },
      { titulo: "Estado", chave: "estado" },
    ], ordensFornecimento);

    renderizar("tabelaOrdensPagamento", [
      { titulo: "ID", chave: "id" },
      { titulo: "Fornecedor", chave: "fornecedor" },
      { titulo: "Valor", chave: "valor" },
      { titulo: "Estado", chave: "estado" },
    ], ordensPagamento);

    renderizar("tabelaContratosTrabalho", [
      { titulo: "ID", chave: "id" },
      { titulo: "Funcionario", chave: "staff_id" },
      { titulo: "Tipo", chave: "tipo" },
      { titulo: "Salario", chave: "salario_base" },
    ], contratosTrabalho);

    renderizar("tabelaServicos", [
      { titulo: "ID", chave: "id" },
      { titulo: "Area", chave: "area" },
      { titulo: "Descricao", chave: "descricao" },
      { titulo: "Estado", chave: "estado" },
    ], servicos);

    preencherSelect("cirLote", esterilizacoes.filter((lote) => lote.validade >= new Date().toISOString().slice(0, 10) && lote.indicador_biologico.toUpperCase() === "NEGATIVO"), "id", "lote", "Sem lote valido");
    preencherSelect("conCotacao", cotacoes, "id", "descricao", "Seleciona a cotacao");
    preencherSelect("ofeRequisicao", requisicoes, "id", "descricao", "Seleciona a requisicao");
    preencherSelect("ordRequisicao", requisicoes, "id", "descricao", "Seleciona a requisicao");
    preencherSelect("ctFuncionario", funcionarios, "id", "nome", "Seleciona o funcionario");
    preencherSelect("folProcessar", folhas, "id", "id", "Seleciona a folha");
    preencherSelect("alePaciente", pacientes, "id", "nome", "Seleciona o paciente");
    preencherSelect("senhaChamar", senhas.filter((senha) => senha.estado === "AGUARDANDO"), "id", "senha", "Sem senhas");
    preencherSelect("aprPrescricao", prescricoes, "id", "medicamento", "Seleciona a prescricao");

    const alergias = await Promise.all(pacientes.slice(0, 30).map((paciente) => api(`/api/pacientes/${paciente.id}/alergias`).catch(() => [])));
    renderizar("tabelaAlergias", [
      { titulo: "Paciente", chave: "patient_id" },
      { titulo: "Substancia", chave: "substancia" },
      { titulo: "Reacao", chave: "reacao" },
    ], alergias.flat());

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
  aplicarPerfis(dados.perfil);
  mostrarSecao("painel");
  carregar();
  ligarPainelTempoReal();
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
  botao.addEventListener("click", () => {
    mostrarSecao(botao.dataset.secao);
    if (botao.dataset.secao === "cuidados") carregarDietas();
  });
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
    parametros: parsearParametrosMdt(document.getElementById("mdtParametros").value),
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
  ["formAlergia", null, () => null],
  ["formGuia", "/api/logistica/guias-remessa", () => ({
    unidade_destino: document.getElementById("guiDestino").value,
    item: document.getElementById("guiItem").value,
    quantidade: Number(document.getElementById("guiQuantidade").value),
  })],
  ["formConcurso", "/api/compras/concursos", () => ({
    cotacao_id: document.getElementById("conCotacao").value,
    numero: document.getElementById("conNumero").value,
  })],
  ["formOrdemFornecimento", "/api/compras/ordens-fornecimento", () => ({
    purchase_id: document.getElementById("ofeRequisicao").value,
    descricao: document.getElementById("ofeDescricao").value,
    quantidade: Number(document.getElementById("ofeQuantidade").value),
  })],
  ["formContratoTrabalho", "/api/rh/contratos-trabalho", () => ({
    staff_id: document.getElementById("ctFuncionario").value,
    tipo: document.getElementById("ctTipo").value,
    inicio: document.getElementById("ctInicio").value,
    fim: document.getElementById("ctFim").value || null,
    salario_base: Number(document.getElementById("ctSalario").value),
  })],
  ["formServicoGeral", "/api/servicos-gerais", () => ({
    area: document.getElementById("srvArea").value,
    descricao: document.getElementById("srvDescricao").value,
  })],
];

for (const [idFormulario, caminho, corpo] of acoes) {
  document.getElementById(idFormulario).addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ultimoFormularioAtivo = evento.target;
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
        const pedido = {
          medicamento: document.getElementById("preMedicamento").value,
          dose: document.getElementById("preDose").value,
          justificacao_risco: document.getElementById("preJustificacao").value || null,
          horarios: document.getElementById("preHorarios").value.split(",").map((valor) => valor.trim()).filter(Boolean),
          dieta: document.getElementById("preDieta").value || null,
        };
        const caminhoPrescricao = `/api/episodios/${document.getElementById("preEpisodio").value}/prescricoes`;
        try {
          await api(caminhoPrescricao, { method: "POST", body: JSON.stringify(pedido) });
        } catch (erro) {
          if (erro.status !== 409) throw erro;
          abrirModalRisco(erro.message, { caminho: caminhoPrescricao, corpo: pedido });
          return;
        }
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
            lote_id: document.getElementById("cirLote").value || null,
          }),
        });
      } else if (idFormulario === "formAlergia") {
        await api(`/api/pacientes/${document.getElementById("alePaciente").value}/alergias`, {
          method: "POST",
          body: JSON.stringify({
            substancia: document.getElementById("aleSubstancia").value,
            reacao: document.getElementById("aleReacao").value,
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

document.getElementById("botaoVerAprazamentos").addEventListener("click", verAprazamentos);
document.getElementById("cuiEpisodio").addEventListener("change", () => {
  carregarDietas();
  carregarEvolucoes();
});

document.getElementById("listaAprazamentos").addEventListener("click", async (evento) => {
  const botao = evento.target.closest("button[data-administrar]");
  if (!botao) return;
  try {
    await api(`/api/aprazamentos/${botao.dataset.administrar}/administrar`, { method: "POST" });
    mensagem("Aprazamento administrado.");
    await verAprazamentos();
  } catch (erro) { mensagem(erro.message, true); }
});

acaoBotao("botaoProcessarFolha", () => `/api/folhas-salario/${document.getElementById("folProcessar").value}/processar`, null, "Folha processada com contrato e faltas.");
acaoBotao("botaoOrdemPagamento", () => `/api/financeiro/ordens-pagamento`, () => ({
  purchase_id: document.getElementById("ordRequisicao").value,
}), "Ordem de pagamento assinada.");
acaoBotao("botaoChamarSenha", () => `/api/painel/chamar?senha_id=${document.getElementById("senhaChamar").value}`, null, "Senha chamada.");

document.getElementById("botaoRecibo").addEventListener("click", async () => {
  try {
    const resposta = await fetch(`/api/recibos/${document.getElementById("folProcessar").value}`, {
      headers: { Authorization: `Bearer ${estado.token}` },
    });
    if (!resposta.ok) throw new Error("Sem permissao para este recibo");
    const janela = window.open("", "_blank");
    janela.document.write(await resposta.text());
    janela.document.close();
  } catch (erro) { mensagem(erro.message, true); }
});

document.getElementById("botaoReciboPdf").addEventListener("click", async () => {
  try {
    const folhaId = document.getElementById("folProcessar").value;
    if (!folhaId) {
      mensagem("Seleciona uma folha para gerar o recibo.", true);
      return;
    }
    const resposta = await fetch(`/api/recibos/${encodeURIComponent(folhaId)}/pdf`, {
      headers: { Authorization: `Bearer ${estado.token}` },
    });
    if (!resposta.ok) throw new Error("Sem permissao para este recibo");
    const bytes = await resposta.arrayBuffer();
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (erro) { mensagem(erro.message, true); }
});

document.getElementById("modalRisco").addEventListener("cancel", () => fecharModalRisco(true));
document.getElementById("botaoCancelarRisco").addEventListener("click", () => fecharModalRisco(true));
document.getElementById("botaoConfirmarRisco").addEventListener("click", async () => {
  if (!riscoPendente) return;
  const justificacao = document.getElementById("justificacaoRisco").value.trim();
  if (justificacao.length < 10) {
    mensagem("A justificacao de risco deve ter pelo menos 10 caracteres.", true);
    return;
  }
  riscoPendente.corpo.justificacao_risco = justificacao;
  document.getElementById("preJustificacao").value = justificacao;
  try {
    await api(riscoPendente.caminho, { method: "POST", body: JSON.stringify(riscoPendente.corpo) });
    fecharModalRisco();
    mensagem("Prescricao com risco confirmada e justificada.");
    document.getElementById("formPrescricao").reset();
    await carregar();
  } catch (erro) { mensagem(erro.message, true); }
});

document.getElementById("manQr").addEventListener("input", (evento) => preencherEquipamentoPorQr(evento.target.value));
document.getElementById("manQr").addEventListener("paste", (evento) => {
  preencherEquipamentoPorQr((evento.clipboardData || window.clipboardData).getData("text"));
});

document.getElementById("tabelaStock").addEventListener("click", (evento) => {
  const botao = evento.target.closest("button[data-solicitar-stock]");
  if (!botao) return;
  document.getElementById("stkMedicamento").value = botao.dataset.solicitarStock;
  document.getElementById("stkQuantidade").value = botao.dataset.minimoStock;
  document.getElementById("stkMinimo").value = botao.dataset.minimoStock;
  document.getElementById("stkMedicamento").focus();
  mensagem(`Reposicao de ${botao.dataset.solicitarStock} preparada.`);
});

document.addEventListener("focusin", (evento) => {
  const formulario = evento.target.closest("form");
  if (formulario) ultimoFormularioAtivo = formulario;
});

for (const [idBotao, formato] of [["botaoExportarHl7", "HL7"], ["botaoExportarFhir", "FHIR"]]) {
  document.getElementById(idBotao).addEventListener("click", async () => {
    try {
      const resultado = await api(`/api/mdt/pedidos/${document.getElementById("mdtPedido").value}/exportar?formato=${formato}`);
      document.getElementById("mdtExportado").textContent = typeof resultado.conteudo === "string"
        ? resultado.conteudo
        : JSON.stringify(resultado.conteudo, null, 2);
    } catch (erro) { mensagem(erro.message, true); }
  });
}

document.getElementById("botaoIndicadoresBi").addEventListener("click", async () => {
  try {
    document.getElementById("biResumo").textContent = JSON.stringify(await api("/api/bi/indicadores"), null, 2);
  } catch (erro) { mensagem(erro.message, true); }
});

document.getElementById("botaoExportarAuditoria").addEventListener("click", async () => {
  try {
    const resultado = await api("/api/auditoria/exportar?formato=csv");
    document.getElementById("auditoriaExportada").textContent = resultado.conteudo;
  } catch (erro) { mensagem(erro.message, true); }
});

function ligarPainelTempoReal() {
  const protocolo = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocolo}://${location.host}/ws/painel`);
  const painel = document.getElementById("painelChamadas");
  socket.onmessage = (evento) => {
    try {
      const dados = JSON.parse(evento.data);
      if (dados.evento === "SenhaChamada") {
        painel.innerHTML = `<span>${escapeHtml(dados.senha)}</span>`;
        mensagem(`Senha ${dados.senha} chamada.`);
      }
    } catch (_) { }
  };
  socket.onclose = () => { setTimeout(ligarPainelTempoReal, 3000); };
}

document.addEventListener("keydown", (evento) => {
  const modal = document.getElementById("modalRisco");
  if (evento.key === "Escape" && modal && modal.open) {
    evento.preventDefault();
    fecharModalRisco(true);
    return;
  }
  if (!evento.ctrlKey || !evento.altKey) return;
  const tecla = evento.key.toUpperCase();
  const destinos = { N: "pacientes", P: "episodios", S: "cuidados" };
  if (destinos[tecla]) {
    evento.preventDefault();
    mostrarSecao(destinos[tecla]);
  }
});

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

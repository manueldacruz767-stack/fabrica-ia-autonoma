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

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ESTATICO = RAIZ / "app" / "static"
HTML = (ESTATICO / "index.html").read_text(encoding="utf-8")
JS = (ESTATICO / "app.js").read_text(encoding="utf-8")
CSS = (ESTATICO / "style.css").read_text(encoding="utf-8")
PDF = (RAIZ / "app" / "pdf.py").read_text(encoding="utf-8")
ROUTER = (RAIZ / "app" / "relatorios_router.py").read_text(encoding="utf-8")


class TestesEstruturaInterface(unittest.TestCase):
    def test_modal_risco_com_aria(self):
        self.assertIn('id="modalRisco"', HTML)
        self.assertIn('role="alertdialog"', HTML)
        self.assertIn('aria-modal="true"', HTML)
        self.assertIn('aria-labelledby="tituloRisco"', HTML)
        self.assertIn('aria-describedby="descricaoRisco"', HTML)
        for identificador in ("descricaoRisco", "justificacaoRisco", "botaoConfirmarRisco", "botaoCancelarRisco"):
            self.assertIn(f'id="{identificador}"', HTML)

    def test_timeline_wizard_kanban_e_qr(self):
        self.assertIn('id="listaEvolucoes" class="timeline"', HTML)
        self.assertIn('id="tabelaStock" class="kanban"', HTML)
        self.assertIn('id="manQr"', HTML)
        self.assertIn('class="qr-help"', HTML)
        self.assertGreaterEqual(HTML.count('class="wizard"'), 2)
        for identificador in ("formTransferencia", "formObito", "botaoAlta", "botaoAltaAdm"):
            self.assertIn(f'id="{identificador}"', HTML)

    def test_botao_pdf_sem_substituir_html(self):
        self.assertIn('id="botaoRecibo"', HTML)
        self.assertIn('id="botaoReciboPdf"', HTML)

    def test_ids_originais_preservados(self):
        identificadores = (
            "formLogin", "loginUsername", "loginPassword", "erroLogin", "sessao", "breadcrumb",
            "navegacao", "botaoSair", "mensagem", "painel", "dashboard", "formPaciente", "pacNome",
            "tabelaPacientes", "formEpisodio", "episPaciente", "formTriagem", "triEpisodio",
            "formAtendimento", "ateEpisodio", "formPrescricao", "preEpisodio", "preJustificacao",
            "acaoEpisodio", "botaoProntuario", "prontuario", "tabelaEpisodios", "formAlocar",
            "aloLeito", "tabelaLeitos", "tabelaStock", "listaPrescricoes", "listaAlertas",
            "formEquipamento", "manEquipamento", "manDescricao", "formChamado", "tabelaChamados",
            "cuiEpisodio", "formEvolucao", "formTransferencia", "formObito", "formAlergia",
            "folProcessar", "botaoRecibo", "botaoProcessarFolha", "tabelaFolhas",
        )
        for identificador in identificadores:
            with self.subTest(identificador=identificador):
                self.assertIn(f'id="{identificador}"', HTML)


class TestesComportamentoJs(unittest.TestCase):
    def test_escape_e_limpeza_do_formulario(self):
        self.assertIn('evento.key === "Escape"', JS)
        self.assertIn("fecharModalRisco(true)", JS)
        self.assertIn("ultimoFormularioAtivo", JS)
        self.assertIn("ultimoFormularioAtivo.reset()", JS)

    def test_risco_409_com_justificacao(self):
        self.assertIn("erro.status !== 409", JS)
        self.assertIn("abrirModalRisco(erro.message", JS)
        self.assertIn("justificacao_risco", JS)
        self.assertIn("riscoPendente.corpo.justificacao_risco = justificacao", JS)
        self.assertIn("botaoConfirmarRisco", JS)

    def test_timeline_e_kanban_renderizados(self):
        self.assertIn("carregarEvolucoes", JS)
        self.assertIn("cartao-evolucao", JS)
        self.assertIn("renderizarStockKanban", JS)
        self.assertIn("data-item-stock", JS)
        self.assertIn("data-solicitar-stock", JS)
        self.assertIn("Solicitar</button>", JS)
        self.assertIn("stkMedicamento", JS)

    def test_qr_e_perfis(self):
        self.assertIn("preencherEquipamentoPorQr", JS)
        self.assertIn('getElementById("manQr").addEventListener("paste"', JS)
        self.assertIn("aplicarPerfis", JS)
        self.assertIn('button[data-perfis]', JS)
        self.assertIn('setAttribute("aria-current", "page")', JS)

    def test_recibo_pdf_via_blob(self):
        self.assertIn("/api/recibos/${encodeURIComponent(folhaId)}/pdf", JS)
        self.assertIn("await resposta.arrayBuffer()", JS)
        self.assertIn("new Blob([bytes], { type: \"application/pdf\" })", JS)
        self.assertIn("URL.createObjectURL", JS)
        self.assertIn("botaoReciboPdf", JS)

    def test_atalhos_mantidos(self):
        for trecho in ("ctrlKey", "altKey", 'N: "pacientes"', 'P: "episodios"', 'S: "cuidados"'):
            self.assertIn(trecho, JS)


class TestesEstiloERegras(unittest.TestCase):
    def test_responsividade_tablet(self):
        self.assertIn("@media (max-width: 900px)", CSS)
        self.assertIn("grid-template-columns: 1fr", CSS)

    def test_alvos_de_toque_e_foco(self):
        self.assertIn("min-height: 44px", CSS)
        self.assertIn(":focus-visible", CSS)
        self.assertIn("outline-offset: 2px", CSS)

    def test_novos_estilos(self):
        for seletor in (".timeline", ".wizard", ".kanban", ".cartao-stock", ".qr-help", ".modal-erro"):
            with self.subTest(seletor=seletor):
                self.assertIn(seletor, CSS)

    def test_cores_manchester_preservadas(self):
        for cor in ("#D32F2F", "#F57C00", "#FBC02D", "#388E3C", "#1976D2"):
            self.assertIn(cor, CSS)

    def test_backend_sem_dependencias_externas(self):
        self.assertTrue(PDF.startswith("import textwrap") or "import textwrap" in PDF)
        self.assertNotIn("reportlab", PDF)
        self.assertNotIn("pyotp", PDF)
        self.assertIn("def gerar_pdf_recibo(dados: dict) -> bytes:", PDF)
        self.assertIn('APIRouter(prefix="/api/recibos", tags=["relatorios"])', ROUTER)


if __name__ == "__main__":
    unittest.main()

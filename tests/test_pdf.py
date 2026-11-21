import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

DIRETORIO_TESTE = tempfile.mkdtemp(prefix="his-pdf-test-")
os.environ["HIS_DB_PATH"] = str(Path(DIRETORIO_TESTE) / "his.db")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db
from app.pdf import escapar_texto_pdf, gerar_pdf_recibo
from app.relatorios_router import router as relatorios_router
from app.security import usuario_atual

DADOS_FOLHA = {
    "id": "FOL-TESTE-01",
    "funcionario": "Maria Costa",
    "mes": "202601",
    "salario_base": 2500.0,
    "descontos": 375.5,
    "liquido": 2124.5,
    "estado": "PROCESSADA",
}


class TestesGeradorPdf(unittest.TestCase):
    def test_cabecalho_e_rodape(self):
        pdf = gerar_pdf_recibo(DADOS_FOLHA)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))

    def test_dados_do_recibo_presentes(self):
        pdf = gerar_pdf_recibo(DADOS_FOLHA)
        for valor in (b"FOL-TESTE-01", b"Maria Costa", b"202601", b"2500.00", b"2124.50"):
            self.assertIn(valor, pdf)
        self.assertIn("PROCESSADA".encode("ascii"), pdf)

    def test_escape_de_parenteses_e_acentos(self):
        escapado = escapar_texto_pdf("Acao (risco) \\ importante")
        self.assertIn(b"Acao \\(risco\\) \\\\ importante", escapado)
        self.assertIn("Ação".encode("cp1252"), escapar_texto_pdf("Ação"))

    def test_multiplas_linhas_e_stream_valido(self):
        dados = dict(DADOS_FOLHA)
        dados["observacao"] = "Texto longo " * 30
        pdf = gerar_pdf_recibo(dados)
        stream = pdf.split(b"stream\n", 1)[1].split(b"endstream", 1)[0]
        self.assertIn(f"/Length {len(stream)}".encode("ascii"), pdf)
        self.assertGreater(stream.count(b" Tj"), 10)
        self.assertIn(b"Helvetica", pdf)
        self.assertIn(b"Helvetica-Bold", pdf)

    def test_tabela_xref_valida(self):
        pdf = gerar_pdf_recibo(DADOS_FOLHA)
        inicio = int(pdf.rsplit(b"startxref\n", 1)[1].split(b"\n", 1)[0])
        linhas = pdf[inicio:].split(b"\n")
        self.assertEqual(linhas[0], b"xref")
        total = int(linhas[1].split()[1])
        self.assertEqual(total, 7)
        for numero in range(1, total):
            deslocamento = int(linhas[2 + numero].split()[0])
            self.assertTrue(pdf[deslocamento:].startswith(f"{numero} 0 obj".encode("ascii")))


class TestesRotaReciboPdf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.inicializar()
        conexao = db.ligacao()
        try:
            conexao.execute(
                "INSERT OR REPLACE INTO folhas_salario "
                "(id, funcionario, mes, salario_base, descontos, liquido, estado, criado_por, criado_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    DADOS_FOLHA["id"], DADOS_FOLHA["funcionario"], DADOS_FOLHA["mes"],
                    DADOS_FOLHA["salario_base"], DADOS_FOLHA["descontos"], DADOS_FOLHA["liquido"],
                    DADOS_FOLHA["estado"], "rh", db.agora(),
                ),
            )
            conexao.commit()
        finally:
            conexao.close()
        cls.aplicativo = FastAPI()
        cls.aplicativo.include_router(relatorios_router)
        cls.cliente = TestClient(cls.aplicativo)

    def tearDown(self):
        self.aplicativo.dependency_overrides.clear()

    def test_rota_devolve_pdf_para_perfil_autorizado(self):
        self.aplicativo.dependency_overrides[usuario_atual] = lambda: {
            "id": "rh", "nome": "RH", "perfil": "rh", "unidade_codigo": "DG",
        }
        resposta = self.cliente.get("/api/recibos/FOL-TESTE-01/pdf")
        self.assertEqual(resposta.status_code, 200, resposta.text)
        self.assertEqual(resposta.headers["content-type"], "application/pdf")
        self.assertIn("attachment;", resposta.headers["content-disposition"])
        self.assertTrue(resposta.content.startswith(b"%PDF-"))
        self.assertIn(b"Maria Costa", resposta.content)

    def test_rota_negada_a_perfil_nao_autorizado(self):
        self.aplicativo.dependency_overrides[usuario_atual] = lambda: {
            "id": "medico", "nome": "Medico", "perfil": "medico", "unidade_codigo": "URG",
        }
        resposta = self.cliente.get("/api/recibos/FOL-TESTE-01/pdf")
        self.assertEqual(resposta.status_code, 403)

    def test_rota_folha_inexistente(self):
        self.aplicativo.dependency_overrides[usuario_atual] = lambda: {
            "id": "auditor", "nome": "Auditoria", "perfil": "auditoria", "unidade_codigo": "AUD",
        }
        resposta = self.cliente.get("/api/recibos/INEXISTENTE/pdf")
        self.assertEqual(resposta.status_code, 404)


if __name__ == "__main__":
    unittest.main()

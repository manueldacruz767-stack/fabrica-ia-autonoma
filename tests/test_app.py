import os
import tempfile
import unittest

DIRETORIO_TESTE = tempfile.mkdtemp(prefix="his-test-")
os.environ["HIS_DB_PATH"] = os.path.join(DIRETORIO_TESTE, "his.db")

from fastapi.testclient import TestClient

from app.main import app


class TestesAppHospitalar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = TestClient(app)

    def token(self, username: str, senha: str) -> str:
        resposta = self.cliente.post("/api/auth/login", json={"username": username, "password": senha})
        self.assertEqual(resposta.status_code, 200, resposta.text)
        return resposta.json()["token"]

    def cabecalho(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def criar_paciente(self, token: str, nome: str = "Paciente Teste") -> str:
        resposta = self.cliente.post(
            "/api/pacientes",
            headers=self.cabecalho(token),
            json={"nome": nome, "desconhecido": True},
        )
        self.assertEqual(resposta.status_code, 201, resposta.text)
        return resposta.json()["id"]

    def criar_episodio(self, token: str, paciente_id: str) -> str:
        resposta = self.cliente.post(
            "/api/episodios",
            headers=self.cabecalho(token),
            json={"paciente_id": paciente_id, "tipo": "URGENCIA"},
        )
        self.assertEqual(resposta.status_code, 201, resposta.text)
        return resposta.json()["id"]

    def test_login_e_rbac(self):
        medico = self.token("medico", "medico123")
        eu = self.cliente.get("/api/me", headers=self.cabecalho(medico))
        self.assertEqual(eu.json()["perfil"], "medico")
        negado = self.cliente.get("/api/auditoria", headers=self.cabecalho(medico))
        self.assertEqual(negado.status_code, 403)
        admin = self.token("admin", "admin123")
        permitido = self.cliente.get("/api/auditoria", headers=self.cabecalho(admin))
        self.assertEqual(permitido.status_code, 200)

    def test_fluxo_clinico_completo(self):
        enfermeiro = self.token("enfermeiro", "enfermeiro123")
        medico = self.token("medico", "medico123")
        farmacia = self.token("farmacia", "farmacia123")
        limpeza = self.token("limpeza", "limpeza123")
        gestor = self.token("gestor", "gestor123")
        auditor = self.token("auditor", "auditor123")

        paciente = self.criar_paciente(enfermeiro, "Paciente Emergencia")
        episodio = self.criar_episodio(enfermeiro, paciente)

        triagem = self.cliente.post(
            f"/api/episodios/{episodio}/triagem",
            headers=self.cabecalho(enfermeiro),
            json={"queixa": "Dor toracica", "sinais_vitais": "PA 90/60, FC 120", "cor": "VERMELHO"},
        )
        self.assertEqual(triagem.status_code, 200, triagem.text)
        self.assertEqual(triagem.json()["prioridade"], 1)
        self.assertEqual(triagem.json()["estado"], "AGUARDANDO_MEDICO")

        fila = self.cliente.get("/api/fila", headers=self.cabecalho(medico)).json()
        self.assertTrue(any(item["episodio_id"] == episodio for item in fila))

        leitos = self.cliente.get("/api/leitos", headers=self.cabecalho(enfermeiro)).json()
        leito_livre = next(leito for leito in leitos if leito["estado"] == "LIVRE")
        alocacao = self.cliente.post(
            f"/api/leitos/{leito_livre['id']}/alocar",
            headers=self.cabecalho(enfermeiro),
            json={"episodio_id": episodio},
        )
        self.assertEqual(alocacao.status_code, 200, alocacao.text)

        alta_sem_atendimento = self.cliente.post(
            f"/api/episodios/{episodio}/alta-medica",
            headers=self.cabecalho(medico),
        )
        self.assertEqual(alta_sem_atendimento.status_code, 400)

        atendimento = self.cliente.post(
            f"/api/episodios/{episodio}/atendimento",
            headers=self.cabecalho(medico),
            json={"anamnese": "Dor subita", "hipotese": "Sindrome coronaria aguda"},
        )
        self.assertEqual(atendimento.status_code, 200, atendimento.text)

        prescricao = self.cliente.post(
            f"/api/episodios/{episodio}/prescricoes",
            headers=self.cabecalho(medico),
            json={"medicamento": "Paracetamol 500mg", "dose": "500mg"},
        )
        self.assertEqual(prescricao.status_code, 201, prescricao.text)
        prescricao_id = prescricao.json()["id"]

        dispensa_pelo_prescritor = self.cliente.post(
            f"/api/prescricoes/{prescricao_id}/dispensar",
            headers=self.cabecalho(medico),
        )
        self.assertEqual(dispensa_pelo_prescritor.status_code, 403)

        dispensa = self.cliente.post(
            f"/api/prescricoes/{prescricao_id}/dispensar",
            headers=self.cabecalho(farmacia),
        )
        self.assertEqual(dispensa.status_code, 200, dispensa.text)
        self.assertEqual(dispensa.json()["estado"], "DISPENSADA")

        alta = self.cliente.post(
            f"/api/episodios/{episodio}/alta-medica",
            headers=self.cabecalho(medico),
        )
        self.assertEqual(alta.status_code, 200, alta.text)
        self.assertIsNotNone(alta.json()["tarefa_higienizacao"])

        leito_sujo = self.cliente.get("/api/leitos", headers=self.cabecalho(enfermeiro)).json()
        estado_leito = next(item for item in leito_sujo if item["id"] == leito_livre["id"])["estado"]
        self.assertEqual(estado_leito, "HIGIENIZACAO")

        bloqueio = self.cliente.post(
            f"/api/leitos/{leito_livre['id']}/alocar",
            headers=self.cabecalho(enfermeiro),
            json={"episodio_id": episodio},
        )
        self.assertEqual(bloqueio.status_code, 400)

        higienizacao = self.cliente.get("/api/higienizacao", headers=self.cabecalho(limpeza)).json()
        tarefa = next(item for item in higienizacao if item["bed_id"] == leito_livre["id"])
        concluida = self.cliente.post(
            f"/api/higienizacao/{tarefa['id']}/concluir",
            headers=self.cabecalho(limpeza),
        )
        self.assertEqual(concluida.status_code, 200, concluida.text)

        leito_limpo = self.cliente.get("/api/leitos", headers=self.cabecalho(enfermeiro)).json()
        estado_final = next(item for item in leito_limpo if item["id"] == leito_livre["id"])["estado"]
        self.assertEqual(estado_final, "LIVRE")

        alta_adm = self.cliente.post(
            f"/api/episodios/{episodio}/alta-administrativa",
            headers=self.cabecalho(gestor),
        )
        self.assertEqual(alta_adm.status_code, 200, alta_adm.text)

        auditoria = self.cliente.get("/api/auditoria", headers=self.cabecalho(auditor)).json()
        acoes = {item["acao"] for item in auditoria}
        self.assertIn("TRIAGEM_REGISTADA", acoes)
        self.assertIn("PRESCRICAO_CRIADA", acoes)
        self.assertIn("ALTA_MEDICA", acoes)
        hashes = [item["hash"] for item in auditoria if item["hash"]]
        self.assertEqual(len(hashes), len(set(hashes)))

        eventos = self.cliente.get("/api/eventos", headers=self.cabecalho(auditor)).json()
        nomes = {item["evento"] for item in eventos}
        self.assertIn("AltaMedicaRegistada", nomes)

    def test_break_glass_e_dose_invalida(self):
        admin = self.token("admin", "admin123")
        enfermeiro = self.token("enfermeiro", "enfermeiro123")
        farmacia = self.token("farmacia", "farmacia123")
        medico = self.token("medico", "medico123")

        paciente = self.criar_paciente(admin, "Paciente Restrito")
        episodio = self.criar_episodio(admin, paciente)

        negado = self.cliente.get(
            f"/api/episodios/{episodio}/prontuario",
            headers=self.cabecalho(farmacia),
        )
        self.assertEqual(negado.status_code, 403)

        emergencia = self.cliente.post(
            "/api/acesso-emergencia",
            headers=self.cabecalho(farmacia),
            json={"episodio_id": episodio, "justificacao": "Risco iminente de morte na urgencia"},
        )
        self.assertEqual(emergencia.status_code, 200, emergencia.text)

        permitido = self.cliente.get(
            f"/api/episodios/{episodio}/prontuario",
            headers=self.cabecalho(farmacia),
        )
        self.assertEqual(permitido.status_code, 200, permitido.text)

        auditoria = self.cliente.get("/api/auditoria", headers=self.cabecalho(admin)).json()
        acoes = {item["acao"] for item in auditoria}
        self.assertIn("BREAK_THE_GLASS", acoes)
        self.assertIn("PRONTUARIO_ACESSO_EMERGENCIA", acoes)

        triagem = self.cliente.post(
            f"/api/episodios/{episodio}/triagem",
            headers=self.cabecalho(enfermeiro),
            json={"queixa": "Observacao", "sinais_vitais": "PA 120/80", "cor": "AMARELO"},
        )
        self.assertEqual(triagem.status_code, 200, triagem.text)

        atendimento = self.cliente.post(
            f"/api/episodios/{episodio}/atendimento",
            headers=self.cabecalho(medico),
            json={"anamnese": "Avaliacao", "hipotese": "Observacao"},
        )
        self.assertEqual(atendimento.status_code, 200)
        dose_invalida = self.cliente.post(
            f"/api/episodios/{episodio}/prescricoes",
            headers=self.cabecalho(medico),
            json={"medicamento": "Paracetamol 500mg", "dose": "muita coisa"},
        )
        self.assertEqual(dose_invalida.status_code, 400)

    def test_dashboard_e_estatica(self):
        token = self.token("enfermeiro", "enfermeiro123")
        resposta = self.cliente.get("/api/dashboard", headers=self.cabecalho(token))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("pacientes", resposta.json())
        self.assertIn("fila_medica", resposta.json())
        pagina = self.cliente.get("/")
        self.assertEqual(pagina.status_code, 200)
        self.assertIn("HIS - Hospital Publico", pagina.text)


if __name__ == "__main__":
    unittest.main()

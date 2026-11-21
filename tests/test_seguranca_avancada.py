import tempfile
import time
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import db
from app.routers import seguranca as router_seguranca
from app.seguranca_avancada import (
    assinar_jws,
    autorizar_acesso_excecional,
    codigo_totp,
    exigir_2fa,
    gerar_chaves_dev,
    gerar_segredo_totp,
    get_chaves,
    middleware_contexto_hospitalar,
    verificar_jws,
    verificar_totp,
)

ESQUEMA = """
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    nome TEXT NOT NULL,
    senha_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    perfil TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1,
    unidade_codigo TEXT
);
CREATE TABLE sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    criado_em TEXT NOT NULL
);
CREATE TABLE unidades_organizacionais (
    codigo TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    nivel INTEGER NOT NULL,
    unidade_pai_codigo TEXT,
    ativo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    perfil TEXT,
    acao TEXT NOT NULL,
    alvo TEXT NOT NULL,
    anterior TEXT,
    novo TEXT,
    ip TEXT,
    criado_em TEXT NOT NULL,
    hash TEXT NOT NULL,
    perfil_ativo TEXT,
    unidade_hospitalar TEXT,
    dispositivo TEXT,
    correlation_id TEXT
);
CREATE TABLE outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evento TEXT NOT NULL,
    payload TEXT NOT NULL,
    estado TEXT NOT NULL,
    criado_em TEXT NOT NULL
);
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nivel TEXT NOT NULL,
    mensagem TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    lido INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE seguranca_2fa (
    user_id TEXT PRIMARY KEY,
    secret TEXT NOT NULL,
    confirmado_em TEXT,
    criado_em TEXT NOT NULL
);
CREATE TABLE sessoes_2fa (
    token TEXT PRIMARY KEY,
    confirmado_em TEXT NOT NULL,
    expira_em TEXT NOT NULL
);
CREATE TABLE acessos_excecionais (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    episodio_id TEXT NOT NULL,
    justificacao TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    expira_em TEXT NOT NULL
);
"""


class TestesSegurancaAvancada(unittest.TestCase):
    def setUp(self):
        self.caminho_original = db.CAMINHO_DB
        self.diretorio = tempfile.TemporaryDirectory(prefix="his-seguranca-")
        db.CAMINHO_DB = Path(self.diretorio.name) / "seguranca.db"
        conexao = db.ligacao()
        try:
            conexao.executescript(ESQUEMA)
            conexao.execute(
                "INSERT INTO unidades_organizacionais (codigo, nome, nivel, unidade_pai_codigo, ativo) "
                "VALUES ('DG', 'Direcao Geral', 1, NULL, 1), ('URG', 'Urgencia', 3, 'DG', 1)"
            )
            conexao.commit()
        finally:
            conexao.close()
        self.app = FastAPI(title="Teste Seguranca")
        middleware_contexto_hospitalar(self.app)
        self.app.include_router(router_seguranca.router)

        @self.app.get("/api/protegido-2fa")
        def protegido(usuario: dict = Depends(exigir_2fa())) -> dict:
            return {"id": usuario["id"]}

        self.cliente = TestClient(self.app)
        self.token_medico = self.criar_sessao("medico", "medico", "Dr. Antonio Silva", "URG")
        self.token_admin = self.criar_sessao("admin", "administrador", "Administrador Geral", "DG")
        self.token_farmacia = self.criar_sessao("farmacia", "farmacia", "Farm. Joaquim Nunes", "FARM")

    def tearDown(self):
        self.cliente.close()
        self.diretorio.cleanup()
        db.CAMINHO_DB = self.caminho_original

    def criar_sessao(self, identificador: str, perfil: str, nome: str, unidade: str) -> str:
        token = f"token-{identificador}"
        conexao = db.ligacao()
        try:
            conexao.execute(
                "INSERT INTO users (id, username, nome, senha_hash, salt, perfil, ativo, unidade_codigo) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (identificador, identificador, nome, "hash", "salt", perfil, unidade),
            )
            conexao.execute(
                "INSERT INTO sessions (token, user_id, criado_em) VALUES (?, ?, ?)",
                (token, identificador, db.agora()),
            )
            conexao.commit()
        finally:
            conexao.close()
        return token

    def cabecalho(self, token: str, **extra) -> dict:
        cabecalho = {"Authorization": f"Bearer {token}"}
        cabecalho.update(extra)
        return cabecalho

    def test_totp_rfc6238_e_janela(self):
        segredo_rfc = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        self.assertEqual(codigo_totp(segredo_rfc, periodo=1), "287082")
        segredo = gerar_segredo_totp()
        self.assertEqual(len(segredo), 32)
        atual = int(time.time()) // 30
        self.assertTrue(verificar_totp(segredo, codigo_totp(segredo)))
        self.assertTrue(verificar_totp(segredo, codigo_totp(segredo, atual - 1)))
        self.assertFalse(verificar_totp(segredo, codigo_totp(segredo, atual - 5)))
        self.assertFalse(verificar_totp(segredo, "abc"))

    def test_jws_ed25519_e_endpoint(self):
        privada, publica = gerar_chaves_dev()
        token = assinar_jws({"sub": "medico", "nivel": 3}, privada)
        partes = token.split(".")
        self.assertEqual(len(partes), 3)
        self.assertTrue(all("=" not in parte for parte in partes))
        self.assertEqual(verificar_jws(token, publica)["sub"], "medico")
        with self.assertRaises(InvalidSignature):
            verificar_jws(token, gerar_chaves_dev()[1])

        resposta = self.cliente.post(
            "/api/seguranca/assinaturas/verificar",
            headers=self.cabecalho(self.token_medico),
            json={"token": assinar_jws({"sub": "medico"}, get_chaves()[0])},
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)
        self.assertTrue(resposta.json()["valido"])
        self.assertEqual(resposta.json()["payload"]["sub"], "medico")
        invalida = self.cliente.post(
            "/api/seguranca/assinaturas/verificar",
            headers=self.cabecalho(self.token_medico),
            json={"token": token[:-2] + "AA"},
        )
        self.assertFalse(invalida.json()["valido"])

    def test_contexto_unidade_e_rotas_livres(self):
        resposta = self.cliente.get("/api/seguranca/contexto", headers=self.cabecalho(self.token_medico))
        self.assertEqual(resposta.status_code, 200, resposta.text)
        dados = resposta.json()
        self.assertEqual(dados["usuario"]["perfil"], "medico")
        self.assertEqual(dados["unidade"], "URG")
        self.assertEqual(dados["nivel"], 3)
        self.assertFalse(dados["dois_fatores_confirmada"])

        invalida = self.cliente.get(
            "/api/seguranca/contexto",
            headers=self.cabecalho(self.token_medico, **{"X-Hospital-Unit-ID": "UCI"}),
        )
        self.assertEqual(invalida.status_code, 403)
        valida = self.cliente.get(
            "/api/seguranca/contexto",
            headers=self.cabecalho(self.token_medico, **{"X-Hospital-Unit-ID": "URG"}),
        )
        self.assertEqual(valida.status_code, 200)
        administrador = self.cliente.get(
            "/api/seguranca/contexto",
            headers=self.cabecalho(self.token_admin, **{"X-Hospital-Unit-ID": "UCI"}),
        )
        self.assertEqual(administrador.status_code, 200)
        self.assertEqual(self.cliente.get("/api/seguranca/contexto").status_code, 401)

        self.assertNotIn(self.cliente.get("/health").status_code, (401, 403))
        self.assertEqual(self.cliente.get("/docs").status_code, 200)

    def test_2fa_setup_e_verificar(self):
        sem_perfil = self.cliente.post("/api/seguranca/2fa/setup", headers=self.cabecalho(self.token_farmacia))
        self.assertEqual(sem_perfil.status_code, 403)
        setup = self.cliente.post("/api/seguranca/2fa/setup", headers=self.cabecalho(self.token_medico))
        self.assertEqual(setup.status_code, 200, setup.text)
        segredo = setup.json()["secret"]
        self.assertIn("otpauth://totp/HIS%3Amedico", setup.json()["otpauth_uri"])
        self.assertNotIn("qrcode", setup.json()["otpauth_uri"])

        protegido_antes = self.cliente.get("/api/protegido-2fa", headers=self.cabecalho(self.token_medico))
        self.assertEqual(protegido_antes.status_code, 403)
        errado = self.cliente.post(
            "/api/seguranca/2fa/verificar",
            headers=self.cabecalho(self.token_medico),
            json={"codigo": codigo_totp(segredo, periodo=999)},
        )
        self.assertEqual(errado.status_code, 400)
        correto = self.cliente.post(
            "/api/seguranca/2fa/verificar",
            headers=self.cabecalho(self.token_medico),
            json={"codigo": codigo_totp(segredo)},
        )
        self.assertEqual(correto.status_code, 200, correto.text)
        self.assertIsNotNone(correto.json()["confirmado_em"])
        self.assertIsNotNone(correto.json()["expira_em"])
        contexto = self.cliente.get("/api/seguranca/contexto", headers=self.cabecalho(self.token_medico)).json()
        self.assertTrue(contexto["dois_fatores_confirmada"])
        self.assertEqual(
            self.cliente.get("/api/protegido-2fa", headers=self.cabecalho(self.token_medico)).status_code,
            200,
        )

    def test_break_the_glass_auditoria_alerta_e_evento(self):
        curto = self.cliente.post(
            "/api/seguranca/break-the-glass",
            headers=self.cabecalho(self.token_medico),
            json={"episodio_id": "EPI-1", "justificacao": "muito curta"},
        )
        self.assertEqual(curto.status_code, 422)
        sem_perfil = self.cliente.post(
            "/api/seguranca/break-the-glass",
            headers=self.cabecalho(self.token_farmacia),
            json={"episodio_id": "EPI-1", "justificacao": "Justificacao com mais de vinte caracteres"},
        )
        self.assertEqual(sem_perfil.status_code, 403)
        resposta = self.cliente.post(
            "/api/seguranca/break-the-glass",
            headers=self.cabecalho(self.token_medico),
            json={"episodio_id": "EPI-1", "justificacao": "Risco iminente de morte no episodio urgente"},
        )
        self.assertEqual(resposta.status_code, 200, resposta.text)
        self.assertTrue(resposta.json()["id"].startswith("BTG-"))
        self.assertIsNotNone(resposta.json()["expira_em"])

        conexao = db.ligacao()
        try:
            auditoria = conexao.execute(
                "SELECT * FROM audit WHERE acao = ?", ("ACEDERO_BREAK_THE_GLASS",)
            ).fetchall()
            self.assertEqual(len(auditoria), 1)
            alertas = conexao.execute("SELECT * FROM alerts WHERE nivel = 'CRITICO'").fetchall()
            self.assertEqual(len(alertas), 1)
            eventos = conexao.execute(
                "SELECT * FROM outbox WHERE evento = ?", ("AcessoExcecionalAutorizado",)
            ).fetchall()
            self.assertEqual(len(eventos), 1)
            acessos = conexao.execute("SELECT * FROM acessos_excecionais").fetchall()
            self.assertEqual(len(acessos), 1)
            self.assertEqual(acessos[0]["episodio_id"], "EPI-1")
        finally:
            conexao.close()

        self.assertTrue(autorizar_acesso_excecional("EPI-1", {"id": "medico"}))
        self.assertFalse(autorizar_acesso_excecional("EPI-2", {"id": "medico"}))
        contexto = self.cliente.get("/api/seguranca/contexto", headers=self.cabecalho(self.token_medico)).json()
        self.assertIsNotNone(contexto["acesso_excecional_ativo"])

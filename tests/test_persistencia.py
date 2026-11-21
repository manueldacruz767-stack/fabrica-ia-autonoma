import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

CAMINHO_TESTE = os.environ.get("HIS_DB_PATH")
if not CAMINHO_TESTE:
    DIRETORIO_TESTE = tempfile.mkdtemp(prefix="his-persistencia-")
    CAMINHO_TESTE = os.path.join(DIRETORIO_TESTE, "his.db")
    os.environ["HIS_DB_PATH"] = CAMINHO_TESTE

from app import consumidor_outbox
from app import db
from app.config import carregar_config
from app.migracoes import MIGRACOES, adaptar_marcadores, eh_postgres, executar_migracoes
from app.repositorio import ErroRepositorio, Repositorio


class BasePersistencia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.inicializar()
        with patch.dict(os.environ, {"HIS_DB_DSN": ""}):
            Repositorio().aplicar_migracoes()

    def setUp(self):
        conexao = db.ligacao()
        try:
            for tabela in ("outbox", "seguranca_2fa", "sessoes_2fa", "acessos_excecionais"):
                conexao.execute(f"DELETE FROM {tabela}")
            conexao.commit()
        finally:
            conexao.close()

    def criar_evento(self, nome: str = "EVENTO_TESTE", payload: str = '{"valor": 1}') -> int:
        conexao = db.ligacao()
        try:
            conexao.execute(
                "INSERT INTO outbox (evento, payload, estado, criado_em) VALUES (?, ?, 'PENDENTE', ?)",
                (nome, payload, db.agora()),
            )
            conexao.commit()
            return conexao.execute("SELECT id FROM outbox ORDER BY id DESC LIMIT 1").fetchone()["id"]
        finally:
            conexao.close()

    def ler_evento(self, identificador: int):
        conexao = db.ligacao()
        try:
            return conexao.execute("SELECT * FROM outbox WHERE id = ?", (identificador,)).fetchone()
        finally:
            conexao.close()


class TestesMigracoes(BasePersistencia):
    def test_migracoes_idempotentes(self):
        conexao = sqlite3.connect(":memory:")
        try:
            self.assertEqual(executar_migracoes(conexao), len(MIGRACOES))
            conexao.execute(
                "INSERT INTO seguranca_2fa (user_id, secret, criado_em) VALUES (?, ?, ?)",
                ("utilizador-1", "segredo-local", db.agora()),
            )
            conexao.commit()
            self.assertEqual(executar_migracoes(conexao), len(MIGRACOES))

            tabelas = {
                linha[0] for linha in conexao.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            self.assertTrue(
                {"seguranca_2fa", "sessoes_2fa", "acessos_excecionais"}.issubset(tabelas)
            )

            colunas = {
                "seguranca_2fa": {"user_id", "secret", "confirmado_em", "criado_em"},
                "sessoes_2fa": {"token", "confirmado_em", "expira_em"},
                "acessos_excecionais": {
                    "id",
                    "user_id",
                    "episodio_id",
                    "justificacao",
                    "criado_em",
                    "expira_em",
                },
            }
            for tabela, esperado in colunas.items():
                encontradas = {
                    linha[1] for linha in conexao.execute(f"PRAGMA table_info({tabela})")
                }
                self.assertEqual(encontradas, esperado)

            self.assertEqual(
                conexao.execute("SELECT COUNT(*) FROM seguranca_2fa").fetchone()[0], 1
            )
        finally:
            conexao.close()

    def test_adaptacao_de_marcadores_para_postgres(self):
        class LigacaoPostgresFalsa:
            __module__ = "psycopg2.extensions"

        conexao = LigacaoPostgresFalsa()
        self.assertTrue(eh_postgres(conexao))
        consulta = "SELECT ? FROM eventos WHERE texto = '?''?' AND estado = ?"
        adaptada = adaptar_marcadores(consulta, conexao)
        self.assertEqual(adaptada.count("%s"), 2)
        self.assertIn("'?''?'", adaptada)

        ligacao_sqlite = sqlite3.connect(":memory:")
        try:
            self.assertFalse(eh_postgres(ligacao_sqlite))
            self.assertEqual(adaptar_marcadores(consulta, ligacao_sqlite), consulta)
        finally:
            ligacao_sqlite.close()


class TestesRepositorio(BasePersistencia):
    def test_fallback_para_sqlite(self):
        with patch.dict(os.environ, {"HIS_DB_DSN": "", "HIS_DB_PATH": CAMINHO_TESTE}):
            repositorio = Repositorio()
        self.assertIsNone(repositorio.configuracao.dsn)
        with patch("app.repositorio.db.ligacao", wraps=db.ligacao) as ligacao:
            with repositorio.ligacao() as conexao:
                self.assertIsInstance(conexao, sqlite3.Connection)
            ligacao.assert_called_once_with()

    def test_erro_claro_sem_driver_postgres(self):
        with patch.dict(os.environ, {"HIS_DB_DSN": "postgresql://utilizador:senha@localhost:5432/his"}):
            repositorio = Repositorio()
        with patch("app.repositorio.import_module", side_effect=ImportError("sem driver")):
            with self.assertRaises(ErroRepositorio) as contexto:
                with repositorio.ligacao():
                    pass
        mensagem = str(contexto.exception)
        self.assertIn("psycopg2", mensagem)
        self.assertNotIn("senha", mensagem)
        self.assertNotIn("postgresql://", mensagem)

    def test_migracoes_com_driver_opcional(self):
        class LigacaoPostgresFalsa:
            __module__ = "psycopg2.extensions"

            def __init__(self):
                self.consultas = []
                self.fechada = False
                self.confirmada = False

            def execute(self, consulta, parametros=None):
                self.consultas.append(consulta)

            def commit(self):
                self.confirmada = True

            def close(self):
                self.fechada = True

        with patch.dict(os.environ, {"HIS_DB_DSN": "postgresql://utilizador@localhost:5432/his"}):
            repositorio = Repositorio()
        driver = MagicMock()
        driver.connect.return_value = LigacaoPostgresFalsa()
        with patch("app.repositorio.import_module", return_value=driver):
            total = repositorio.aplicar_migracoes()
        ligacao = driver.connect.return_value
        self.assertEqual(total, len(MIGRACOES))
        self.assertTrue(driver.connect.called)
        self.assertEqual(len(ligacao.consultas), len(MIGRACOES))
        self.assertTrue(ligacao.confirmada)
        self.assertTrue(ligacao.fechada)
        self.assertFalse(any("?" in consulta for consulta in ligacao.consultas))


class TestesPublicador(BasePersistencia):
    def test_publicador_local_emite_log_json(self):
        saida = io.StringIO()
        with redirect_stdout(saida):
            consumidor_outbox.PublicadorLocal().publicar(
                {"id": 1, "evento": "EVENTO_TESTE", "payload": '{"chave": "valor-sensivel"}'}
            )
        registo = json.loads(saida.getvalue().strip())
        self.assertEqual(registo["publicador"], "local")
        self.assertEqual(registo["estado"], "PUBLICADO")
        self.assertEqual(registo["evento"], "EVENTO_TESTE")
        self.assertNotIn("valor-sensivel", saida.getvalue())

    def test_publicar_pendentes_marca_como_publicado(self):
        identificador = self.criar_evento()
        with redirect_stdout(io.StringIO()):
            resultado = consumidor_outbox.publicar_pendentes()
        self.assertEqual(resultado["processados"], 1)
        self.assertEqual(resultado["eventos"], [{"id": identificador, "evento": "EVENTO_TESTE"}])
        linha = self.ler_evento(identificador)
        self.assertEqual(linha["estado"], "PUBLICADO")
        self.assertEqual(linha["tentativas"], 1)
        self.assertIsNotNone(linha["publicado_em"])
        self.assertIsNone(linha["ultimo_erro"])

    def test_selecao_do_publicador_pela_configuracao(self):
        with patch.dict(os.environ, {"OUTBOX_WEBHOOK_URL": "http://localhost:9999/hook"}):
            self.assertIsInstance(consumidor_outbox.publicador_padrao(), consumidor_outbox.PublicadorWebhook)
        with patch.dict(os.environ, {"OUTBOX_WEBHOOK_URL": ""}):
            self.assertIsInstance(consumidor_outbox.publicador_padrao(), consumidor_outbox.PublicadorLocal)


class TestesPublicadorWebhook(BasePersistencia):
    def setUp(self):
        super().setUp()
        with patch.dict(os.environ, {"OUTBOX_WEBHOOK_URL": "http://localhost:9999/hook"}):
            self.configuracao = carregar_config()
        self.publicador = consumidor_outbox.PublicadorWebhook(configuracao=self.configuracao)

    def test_webhook_com_retry_e_sucesso(self):
        identificador = self.criar_evento()
        resposta = MagicMock()
        resposta.status = 200
        resposta.read.return_value = b""
        conexao = MagicMock()
        conexao.getresponse.side_effect = [MagicMock(status=503, read=MagicMock(return_value=b"")), resposta]
        with patch.object(consumidor_outbox.http.client, "HTTPConnection", return_value=conexao) as fabrica:
            with patch.object(consumidor_outbox.time, "sleep"):
                resultado = consumidor_outbox.publicar_pendentes(publicador=self.publicador)
        self.assertEqual(fabrica.call_count, 2)
        self.assertEqual(conexao.request.call_args.args[0], "POST")
        self.assertEqual(conexao.request.call_args.args[1], "/hook")
        self.assertEqual(conexao.request.call_args.kwargs["headers"]["Content-Type"], "application/json")
        corpo = json.loads(conexao.request.call_args.kwargs["body"])
        self.assertEqual(corpo["evento"], "EVENTO_TESTE")
        self.assertEqual(corpo["payload"], {"valor": 1})
        self.assertEqual(resultado["processados"], 1)
        self.assertEqual(self.ler_evento(identificador)["estado"], "PUBLICADO")

    def test_webhook_esgotado_mantem_evento_pendente(self):
        identificador = self.criar_evento()
        resposta = MagicMock(status=503, read=MagicMock(return_value=b""))
        conexao = MagicMock()
        conexao.getresponse.return_value = resposta
        with patch.object(consumidor_outbox.http.client, "HTTPConnection", return_value=conexao) as fabrica:
            with patch.object(consumidor_outbox.time, "sleep"):
                resultado = consumidor_outbox.publicar_pendentes(publicador=self.publicador)
        self.assertEqual(fabrica.call_count, 3)
        self.assertEqual(resultado["processados"], 0)
        self.assertEqual(len(resultado["falhas"]), 1)
        linha = self.ler_evento(identificador)
        self.assertEqual(linha["estado"], "PENDENTE")
        self.assertEqual(linha["tentativas"], 1)
        self.assertIn("HTTP 503", linha["ultimo_erro"])
        self.assertNotIn("localhost", linha["ultimo_erro"])


if __name__ == "__main__":
    unittest.main()

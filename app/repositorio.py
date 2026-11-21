from contextlib import contextmanager
from importlib import import_module

from app import db
from app.config import Configuracao, carregar_config
from app.migracoes import executar_migracoes


class ErroRepositorio(RuntimeError):
    pass


def _ligar_postgres(configuracao: Configuracao):
    try:
        driver = import_module("psycopg2")
    except ImportError as exc:
        raise ErroRepositorio(
            "HIS_DB_DSN definido mas psycopg2 nao esta instalado; "
            "instale psycopg2-binary ou remova HIS_DB_DSN"
        ) from exc
    try:
        extras = import_module("psycopg2.extras")
        fabrica_cursor = extras.RealDictCursor
    except ImportError:
        fabrica_cursor = None
    opcoes = {"cursor_factory": fabrica_cursor} if fabrica_cursor else {}
    try:
        return driver.connect(configuracao.dsn, **opcoes)
    except Exception as exc:
        raise ErroRepositorio("Falha ao ligar ao PostgreSQL configurado em HIS_DB_DSN") from exc


def abrir_ligacao(configuracao: Configuracao | None = None):
    config = configuracao or carregar_config()
    if config.dsn:
        return _ligar_postgres(config)
    return db.ligacao()


class Repositorio:
    def __init__(self, configuracao: Configuracao | None = None):
        self.configuracao = configuracao or carregar_config()

    @contextmanager
    def ligacao(self):
        conexao = abrir_ligacao(self.configuracao)
        try:
            yield conexao
        except Exception:
            if hasattr(conexao, "rollback"):
                conexao.rollback()
            raise
        finally:
            conexao.close()

    def aplicar_migracoes(self) -> int:
        with self.ligacao() as conexao:
            return executar_migracoes(conexao)

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Configuracao, carregar_config
from app.repositorio import Repositorio


def migrar(configuracao: Configuracao | None = None) -> dict:
    config = configuracao or carregar_config()
    if not config.dsn:
        raise RuntimeError("HIS_DB_DSN nao configurado; defina a DSN do PostgreSQL antes de migrar")
    repositorio = Repositorio(config)
    aplicadas = repositorio.aplicar_migracoes()
    return {"estado": "concluido", "destino": "postgresql", "migracoes": aplicadas}


def main() -> None:
    argparse.ArgumentParser(
        description="Aplica as migracoes ao PostgreSQL sem apagar dados existentes."
    ).parse_args()
    print(json.dumps(migrar(), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()

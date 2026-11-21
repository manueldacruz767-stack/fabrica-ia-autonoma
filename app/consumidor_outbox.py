import json
import sys
import time

from app import db


def publicar_pendentes(limite: int = 100) -> dict:
    conexao = db.ligacao()
    publicados = []
    try:
        pendentes = conexao.execute(
            "SELECT id, evento, payload FROM outbox WHERE estado = 'PENDENTE' ORDER BY id LIMIT ?", (limite,)
        ).fetchall()
        for evento in pendentes:
            conexao.execute(
                "UPDATE outbox SET estado = 'PUBLICADO', tentativas = tentativas + 1, publicado_em = ?, "
                "ultimo_erro = NULL WHERE id = ?",
                (db.agora(), evento["id"]),
            )
            publicados.append({"id": evento["id"], "evento": evento["evento"]})
        conexao.commit()
    finally:
        conexao.close()
    return {"processados": len(publicados), "eventos": publicados}


def main() -> None:
    db.inicializar()
    while True:
        resultado = publicar_pendentes()
        print(json.dumps(resultado, sort_keys=True), flush=True)
        if "--once" in sys.argv:
            break
        time.sleep(5)


if __name__ == "__main__":
    main()

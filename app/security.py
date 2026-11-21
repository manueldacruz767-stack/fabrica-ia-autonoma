import hashlib
import json
import secrets
from typing import Any, Callable

from fastapi import Depends, Header, HTTPException, Request

from app import db


def verificar_senha(senha: str, salt: str, esperado: str) -> bool:
    return secrets.compare_digest(db.derivar_hash(senha, salt), esperado)


def autenticar(conexao, username: str, senha: str) -> dict | None:
    linha = conexao.execute("SELECT * FROM users WHERE username = ? AND ativo = 1", (username,)).fetchone()
    if not linha or not verificar_senha(senha, linha["salt"], linha["senha_hash"]):
        return None
    token = secrets.token_urlsafe(32)
    conexao.execute(
        "INSERT INTO sessions (token, user_id, criado_em) VALUES (?, ?, ?)",
        (token, linha["id"], db.agora()),
    )
    conexao.commit()
    return {
        "token": token,
        "id": linha["id"],
        "username": linha["username"],
        "nome": linha["nome"],
        "perfil": linha["perfil"],
    }


async def usuario_atual(request: Request, authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Token ausente")
    token = authorization.split(" ", 1)[1].strip()
    conexao = db.ligacao()
    try:
        linha = conexao.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ? AND u.ativo = 1",
            (token,),
        ).fetchone()
    finally:
        conexao.close()
    if not linha:
        raise HTTPException(status_code=401, detail="Token invalido")
    return {
        "id": linha["id"],
        "username": linha["username"],
        "nome": linha["nome"],
        "perfil": linha["perfil"],
        "token": token,
        "ip": request.client.host if request.client else "desconhecido",
    }


def exigir(*perfis: str) -> Callable[..., Any]:
    def dependencia(usuario: dict = Depends(usuario_atual)) -> dict:
        if usuario["perfil"] != "administrador" and usuario["perfil"] not in perfis:
            raise HTTPException(status_code=403, detail="Perfil sem permissao para esta acao")
        return usuario

    return dependencia


def registrar_auditoria(
    conexao,
    usuario: dict,
    acao: str,
    alvo: str,
    anterior: Any = None,
    novo: Any = None,
) -> None:
    ultimo = conexao.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
    payload = {
        "anterior": ultimo["hash"] if ultimo else "",
        "user_id": usuario.get("id"),
        "perfil": usuario.get("perfil"),
        "acao": acao,
        "alvo": alvo,
        "anterior_valor": anterior,
        "novo_valor": novo,
        "ip": usuario.get("ip", "desconhecido"),
        "criado_em": db.agora(),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    conexao.execute(
        "INSERT INTO audit (user_id, perfil, acao, alvo, anterior, novo, ip, criado_em, hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            payload["user_id"],
            payload["perfil"],
            acao,
            alvo,
            json.dumps(anterior, default=str) if anterior is not None else None,
            json.dumps(novo, default=str) if novo is not None else None,
            payload["ip"],
            payload["criado_em"],
            digest,
        ),
    )


def registrar_evento(conexao, evento: str, payload: dict) -> None:
    conexao.execute(
        "INSERT INTO outbox (evento, payload, estado, criado_em) VALUES (?, ?, 'PENDENTE', ?)",
        (evento, json.dumps(payload, sort_keys=True, default=str), db.agora()),
    )


def criar_alerta(conexao, nivel: str, mensagem: str) -> None:
    conexao.execute(
        "INSERT INTO alerts (nivel, mensagem, criado_em) VALUES (?, ?, ?)",
        (nivel, mensagem, db.agora()),
    )

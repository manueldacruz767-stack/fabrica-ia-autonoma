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
        "unidade_codigo": linha["unidade_codigo"],
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
        "unidade_codigo": linha["unidade_codigo"],
        "perfil_ativo": linha["perfil"],
        "correlation_id": getattr(request.state, "correlation_id", ""),
        "dispositivo": request.headers.get("user-agent", "desconhecido"),
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
        "perfil_ativo": usuario.get("perfil_ativo", usuario.get("perfil")),
        "unidade_hospitalar": usuario.get("unidade_codigo"),
        "dispositivo": usuario.get("dispositivo", "desconhecido"),
        "correlation_id": usuario.get("correlation_id", ""),
        "criado_em": db.agora(),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    conexao.execute(
        "INSERT INTO audit (user_id, perfil, acao, alvo, anterior, novo, ip, criado_em, hash, "
        "perfil_ativo, unidade_hospitalar, dispositivo, correlation_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            payload["perfil_ativo"],
            payload["unidade_hospitalar"],
            payload["dispositivo"],
            payload["correlation_id"],
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


def assinar_documento(conexao, usuario: dict, tipo: str, referencia_id: str, conteudo: str) -> dict:
    criado_em = db.agora()
    payload = json.dumps(
        {
            "tipo": tipo,
            "referencia_id": referencia_id,
            "conteudo": conteudo,
            "utilizador_id": usuario.get("id"),
            "perfil_ativo": usuario.get("perfil_ativo", usuario.get("perfil")),
            "criado_em": criado_em,
        },
        sort_keys=True,
        default=str,
    )
    hash_documento = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assinatura = hashlib.sha256(
        f"{hash_documento}|{usuario.get('id')}|{usuario.get('correlation_id', '')}".encode("utf-8")
    ).hexdigest()
    documento_id = f"DOC-{secrets.token_hex(6).upper()}"
    conexao.execute(
        "INSERT INTO documentos_assinados (id, tipo_documento, referencia_id, conteudo, hash_documento, "
        "assinatura, certificado_id, utilizador_id, perfil_ativo, unidade_codigo, ip_origem, "
        "correlation_id, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            documento_id,
            tipo,
            referencia_id,
            conteudo,
            hash_documento,
            assinatura,
            f"CERT-{usuario.get('id')}",
            usuario.get("id"),
            usuario.get("perfil_ativo", usuario.get("perfil")),
            usuario.get("unidade_codigo"),
            usuario.get("ip", "desconhecido"),
            usuario.get("correlation_id", ""),
            criado_em,
        ),
    )
    registrar_auditoria(conexao, usuario, "ASSINAR_DOCUMENTO", f"{tipo}:{referencia_id}", None, {"id": documento_id})
    return {"id": documento_id, "hash": hash_documento, "assinatura": assinatura, "criado_em": criado_em}


def registrar_bi(conexao, origem: str, chave: str, dados: Any, usuario: dict) -> None:
    conexao.execute(
        "INSERT INTO registos_bi (origem, chave, unidade_codigo, perfil, dados, criado_em) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            origem,
            chave,
            usuario.get("unidade_codigo"),
            usuario.get("perfil"),
            json.dumps(dados, sort_keys=True, default=str),
            db.agora(),
        ),
    )


def episodio_permitido(conexao, usuario: dict, episodio_id: str) -> bool:
    perfis_clinicos = {
        "administrador",
        "auditoria",
        "medico",
        "enfermeiro",
        "rececionista",
        "laboratorio",
        "imagiologia",
        "fisioterapia",
        "farmacia",
        "nutricionista",
        "transportes",
        "comissao_etica",
    }
    if usuario.get("perfil") in perfis_clinicos:
        return True
    linha = conexao.execute(
        "SELECT unidade_codigo FROM episodes WHERE id = ?", (episodio_id,)
    ).fetchone()
    if not linha or not linha["unidade_codigo"]:
        return True
    return unidade_permitida(usuario, linha["unidade_codigo"])


def unidade_permitida(usuario: dict, unidade_codigo: str | None) -> bool:
    if not unidade_codigo:
        return True
    if usuario.get("perfil") == "administrador":
        return True
    return usuario.get("unidade_codigo") in {unidade_codigo, "DG"}

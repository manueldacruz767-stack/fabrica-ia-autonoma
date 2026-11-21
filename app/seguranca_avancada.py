import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import struct
import time
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app import db

ISSUER_TOTP = "HIS"
CAMINHOS_LIVRES = {"/api/auth/login", "/health", "/metrics"}
_CHAVES_ASSINATURA: tuple[Ed25519PrivateKey, Ed25519PublicKey] | None = None


def gerar_segredo_totp() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decodificar_segredo(secret: str) -> bytes:
    limpo = secret.strip().upper()
    return base64.b32decode(limpo + "=" * ((8 - len(limpo) % 8) % 8))


def codigo_totp(secret: str, periodo: int | None = None) -> str:
    contador = int(time.time()) // 30 if periodo is None else int(periodo)
    resumo = hmac.new(_decodificar_segredo(secret), struct.pack(">Q", contador), hashlib.sha1).digest()
    deslocamento = resumo[-1] & 0x0F
    valor = struct.unpack(">I", resumo[deslocamento:deslocamento + 4])[0] & 0x7FFFFFFF
    return f"{valor % 1000000:06d}"


def verificar_totp(secret: str, codigo: str, janela: int = 1) -> bool:
    codigo = str(codigo).strip()
    if len(codigo) != 6 or not codigo.isdigit():
        return False
    contador = int(time.time()) // 30
    for desvio in range(-abs(janela), abs(janela) + 1):
        if secrets.compare_digest(codigo, codigo_totp(secret, contador + desvio)):
            return True
    return False


def _codificar_b64url(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def _decodificar_b64url(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * ((4 - len(texto) % 4) % 4))


def gerar_chaves_dev() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    privada = Ed25519PrivateKey.generate()
    return privada, privada.public_key()


def assinar_jws(payload: dict, chave_privada: Ed25519PrivateKey) -> str:
    cabecalho = _codificar_b64url(
        json.dumps({"alg": "EdDSA", "typ": "JWT"}, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    corpo = _codificar_b64url(
        json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
    )
    dados = f"{cabecalho}.{corpo}".encode("ascii")
    return f"{cabecalho}.{corpo}.{_codificar_b64url(chave_privada.sign(dados))}"


def verificar_jws(token: str, chave_publica: Ed25519PublicKey) -> dict:
    partes = token.split(".")
    if len(partes) != 3:
        raise ValueError("JWS invalido")
    cabecalho = json.loads(_decodificar_b64url(partes[0]))
    if cabecalho.get("alg") != "EdDSA":
        raise ValueError("Algoritmo de assinatura nao suportado")
    assinatura = _decodificar_b64url(partes[2])
    chave_publica.verify(assinatura, f"{partes[0]}.{partes[1]}".encode("ascii"))
    payload = json.loads(_decodificar_b64url(partes[1]))
    if not isinstance(payload, dict):
        raise ValueError("Payload JWS invalido")
    return payload


def get_chaves() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    global _CHAVES_ASSINATURA
    if _CHAVES_ASSINATURA is None:
        caminho = os.getenv("HIS_SIGNING_KEY_PATH")
        if caminho and Path(caminho).is_file():
            privada = serialization.load_pem_private_key(Path(caminho).read_bytes(), password=None)
        else:
            privada = Ed25519PrivateKey.generate()
        _CHAVES_ASSINATURA = (privada, privada.public_key())
    return _CHAVES_ASSINATURA


def uri_otpauth(secret: str, usuario: str) -> str:
    nome = quote(f"{ISSUER_TOTP}:{usuario}", safe="")
    return (
        f"otpauth://totp/{nome}?secret={secret}&issuer={ISSUER_TOTP}"
        "&algorithm=SHA1&digits=6&period=30"
    )


def _carregar_usuario(token: str) -> dict | None:
    conexao = db.ligacao()
    try:
        linha = conexao.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token = ? AND u.ativo = 1",
            (token,),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conexao.close()
    if not linha:
        return None
    return {
        "id": linha["id"],
        "username": linha["username"],
        "nome": linha["nome"],
        "perfil": linha["perfil"],
        "unidade_codigo": linha["unidade_codigo"] if "unidade_codigo" in linha.keys() else None,
        "perfil_ativo": linha["perfil"],
        "token": token,
    }


def nivel_hierarquico(unidade_codigo: str | None) -> int:
    if not unidade_codigo:
        return 4
    conexao = db.ligacao()
    try:
        linha = conexao.execute(
            "SELECT nivel FROM unidades_organizacionais WHERE codigo = ?", (unidade_codigo,)
        ).fetchone()
    except sqlite3.Error:
        return 4
    finally:
        conexao.close()
    return int(linha["nivel"]) if linha and linha["nivel"] is not None else 4


def middleware_contexto_hospitalar(app):
    async def contexto_hospitalar(request: Request, call_next):
        caminho = request.url.path
        if not caminho.startswith("/api") or caminho in CAMINHOS_LIVRES:
            return await call_next(request)
        autorizacao = request.headers.get("authorization", "")
        if not autorizacao.lower().startswith("bearer "):
            return JSONResponse(status_code=401, content={"detail": "Token ausente"})
        token = autorizacao.split(" ", 1)[1].strip()
        usuario = _carregar_usuario(token)
        if not usuario:
            return JSONResponse(status_code=401, content={"detail": "Token invalido"})
        unidade_cabecalho = request.headers.get("x-hospital-unit-id")
        if (
            unidade_cabecalho
            and usuario.get("perfil") != "administrador"
            and usuario.get("unidade_codigo") != "DG"
            and unidade_cabecalho != usuario.get("unidade_codigo")
        ):
            return JSONResponse(status_code=403, content={"detail": "Unidade hospitalar nao autorizada"})
        usuario["correlation_id"] = request.headers.get("x-correlation-id", "")
        usuario["dispositivo"] = request.headers.get("user-agent", "desconhecido")
        usuario["ip"] = request.client.host if request.client else "desconhecido"
        unidade = unidade_cabecalho or usuario.get("unidade_codigo")
        request.state.hospital_user = usuario
        request.state.hospital_unit = unidade
        request.state.nivel_hierarquico = nivel_hierarquico(unidade)
        return await call_next(request)

    app.add_middleware(BaseHTTPMiddleware, dispatch=contexto_hospitalar)
    return contexto_hospitalar


def usuario_hospitalar(request: Request) -> dict:
    usuario = getattr(request.state, "hospital_user", None)
    if not usuario:
        raise HTTPException(status_code=401, detail="Contexto hospitalar ausente")
    return usuario


def exigir_perfil(*perfis: str) -> Callable[..., dict]:
    def dependencia(usuario: dict = Depends(usuario_hospitalar)) -> dict:
        if usuario.get("perfil") != "administrador" and usuario.get("perfil") not in perfis:
            raise HTTPException(status_code=403, detail="Perfil sem permissao para esta acao")
        return usuario

    return dependencia


def sessao_2fa_confirmada(token: str | None) -> bool:
    if not token:
        return False
    conexao = db.ligacao()
    try:
        linha = conexao.execute(
            "SELECT 1 FROM sessoes_2fa WHERE token = ? AND confirmado_em IS NOT NULL AND expira_em > ?",
            (token, db.agora()),
        ).fetchone()
        return bool(linha)
    except sqlite3.Error:
        return False
    finally:
        conexao.close()


def exigir_2fa() -> Callable[..., dict]:
    def dependencia(usuario: dict = Depends(usuario_hospitalar)) -> dict:
        if not sessao_2fa_confirmada(usuario.get("token")):
            raise HTTPException(status_code=403, detail="Autenticacao de dois fatores exigida")
        return usuario

    return dependencia


def autorizar_acesso_excecional(episodio_id: str, usuario: dict) -> bool:
    conexao = db.ligacao()
    try:
        linha = conexao.execute(
            "SELECT 1 FROM acessos_excecionais WHERE user_id = ? AND episodio_id = ? AND expira_em > ?",
            (usuario.get("id"), episodio_id, db.agora()),
        ).fetchone()
        return bool(linha)
    except sqlite3.Error:
        return False
    finally:
        conexao.close()


def acesso_excecional_ativo(usuario: dict) -> dict | None:
    conexao = db.ligacao()
    try:
        linha = conexao.execute(
            "SELECT * FROM acessos_excecionais WHERE user_id = ? AND expira_em > ? "
            "ORDER BY expira_em DESC LIMIT 1",
            (usuario.get("id"), db.agora()),
        ).fetchone()
        return dict(linha) if linha else None
    except sqlite3.Error:
        return None
    finally:
        conexao.close()

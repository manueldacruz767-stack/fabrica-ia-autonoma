from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app import db, security
from app.domain import criar_id
from app.seguranca_avancada import (
    acesso_excecional_ativo,
    exigir_perfil,
    gerar_segredo_totp,
    get_chaves,
    sessao_2fa_confirmada,
    uri_otpauth,
    usuario_hospitalar,
    verificar_jws,
    verificar_totp,
)

router = APIRouter(prefix="/api/seguranca", tags=["seguranca"])


class Codigo2FAModel(BaseModel):
    codigo: str = Field(min_length=6, max_length=6)


class BreakGlassModel(BaseModel):
    episodio_id: str = Field(min_length=1)
    justificacao: str = Field(min_length=20)


class AssinaturaModel(BaseModel):
    token: str = Field(min_length=1)


def _expiracao(horas: int = 0, minutos: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=horas, minutes=minutos)).isoformat(timespec="seconds")


@router.post("/2fa/setup")
def configurar_2fa(
    usuario: dict = Depends(exigir_perfil("medico", "enfermeiro", "administrador", "rh", "financeiro")),
) -> dict:
    segredo = gerar_segredo_totp()
    conexao = db.ligacao()
    try:
        conexao.execute(
            "INSERT OR REPLACE INTO seguranca_2fa (user_id, secret, confirmado_em, criado_em) "
            "VALUES (?, ?, NULL, ?)",
            (usuario["id"], segredo, db.agora()),
        )
        conexao.commit()
    finally:
        conexao.close()
    return {"secret": segredo, "otpauth_uri": uri_otpauth(segredo, usuario.get("username") or usuario["id"])}


@router.post("/2fa/verificar")
def verificar_codigo_2fa(
    dados: Codigo2FAModel,
    usuario: dict = Depends(usuario_hospitalar),
) -> dict:
    conexao = db.ligacao()
    try:
        linha = conexao.execute(
            "SELECT secret FROM seguranca_2fa WHERE user_id = ? ORDER BY criado_em DESC LIMIT 1",
            (usuario["id"],),
        ).fetchone()
    finally:
        conexao.close()
    if not linha:
        raise HTTPException(status_code=409, detail="Configuracao de 2FA nao encontrada")
    if not verificar_totp(linha["secret"], dados.codigo):
        raise HTTPException(status_code=400, detail="Codigo TOTP invalido")
    confirmado_em = db.agora()
    expira_em = _expiracao(horas=8)
    conexao = db.ligacao()
    try:
        conexao.execute(
            "UPDATE seguranca_2fa SET confirmado_em = ? WHERE user_id = ?",
            (confirmado_em, usuario["id"]),
        )
        conexao.execute(
            "INSERT OR REPLACE INTO sessoes_2fa (token, confirmado_em, expira_em) VALUES (?, ?, ?)",
            (usuario["token"], confirmado_em, expira_em),
        )
        conexao.commit()
    finally:
        conexao.close()
    return {"confirmado_em": confirmado_em, "expira_em": expira_em}


@router.post("/break-the-glass")
def autorizar_break_glass(
    dados: BreakGlassModel,
    usuario: dict = Depends(exigir_perfil("medico", "enfermeiro", "administrador")),
) -> dict:
    identificador = criar_id("BTG")
    criado_em = db.agora()
    expira_em = _expiracao(minutos=30)
    justificacao = dados.justificacao.strip()
    conexao = db.ligacao()
    try:
        conexao.execute(
            "INSERT INTO acessos_excecionais (id, user_id, episodio_id, justificacao, criado_em, expira_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (identificador, usuario["id"], dados.episodio_id, justificacao, criado_em, expira_em),
        )
        security.registrar_auditoria(
            conexao,
            usuario,
            "ACEDERO_BREAK_THE_GLASS",
            dados.episodio_id,
            novo={"id": identificador, "justificacao": justificacao, "expira_em": expira_em},
        )
        security.criar_alerta(
            conexao,
            "CRITICO",
            f"Acesso excecional ao episodio {dados.episodio_id} por {usuario.get('nome')}: {justificacao}",
        )
        security.registrar_evento(
            conexao,
            "AcessoExcecionalAutorizado",
            {
                "id": identificador,
                "user_id": usuario["id"],
                "episodio_id": dados.episodio_id,
                "expira_em": expira_em,
            },
        )
        conexao.commit()
    finally:
        conexao.close()
    return {"id": identificador, "expira_em": expira_em}


@router.post("/assinaturas/verificar")
def verificar_assinatura(dados: AssinaturaModel) -> dict:
    try:
        payload = verificar_jws(dados.token, get_chaves()[1])
    except (ValueError, InvalidSignature, TypeError):
        return {"payload": None, "valido": False}
    return {"payload": payload, "valido": True}


@router.get("/contexto")
def contexto(request: Request, usuario: dict = Depends(usuario_hospitalar)) -> dict:
    return {
        "usuario": usuario,
        "unidade": getattr(request.state, "hospital_unit", None),
        "nivel": getattr(request.state, "nivel_hierarquico", 4),
        "dois_fatores_confirmada": sessao_2fa_confirmada(usuario.get("token")),
        "acesso_excecional_ativo": acesso_excecional_ativo(usuario),
    }

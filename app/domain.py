import uuid
from collections.abc import Mapping

from sqlite3 import Row

CORES_MANCHESTER: Mapping[str, int] = {
    "VERMELHO": 1,
    "LARANJA": 2,
    "AMARELO": 3,
    "VERDE": 4,
    "AZUL": 5,
}

TRANSICOES: Mapping[str, set[str]] = {
    "ADMITIDO": {"AGUARDANDO_TRIAGEM", "EM_TRIAGEM"},
    "AGUARDANDO_TRIAGEM": {"EM_TRIAGEM", "AGUARDANDO_MEDICO"},
    "EM_TRIAGEM": {"AGUARDANDO_MEDICO"},
    "AGUARDANDO_MEDICO": {"EM_ATENDIMENTO", "EM_OBSERVACAO"},
    "EM_ATENDIMENTO": {"AGUARDANDO_EXAMES_OU_MEDICACAO", "EM_OBSERVACAO", "ALTA_MEDICA_DADA", "INTERNADO_ATIVO"},
    "AGUARDANDO_EXAMES_OU_MEDICACAO": {"EM_ATENDIMENTO", "EM_OBSERVACAO", "ALTA_MEDICA_DADA"},
    "EM_OBSERVACAO": {"ALTA_MEDICA_DADA", "INTERNADO_ATIVO", "TRANSFERIDO"},
    "INTERNADO_ATIVO": {"EM_CIRURGIA", "ALTA_MEDICA_DADA", "OBITO", "TRANSFERIDO"},
    "EM_CIRURGIA": {"INTERNADO_ATIVO", "ALTA_MEDICA_DADA", "OBITO"},
    "ALTA_MEDICA_DADA": {"ALTA_ADMINISTRATIVA_CONCLUIDA"},
    "ALTA_ADMINISTRATIVA_CONCLUIDA": set(),
    "OBITO": {"ALTA_ADMINISTRATIVA_CONCLUIDA"},
    "TRANSFERIDO": {"ALTA_ADMINISTRATIVA_CONCLUIDA"},
    "AGENDADO": {"CHECK_IN_REALIZADO", "CANCELADO"},
    "CHECK_IN_REALIZADO": {"PRE_CONSULTA", "FALTOU"},
    "PRE_CONSULTA": {"EM_CONSULTA"},
    "EM_CONSULTA": {"FINALIZADO"},
    "FINALIZADO": set(),
    "CANCELADO": set(),
    "FALTOU": set(),
}

ESTADOS_FINAIS = {"ALTA_ADMINISTRATIVA_CONCLUIDA", "FINALIZADO", "CANCELADO", "FALTOU", "TRANSFERIDO", "OBITO"}
ESTADOS_SEM_PRESCRICAO = ESTADOS_FINAIS | {"ALTA_MEDICA_DADA"}


class EstadoInvalido(ValueError):
    pass


def criar_id(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:12]}"


def prioridade_manchester(cor: str) -> int:
    try:
        return CORES_MANCHESTER[cor.strip().upper()]
    except (AttributeError, KeyError) as exc:
        raise ValueError("Cor de triagem invalida. Usa VERMELHO, LARANJA, AMARELO, VERDE ou AZUL.") from exc


def validar_transicao(estado_atual: str, novo_estado: str) -> str:
    permitidos = TRANSICOES.get(estado_atual, set())
    if novo_estado not in permitidos:
        raise EstadoInvalido(f"Transicao invalida: {estado_atual} -> {novo_estado}")
    return novo_estado


def em_dict(linha: Row | None) -> dict | None:
    return dict(linha) if linha is not None else None


def em_lista(linhas) -> list[dict]:
    return [dict(linha) for linha in linhas]

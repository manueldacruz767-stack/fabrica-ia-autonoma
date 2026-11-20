from fabrica_core import acoes_externas_ativas, executar_comando


def executar_comando_sistema(comando: str) -> str:
    if not acoes_externas_ativas():
        return f"[BLOQUEADO] FABRICA_ACOES_EXTERNAS desativado; nao executado: {comando}"
    return executar_comando(comando)


if __name__ == "__main__":
    print("Modulo de ferramentas de sistema carregado.")

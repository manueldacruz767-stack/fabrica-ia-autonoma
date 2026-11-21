MIGRACOES = [
    """CREATE TABLE IF NOT EXISTS seguranca_2fa (
        user_id TEXT PRIMARY KEY,
        secret TEXT,
        confirmado_em TEXT,
        criado_em TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS sessoes_2fa (
        token TEXT PRIMARY KEY,
        confirmado_em TEXT,
        expira_em TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS acessos_excecionais (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        episodio_id TEXT,
        justificacao TEXT,
        criado_em TEXT,
        expira_em TEXT
    )""",
]


def eh_postgres(conexao) -> bool:
    modulo = type(conexao).__module__.lower()
    return modulo.startswith("psycopg") or "postgres" in modulo


def adaptar_marcadores(consulta: str, conexao) -> str:
    if not eh_postgres(conexao):
        return consulta
    resultado = []
    dentro_texto = False
    indice = 0
    while indice < len(consulta):
        caractere = consulta[indice]
        if caractere == "'":
            if dentro_texto and indice + 1 < len(consulta) and consulta[indice + 1] == "'":
                resultado.append("''")
                indice += 2
                continue
            dentro_texto = not dentro_texto
            resultado.append(caractere)
        elif caractere == "?" and not dentro_texto:
            resultado.append("%s")
        elif caractere == "\\" and dentro_texto and indice + 1 < len(consulta):
            resultado.append(consulta[indice : indice + 2])
            indice += 2
            continue
        else:
            resultado.append(caractere)
        indice += 1
    return "".join(resultado)


def executar_migracoes(conexao) -> int:
    for consulta in MIGRACOES:
        conexao.execute(adaptar_marcadores(consulta, conexao))
    conexao.commit()
    return len(MIGRACOES)

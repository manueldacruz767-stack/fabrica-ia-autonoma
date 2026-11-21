import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import db
from app.domain import (
    ESTADOS_FINAIS,
    EstadoInvalido,
    criar_id,
    em_lista,
    prioridade_manchester,
    validar_transicao,
)
from app.security import (
    autenticar,
    criar_alerta,
    exigir,
    registrar_auditoria,
    registrar_evento,
    usuario_atual,
)

db.inicializar()

app = FastAPI(title="HIS - Sistema de Gestao Hospitalar", version="0.1.0")
DIRETORIO_STATIC = Path(__file__).resolve().parent / "static"


class LoginModel(BaseModel):
    username: str
    password: str


class BreakGlassModel(BaseModel):
    episodio_id: str
    justificacao: str = Field(min_length=8)


class PacienteModel(BaseModel):
    nome: str = Field(min_length=2)
    documento: str | None = None
    data_nascimento: str | None = None
    desconhecido: bool = False


class EpisodioModel(BaseModel):
    paciente_id: str
    tipo: str = "URGENCIA"


class TriagemModel(BaseModel):
    queixa: str = Field(min_length=3)
    sinais_vitais: str = Field(min_length=3)
    cor: str


class NotaModel(BaseModel):
    anamnese: str = Field(min_length=3)
    hipotese: str = Field(min_length=3)


class PrescricaoModel(BaseModel):
    medicamento: str = Field(min_length=2)
    dose: str = Field(min_length=2)


class StockModel(BaseModel):
    medicamento: str = Field(min_length=2)
    quantidade: int = Field(ge=0)
    minimo: int = Field(ge=0)


class AlocacaoModel(BaseModel):
    episodio_id: str


@contextmanager
def conexao_aberta():
    conexao = db.ligacao()
    try:
        yield conexao
    finally:
        conexao.close()


@app.exception_handler(EstadoInvalido)
async def estado_invalido_handler(request: Request, exc: EstadoInvalido) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


def obter_episodio(conexao, episodio_id: str):
    linha = conexao.execute("SELECT * FROM episodes WHERE id = ?", (episodio_id,)).fetchone()
    if not linha:
        raise HTTPException(status_code=404, detail="Episodio nao encontrado")
    return linha


def obter_prescricao(conexao, prescricao_id: str):
    linha = conexao.execute("SELECT * FROM prescriptions WHERE id = ?", (prescricao_id,)).fetchone()
    if not linha:
        raise HTTPException(status_code=404, detail="Prescricao nao encontrada")
    return linha


def validar_dose(dose: str) -> None:
    encontrado = re.search(r"(\d+(?:\.\d+)?)\s*(mg|ml|g)\b", dose.strip(), flags=re.IGNORECASE)
    if not encontrado:
        raise HTTPException(status_code=400, detail="Dose invalida. Exemplo: 500mg")
    valor = float(encontrado.group(1))
    unidade = encontrado.group(2).lower()
    limite = 10 if unidade == "g" else 1000
    if valor <= 0 or valor > limite:
        raise HTTPException(status_code=400, detail=f"Dose fora do intervalo seguro para {unidade}")


@app.post("/api/auth/login")
def login(dados: LoginModel, request: Request) -> dict:
    with conexao_aberta() as conexao:
        usuario = autenticar(conexao, dados.username, dados.password)
        if not usuario:
            raise HTTPException(status_code=401, detail="Credenciais invalidas")
        usuario["ip"] = request.client.host if request.client else "desconhecido"
        registrar_auditoria(conexao, usuario, "LOGIN", usuario["username"])
        conexao.commit()
        return {
            "token": usuario["token"],
            "username": usuario["username"],
            "nome": usuario["nome"],
            "perfil": usuario["perfil"],
        }


@app.get("/api/me")
def eu(usuario: dict = Depends(usuario_atual)) -> dict:
    return {chave: usuario[chave] for chave in ("id", "username", "nome", "perfil")}


@app.post("/api/acesso-emergencia")
def acesso_emergencia(dados: BreakGlassModel, usuario: dict = Depends(usuario_atual)) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, dados.episodio_id)
        if episodio["estado"] in ESTADOS_FINAIS:
            raise HTTPException(status_code=400, detail="Episodio ja encerrado")
        expira_em = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(timespec="seconds")
        conexao.execute(
            "INSERT INTO elevations (token, episode_id, expira_em, justificacao) VALUES (?, ?, ?, ?)",
            (usuario["token"], dados.episodio_id, expira_em, dados.justificacao),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "BREAK_THE_GLASS",
            dados.episodio_id,
            novo={"justificacao": dados.justificacao, "expira_em": expira_em},
        )
        criar_alerta(
            conexao,
            "CRITICO",
            f"Break-the-glass no episodio {dados.episodio_id} por {usuario['nome']}: {dados.justificacao}",
        )
        conexao.commit()
    return {"autorizado": True, "expira_em": expira_em}


@app.post("/api/pacientes", status_code=201)
def criar_paciente(
    dados: PacienteModel,
    usuario: dict = Depends(exigir("enfermeiro", "medico", "administrador")),
) -> dict:
    paciente_id = criar_id("PAC")
    with conexao_aberta() as conexao:
        conexao.execute(
            "INSERT INTO patients (id, nome, documento, data_nascimento, desconhecido, criado_por, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                paciente_id,
                dados.nome.strip(),
                dados.documento,
                dados.data_nascimento,
                int(dados.desconhecido),
                usuario["id"],
                db.agora(),
            ),
        )
        registrar_auditoria(conexao, usuario, "PACIENTE_CRIADO", paciente_id, novo=dados.model_dump())
        conexao.commit()
    return {"id": paciente_id, "nome": dados.nome.strip()}


@app.get("/api/pacientes")
def listar_pacientes(usuario: dict = Depends(exigir("medico", "enfermeiro", "farmacia", "gestor", "auditoria"))) -> list[dict]:
    with conexao_aberta() as conexao:
        linhas = conexao.execute("SELECT * FROM patients ORDER BY criado_em DESC").fetchall()
        return em_lista(linhas)


@app.post("/api/episodios", status_code=201)
def criar_episodio(
    dados: EpisodioModel,
    usuario: dict = Depends(exigir("enfermeiro", "medico", "administrador")),
) -> dict:
    tipo = dados.tipo.strip().upper()
    if tipo not in {"URGENCIA", "AMBULATORIO"}:
        raise HTTPException(status_code=400, detail="Tipo deve ser URGENCIA ou AMBULATORIO")
    estado = "AGUARDANDO_TRIAGEM" if tipo == "URGENCIA" else "AGENDADO"
    episodio_id = criar_id("EPI")
    with conexao_aberta() as conexao:
        paciente = conexao.execute("SELECT 1 FROM patients WHERE id = ?", (dados.paciente_id,)).fetchone()
        if not paciente:
            raise HTTPException(status_code=404, detail="Paciente nao encontrado")
        agora = db.agora()
        conexao.execute(
            "INSERT INTO episodes (id, patient_id, tipo, estado, criado_por, criado_em, atualizado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (episodio_id, dados.paciente_id, tipo, estado, usuario["id"], agora, agora),
        )
        registrar_auditoria(conexao, usuario, "EPISODIO_CRIADO", episodio_id, novo={"tipo": tipo, "estado": estado})
        conexao.commit()
    return {"id": episodio_id, "estado": estado, "tipo": tipo}


@app.get("/api/episodios")
def listar_episodios(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        linhas = conexao.execute(
            """
            SELECT e.*, p.nome AS paciente_nome, t.cor, t.prioridade, t.criado_em AS triagem_em
            FROM episodes e
            JOIN patients p ON p.id = e.patient_id
            LEFT JOIN triages t ON t.episode_id = e.id
                AND t.criado_em = (SELECT MAX(criado_em) FROM triages WHERE episode_id = e.id)
            ORDER BY e.criado_em DESC
            """
        ).fetchall()
        return em_lista(linhas)


@app.get("/api/fila")
def fila_medica(usuario: dict = Depends(exigir("medico", "enfermeiro", "gestor", "administrador"))) -> list[dict]:
    with conexao_aberta() as conexao:
        linhas = conexao.execute(
            """
            SELECT t.cor, t.prioridade, t.criado_em AS triagem_em, e.id AS episodio_id,
                   e.estado, p.id AS paciente_id, p.nome AS paciente_nome
            FROM triages t
            JOIN episodes e ON e.id = t.episode_id
            JOIN patients p ON p.id = e.patient_id
            WHERE e.estado IN ('AGUARDANDO_MEDICO', 'AGUARDANDO_EXAMES_OU_MEDICACAO', 'EM_OBSERVACAO')
            ORDER BY t.prioridade ASC, t.criado_em ASC
            """
        ).fetchall()
        return em_lista(linhas)


@app.post("/api/episodios/{episodio_id}/triagem")
def registar_triagem(
    episodio_id: str,
    dados: TriagemModel,
    usuario: dict = Depends(exigir("enfermeiro", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        if episodio["estado"] in ESTADOS_FINAIS:
            raise HTTPException(status_code=400, detail="Episodio encerrado")
        prioridade = prioridade_manchester(dados.cor)
        estado = episodio["estado"]
        if estado != "AGUARDANDO_MEDICO":
            estado = validar_transicao(estado, "AGUARDANDO_MEDICO")
        triagem_id = criar_id("TRI")
        conexao.execute(
            "INSERT INTO triages (id, episode_id, queixa, sinais_vitais, cor, prioridade, enfermeiro_id, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                triagem_id,
                episodio_id,
                dados.queixa.strip(),
                dados.sinais_vitais.strip(),
                dados.cor.strip().upper(),
                prioridade,
                usuario["id"],
                db.agora(),
            ),
        )
        conexao.execute(
            "UPDATE episodes SET estado = ?, atualizado_em = ? WHERE id = ?",
            (estado, db.agora(), episodio_id),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "TRIAGEM_REGISTADA",
            episodio_id,
            novo={"cor": dados.cor.strip().upper(), "prioridade": prioridade},
        )
        registrar_evento(
            conexao,
            "TriagemRegistada",
            {"episodio_id": episodio_id, "cor": dados.cor.strip().upper(), "prioridade": prioridade},
        )
        conexao.commit()
    return {"id": triagem_id, "estado": estado, "cor": dados.cor.strip().upper(), "prioridade": prioridade}


def pode_ver_prontuario(usuario: dict, episodio: dict) -> bool:
    if usuario["perfil"] in {"medico", "enfermeiro", "administrador", "auditoria"}:
        return True
    return False


@app.get("/api/episodios/{episodio_id}/prontuario")
def ver_prontuario(episodio_id: str, usuario: dict = Depends(usuario_atual)) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        elevado = conexao.execute(
            "SELECT 1 FROM elevations WHERE token = ? AND episode_id = ? AND expira_em > ?",
            (usuario["token"], episodio_id, db.agora()),
        ).fetchone()
        if not pode_ver_prontuario(usuario, episodio) and not elevado:
            raise HTTPException(status_code=403, detail="Prontuario restrito; usa acesso de emergencia justificado")
        triagens = em_lista(
            conexao.execute("SELECT * FROM triages WHERE episode_id = ? ORDER BY criado_em", (episodio_id,)).fetchall()
        )
        notas = em_lista(
            conexao.execute("SELECT * FROM notes WHERE episode_id = ? ORDER BY criado_em", (episodio_id,)).fetchall()
        )
        prescricoes = em_lista(
            conexao.execute("SELECT * FROM prescriptions WHERE episode_id = ? ORDER BY criado_em", (episodio_id,)).fetchall()
        )
        if elevado:
            registrar_auditoria(conexao, usuario, "PRONTUARIO_ACESSO_EMERGENCIA", episodio_id)
            conexao.commit()
        return {"episodio": dict(episodio), "triagens": triagens, "notas": notas, "prescricoes": prescricoes}


@app.post("/api/episodios/{episodio_id}/atendimento")
def registar_atendimento(
    episodio_id: str,
    dados: NotaModel,
    usuario: dict = Depends(exigir("medico", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        if episodio["estado"] in ESTADOS_FINAIS:
            raise HTTPException(status_code=400, detail="Episodio encerrado")
        estado = episodio["estado"]
        if estado != "EM_ATENDIMENTO":
            estado = validar_transicao(estado, "EM_ATENDIMENTO")
        nota_id = criar_id("NOT")
        conexao.execute(
            "INSERT INTO notes (id, episode_id, autor_id, anamnese, hipotese, criado_em) VALUES (?, ?, ?, ?, ?, ?)",
            (nota_id, episodio_id, usuario["id"], dados.anamnese.strip(), dados.hipotese.strip(), db.agora()),
        )
        conexao.execute(
            "UPDATE episodes SET estado = ?, atualizado_em = ? WHERE id = ?",
            (estado, db.agora(), episodio_id),
        )
        registrar_auditoria(conexao, usuario, "ATENDIMENTO_REGISTADO", episodio_id, novo={"nota_id": nota_id})
        registrar_evento(conexao, "AtendimentoRegistado", {"episodio_id": episodio_id, "nota_id": nota_id})
        conexao.commit()
    return {"id": nota_id, "estado": estado}


@app.post("/api/episodios/{episodio_id}/prescricoes", status_code=201)
def criar_prescricao(
    episodio_id: str,
    dados: PrescricaoModel,
    usuario: dict = Depends(exigir("medico", "administrador")),
) -> dict:
    validar_dose(dados.dose)
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        if episodio["estado"] in ESTADOS_FINAIS:
            raise HTTPException(status_code=400, detail="Episodio encerrado")
        nota = conexao.execute("SELECT 1 FROM notes WHERE episode_id = ? LIMIT 1", (episodio_id,)).fetchone()
        if not nota:
            raise HTTPException(status_code=400, detail="Regista o atendimento antes de prescrever")
        medicamento = dados.medicamento.strip()
        stock = conexao.execute("SELECT * FROM stock WHERE medicamento = ?", (medicamento,)).fetchone()
        if not stock:
            raise HTTPException(status_code=404, detail="Medicamento nao existe no stock")
        if stock["quantidade"] <= 0:
            raise HTTPException(status_code=400, detail="Medicamento sem stock disponivel")
        prescricao_id = criar_id("PRE")
        conexao.execute(
            "INSERT INTO prescriptions (id, episode_id, medicamento, dose, prescritor_id, estado, criado_em) "
            "VALUES (?, ?, ?, ?, ?, 'PENDENTE', ?)",
            (prescricao_id, episodio_id, medicamento, dados.dose.strip(), usuario["id"], db.agora()),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "PRESCRICAO_CRIADA",
            prescricao_id,
            novo={"medicamento": medicamento, "dose": dados.dose.strip()},
        )
        registrar_evento(
            conexao,
            "PrescricaoCriada",
            {"prescricao_id": prescricao_id, "medicamento": medicamento, "episodio_id": episodio_id},
        )
        conexao.commit()
    return {"id": prescricao_id, "estado": "PENDENTE"}


@app.post("/api/prescricoes/{prescricao_id}/dispensar")
def dispensar_prescricao(
    prescricao_id: str,
    usuario: dict = Depends(exigir("farmacia", "enfermeiro", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        prescricao = obter_prescricao(conexao, prescricao_id)
        if prescricao["estado"] != "PENDENTE":
            raise HTTPException(status_code=400, detail="Prescricao ja processada")
        if prescricao["prescritor_id"] == usuario["id"]:
            raise HTTPException(status_code=403, detail="Segregacao de funcoes: quem prescreve nao dispensa")
        stock = conexao.execute("SELECT * FROM stock WHERE medicamento = ?", (prescricao["medicamento"],)).fetchone()
        if not stock or stock["quantidade"] < 1:
            raise HTTPException(status_code=400, detail="Stock insuficiente")
        nova_quantidade = stock["quantidade"] - 1
        conexao.execute(
            "UPDATE stock SET quantidade = ? WHERE id = ?",
            (nova_quantidade, stock["id"]),
        )
        conexao.execute(
            "UPDATE prescriptions SET estado = 'DISPENSADA' WHERE id = ?",
            (prescricao_id,),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "MEDICACAO_DISPENSADA",
            prescricao_id,
            anterior={"quantidade": stock["quantidade"]},
            novo={"quantidade": nova_quantidade},
        )
        registrar_evento(
            conexao,
            "MedicacaoAdministrada",
            {"prescricao_id": prescricao_id, "medicamento": prescricao["medicamento"]},
        )
        if nova_quantidade < stock["minimo"]:
            criar_alerta(
                conexao,
                "ALTO",
                f"Stock critico de {prescricao['medicamento']}: {nova_quantidade} unidades",
            )
        conexao.commit()
    return {"id": prescricao_id, "estado": "DISPENSADA", "quantidade_restante": nova_quantidade}


@app.post("/api/episodios/{episodio_id}/alta-medica")
def alta_medica(episodio_id: str, usuario: dict = Depends(exigir("medico", "administrador"))) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        nota = conexao.execute("SELECT 1 FROM notes WHERE episode_id = ? LIMIT 1", (episodio_id,)).fetchone()
        if not nota:
            raise HTTPException(status_code=400, detail="Alta medica exige registo de atendimento")
        validar_transicao(episodio["estado"], "ALTA_MEDICA_DADA")
        leito = conexao.execute("SELECT * FROM beds WHERE episodio_id = ? AND estado = 'OCUPADO'", (episodio_id,)).fetchone()
        tarefa_id = None
        if leito:
            tarefa_id = criar_id("HIG")
            conexao.execute(
                "UPDATE beds SET estado = 'HIGIENIZACAO' WHERE id = ?",
                (leito["id"],),
            )
            conexao.execute(
                "INSERT INTO hygiene_tasks (id, bed_id, estado, criado_em) VALUES (?, ?, 'PENDENTE', ?)",
                (tarefa_id, leito["id"], db.agora()),
            )
        conexao.execute(
            "UPDATE episodes SET estado = ?, atualizado_em = ? WHERE id = ?",
            ("ALTA_MEDICA_DADA", db.agora(), episodio_id),
        )
        registrar_auditoria(conexao, usuario, "ALTA_MEDICA", episodio_id, anterior={"estado": episodio["estado"]})
        registrar_evento(
            conexao,
            "AltaMedicaRegistada",
            {"episodio_id": episodio_id, "leito": leito["codigo"] if leito else None, "higienizacao": tarefa_id},
        )
        conexao.commit()
    return {"estado": "ALTA_MEDICA_DADA", "tarefa_higienizacao": tarefa_id}


@app.post("/api/episodios/{episodio_id}/alta-administrativa")
def alta_administrativa(episodio_id: str, usuario: dict = Depends(exigir("administrador", "gestor"))) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        validar_transicao(episodio["estado"], "ALTA_ADMINISTRATIVA_CONCLUIDA")
        conexao.execute(
            "UPDATE episodes SET estado = ?, atualizado_em = ? WHERE id = ?",
            ("ALTA_ADMINISTRATIVA_CONCLUIDA", db.agora(), episodio_id),
        )
        registrar_auditoria(conexao, usuario, "ALTA_ADMINISTRATIVA", episodio_id, anterior={"estado": episodio["estado"]})
        registrar_evento(conexao, "AltaAdministrativaConcluida", {"episodio_id": episodio_id})
        conexao.commit()
    return {"estado": "ALTA_ADMINISTRATIVA_CONCLUIDA"}


@app.get("/api/leitos")
def listar_leitos(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM beds ORDER BY codigo").fetchall())


@app.post("/api/leitos/{leito_id}/alocar")
def alocar_leito(
    leito_id: str,
    dados: AlocacaoModel,
    usuario: dict = Depends(exigir("enfermeiro", "gestor", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        leito = conexao.execute("SELECT * FROM beds WHERE id = ?", (leito_id,)).fetchone()
        if not leito:
            raise HTTPException(status_code=404, detail="Leito nao encontrado")
        if leito["estado"] != "LIVRE":
            raise HTTPException(status_code=400, detail=f"Leito indisponivel: {leito['estado']}")
        episodio = obter_episodio(conexao, dados.episodio_id)
        if episodio["estado"] in ESTADOS_FINAIS:
            raise HTTPException(status_code=400, detail="Episodio encerrado")
        conexao.execute(
            "UPDATE beds SET estado = 'OCUPADO', paciente_id = ?, episodio_id = ? WHERE id = ?",
            (episodio["patient_id"], episodio["id"], leito_id),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "LEITO_ALOCADO",
            leito_id,
            anterior={"estado": leito["estado"]},
            novo={"episodio_id": episodio["id"]},
        )
        registrar_evento(conexao, "LeitoAlocado", {"leito": leito_id, "episodio_id": episodio["id"]})
        conexao.commit()
    return {"id": leito_id, "estado": "OCUPADO"}


@app.get("/api/higienizacao")
def listar_higienizacao(usuario: dict = Depends(exigir("limpeza", "gestor", "enfermeiro", "administrador"))) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute(
                "SELECT h.*, b.codigo FROM hygiene_tasks h JOIN beds b ON b.id = h.bed_id ORDER BY h.criado_em"
            ).fetchall()
        )


@app.post("/api/higienizacao/{tarefa_id}/concluir")
def concluir_higienizacao(
    tarefa_id: str,
    usuario: dict = Depends(exigir("limpeza", "gestor", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        tarefa = conexao.execute("SELECT * FROM hygiene_tasks WHERE id = ?", (tarefa_id,)).fetchone()
        if not tarefa:
            raise HTTPException(status_code=404, detail="Tarefa nao encontrada")
        if tarefa["estado"] != "PENDENTE":
            raise HTTPException(status_code=400, detail="Tarefa ja concluida")
        conexao.execute("UPDATE hygiene_tasks SET estado = 'CONCLUIDA', concluido_em = ? WHERE id = ?", (db.agora(), tarefa_id))
        conexao.execute(
            "UPDATE beds SET estado = 'LIVRE', paciente_id = NULL, episodio_id = NULL WHERE id = ?",
            (tarefa["bed_id"],),
        )
        registrar_auditoria(conexao, usuario, "HIGIENIZACAO_CONCLUIDA", tarefa["bed_id"])
        registrar_evento(conexao, "LeitoHigienizado", {"leito": tarefa["bed_id"]})
        conexao.commit()
    return {"id": tarefa_id, "estado": "CONCLUIDA"}


@app.get("/api/prescricoes/pendentes")
def listar_prescricoes_pendentes(
    usuario: dict = Depends(exigir("farmacia", "enfermeiro", "administrador")),
) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute(
                "SELECT p.*, e.patient_id FROM prescriptions p JOIN episodes e ON e.id = p.episode_id "
                "WHERE p.estado = 'PENDENTE' ORDER BY p.criado_em"
            ).fetchall()
        )


@app.get("/api/stock")
def listar_stock(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM stock ORDER BY medicamento").fetchall())


@app.post("/api/stock", status_code=201)
def atualizar_stock(
    dados: StockModel,
    usuario: dict = Depends(exigir("farmacia", "gestor", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        anterior = conexao.execute("SELECT * FROM stock WHERE medicamento = ?", (dados.medicamento.strip(),)).fetchone()
        identificador = anterior["id"] if anterior else criar_id("STK")
        conexao.execute(
            "INSERT INTO stock (id, medicamento, quantidade, minimo) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(medicamento) DO UPDATE SET quantidade = excluded.quantidade, minimo = excluded.minimo",
            (identificador, dados.medicamento.strip(), dados.quantidade, dados.minimo),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "STOCK_ATUALIZADO",
            identificador,
            anterior=dict(anterior) if anterior else None,
            novo=dados.model_dump(),
        )
        if dados.quantidade < dados.minimo:
            criar_alerta(
                conexao,
                "ALTO",
                f"Stock critico de {dados.medicamento.strip()}: {dados.quantidade} unidades",
            )
        conexao.commit()
    return {"id": identificador, "medicamento": dados.medicamento.strip()}


@app.get("/api/alertas")
def listar_alertas(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM alerts ORDER BY criado_em DESC").fetchall())


@app.get("/api/auditoria")
def listar_auditoria(usuario: dict = Depends(exigir("auditoria", "administrador"))) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 200").fetchall())


@app.get("/api/eventos")
def listar_eventos(usuario: dict = Depends(exigir("auditoria", "administrador"))) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM outbox ORDER BY id DESC LIMIT 200").fetchall())


@app.get("/api/dashboard")
def dashboard(usuario: dict = Depends(usuario_atual)) -> dict:
    marcadores = ",".join("?" for _ in ESTADOS_FINAIS)
    with conexao_aberta() as conexao:
        episodios_ativos = conexao.execute(
            f"SELECT COUNT(*) AS total FROM episodes WHERE estado NOT IN ({marcadores})",
            tuple(ESTADOS_FINAIS),
        ).fetchone()["total"]
        fila = conexao.execute(
            "SELECT COUNT(*) AS total FROM triages t JOIN episodes e ON e.id = t.episode_id "
            "WHERE e.estado = 'AGUARDANDO_MEDICO'"
        ).fetchone()["total"]
        leitos = {
            linha["estado"]: linha["total"]
            for linha in conexao.execute("SELECT estado, COUNT(*) AS total FROM beds GROUP BY estado").fetchall()
        }
        return {
            "pacientes": conexao.execute("SELECT COUNT(*) AS total FROM patients").fetchone()["total"],
            "episodios_ativos": episodios_ativos,
            "fila_medica": fila,
            "leitos_livres": leitos.get("LIVRE", 0),
            "leitos_ocupados": leitos.get("OCUPADO", 0),
            "leitos_higienizacao": leitos.get("HIGIENIZACAO", 0),
            "alertas": conexao.execute("SELECT COUNT(*) AS total FROM alerts WHERE lido = 0").fetchone()["total"],
            "stock_critico": conexao.execute("SELECT COUNT(*) AS total FROM stock WHERE quantidade < minimo").fetchone()["total"],
            "registos_auditoria": conexao.execute("SELECT COUNT(*) AS total FROM audit").fetchone()["total"],
        }


app.mount("/static", StaticFiles(directory=DIRETORIO_STATIC), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(DIRETORIO_STATIC / "index.html")

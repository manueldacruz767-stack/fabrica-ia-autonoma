import hashlib
import json
import os
import re
import socket
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import db
from app.consumidor_outbox import publicar_pendentes
from app.domain import (
    ESTADOS_FINAIS,
    ESTADOS_SEM_PRESCRICAO,
    EstadoInvalido,
    criar_id,
    em_lista,
    prioridade_manchester,
    validar_transicao,
)
from app.security import (
    assinar_documento,
    autenticar,
    criar_alerta,
    episodio_permitido,
    exigir,
    registrar_auditoria,
    registrar_bi,
    registrar_evento,
    unidade_permitida,
    usuario_atual,
)

db.inicializar()

app = FastAPI(title="HIS - Sistema de Gestao Hospitalar", version="0.1.0")
DIRETORIO_STATIC = Path(__file__).resolve().parent / "static"
METRICAS = {"requisicoes": 0, "erros": 0, "eventos_publicados": 0}
PAINEL_CLIENTES: set[WebSocket] = set()


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request.state.correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    METRICAS["requisicoes"] += 1
    try:
        resposta = await call_next(request)
    except Exception:
        METRICAS["erros"] += 1
        raise
    if resposta.status_code >= 500:
        METRICAS["erros"] += 1
    resposta.headers["X-Correlation-ID"] = request.state.correlation_id
    print(
        json.dumps(
            {
                "evento": "http_request",
                "correlation_id": request.state.correlation_id,
                "metodo": request.method,
                "caminho": request.url.path,
                "status": resposta.status_code,
                "utilizador": getattr(getattr(request.state, "usuario", None), "get", lambda *_: None)("id"),
            },
            sort_keys=True,
        )
    )
    return resposta


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
    justificacao_risco: str | None = None
    horarios: list[str] | None = None
    dieta: str | None = None


class StockModel(BaseModel):
    medicamento: str = Field(min_length=2)
    quantidade: int = Field(ge=0)
    minimo: int = Field(ge=0)


class AlocacaoModel(BaseModel):
    episodio_id: str
    motivo: str = "Internamento clinico"


class FuncionarioModel(BaseModel):
    nome: str = Field(min_length=2)
    perfil_funcional: str = Field(min_length=2)
    unidade: str = Field(min_length=2)


class EscalaModel(BaseModel):
    staff_id: str
    data: str = Field(min_length=8)
    turno: str
    unidade: str = Field(min_length=2)


class PedidoRhModel(BaseModel):
    staff_id: str
    tipo: str
    inicio: str = Field(min_length=8)
    fim: str = Field(min_length=8)
    justificacao: str | None = None


class ParecerModel(BaseModel):
    parecer: str = Field(min_length=5)
    aprovado: bool = True
    tipo: str | None = None


class RececaoModel(BaseModel):
    conferencia: str = Field(min_length=5)


class RequisicaoModel(BaseModel):
    descricao: str = Field(min_length=3)
    quantidade: int = Field(ge=1)
    valor: float = Field(gt=0)
    unidade: str = Field(min_length=2)


class BudgetModel(BaseModel):
    total: float = Field(gt=0)


class EmpenhoModel(BaseModel):
    purchase_id: str
    valor: float = Field(gt=0)


class MdtParametroModel(BaseModel):
    parametro: str = Field(min_length=2)
    valor: str = Field(min_length=1)
    unidade: str | None = None
    valor_referencia: str | None = None
    criticidade: str = "NORMAL"


class MdtPedidoModel(BaseModel):
    episodio_id: str
    tipo: str
    descricao: str = Field(min_length=3)
    parametros: list[MdtParametroModel] | None = None


class MdtResultadoModel(BaseModel):
    resultado: str = Field(min_length=3)


class CheckInModel(BaseModel):
    observacao: str | None = None


class PreConsultaModel(BaseModel):
    sinais_vitais: str = Field(min_length=3)
    observacao: str | None = None


class InternamentoModel(BaseModel):
    leito_id: str
    motivo: str = Field(min_length=3)


class CirurgiaModel(BaseModel):
    descricao: str = Field(min_length=3)
    checklist: str = Field(min_length=3)
    equipamento_id: str | None = None
    lote_id: str | None = None


class ConcluirCirurgiaModel(BaseModel):
    destino: str = "ENFERMARIA"


class EsterilizacaoModel(BaseModel):
    lote: str = Field(min_length=3)
    descricao: str = Field(min_length=3)
    esterilizado_em: str = Field(min_length=8)
    validade: str = Field(min_length=8)
    indicador_biologico: str = Field(min_length=2)


class EquipamentoModel(BaseModel):
    codigo: str = Field(min_length=2)
    descricao: str = Field(min_length=3)
    unidade: str = Field(min_length=2)
    proxima_manutencao: str = Field(min_length=8)


class ChamadoModel(BaseModel):
    equipamento_id: str
    descricao: str = Field(min_length=3)
    prioridade: str = "NORMAL"


class DocumentoAssinaturaModel(BaseModel):
    tipo_documento: str
    referencia_id: str
    conteudo: str = Field(min_length=3)


class ParecerRegistoModel(BaseModel):
    tipo: str
    parecer: str = Field(min_length=5)
    aprovado: bool = True


class SumarioAltaModel(BaseModel):
    diagnostico: str = Field(min_length=3)
    evolucao: str = Field(min_length=3)
    orientacoes: str = Field(min_length=3)
    medicamentos: str = Field(min_length=2)


class EvolucaoModel(BaseModel):
    nota: str = Field(min_length=3)
    conduta: str = Field(min_length=3)
    proxima_avaliacao: str = Field(min_length=8)


class BalancoHidricoModel(BaseModel):
    entradas_ml: int = Field(ge=0)
    saidas_ml: int = Field(ge=0)
    dieta: str = Field(min_length=2)
    turno: str


class TransferenciaModel(BaseModel):
    destino: str = Field(min_length=3)
    motivo: str = Field(min_length=3)
    veiculo: str = Field(min_length=2)
    acompanhante_id: str | None = None


class ObitoModel(BaseModel):
    causa: str = Field(min_length=3)
    data_obito: str = Field(min_length=8)


class ConsultaAgendadaModel(BaseModel):
    patient_id: str
    especialidade: str = Field(min_length=2)
    medico_id: str | None = None
    data_hora: str = Field(min_length=8)
    retorno_de_id: str | None = None


class MovimentoStockModel(BaseModel):
    unidade_codigo: str
    item: str = Field(min_length=2)
    tipo: str
    quantidade: int = Field(ge=1)
    destino: str | None = None


class ContratoModel(BaseModel):
    fornecedor: str = Field(min_length=2)
    objeto: str = Field(min_length=3)
    valor: float = Field(gt=0)
    inicio: str = Field(min_length=8)
    fim: str = Field(min_length=8)


class CotacaoModel(BaseModel):
    descricao: str = Field(min_length=3)
    quantidade: int = Field(ge=1)
    estimativa: float = Field(gt=0)


class PropostaModel(BaseModel):
    fornecedor: str = Field(min_length=2)
    valor: float = Field(gt=0)
    prazo: str = Field(min_length=2)


class FolhaSalarioModel(BaseModel):
    funcionario: str = Field(min_length=2)
    mes: str = Field(min_length=6)
    salario_base: float = Field(gt=0)
    descontos: float = Field(ge=0)


class PontoModel(BaseModel):
    funcionario: str = Field(min_length=2)
    data: str = Field(min_length=8)
    entrada: str = Field(min_length=3)
    saida: str | None = None


class AlergiaModel(BaseModel):
    substancia: str = Field(min_length=2)
    reacao: str = Field(min_length=2)


class AprazamentoModel(BaseModel):
    horarios: list[str] = Field(min_length=1)
    dieta: str | None = None
    observacao_dieta: str | None = None


class PrescricaoRiscoModel(BaseModel):
    justificacao: str = Field(min_length=10)


class AdministrarAprazamentoModel(BaseModel):
    observacao: str | None = None


class GuiaRemessaModel(BaseModel):
    unidade_destino: str = Field(min_length=2)
    item: str = Field(min_length=2)
    quantidade: int = Field(ge=1)


class ConcursoModel(BaseModel):
    cotacao_id: str
    numero: str = Field(min_length=2)


class OrdemModel(BaseModel):
    purchase_id: str


class OrdemFornecimentoModel(BaseModel):
    purchase_id: str
    descricao: str = Field(min_length=3)
    quantidade: int = Field(ge=1)


class ContratoTrabalhoModel(BaseModel):
    staff_id: str
    tipo: str = Field(min_length=2)
    inicio: str = Field(min_length=8)
    fim: str | None = None
    salario_base: float = Field(gt=0)


class ServicoGeralModel(BaseModel):
    area: str = Field(min_length=2)
    descricao: str = Field(min_length=3)


LIMITE_ALCADA_1 = 5000.0
PERFIS_ASSINATURA = {
    "RECEITA_MEDICA": {"medico"},
    "SUMARIO_ALTA": {"medico"},
    "EVOLUCAO_CLINICA": {"medico", "enfermeiro"},
    "PARECER_JURIDICO": {"juridico"},
    "PARECER_AUDITORIA": {"auditoria"},
    "CONTRATO_ALTA_VALOR": {"administrador", "compras", "financeiro"},
    "APROVACAO_COMPRA": {"administrador", "financeiro"},
    "LAUDO_MDT": {"laboratorio", "imagiologia", "fisioterapia", "administrador"},
    "GUIA_REMESSA": {"logistica", "enfermeiro", "administrador"},
    "ORDEM_PAGAMENTO": {"financeiro", "administrador"},
}
TIPO_PARECER_PERFIL = {"JURIDICO": "juridico", "AUDITORIA_INTERNA": "auditoria"}
PERFIS_MDT = {"LABORATORIO": "laboratorio", "IMAGEM": "imagiologia", "FISIOTERAPIA": "fisioterapia"}


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


def obter_pedido_rh(conexao, pedido_id: str):
    linha = conexao.execute("SELECT * FROM leave_requests WHERE id = ?", (pedido_id,)).fetchone()
    if not linha:
        raise HTTPException(status_code=404, detail="Pedido de RH nao encontrado")
    return linha


def obter_requisicao(conexao, requisicao_id: str):
    linha = conexao.execute("SELECT * FROM purchase_requests WHERE id = ?", (requisicao_id,)).fetchone()
    if not linha:
        raise HTTPException(status_code=404, detail="Requisicao nao encontrada")
    return linha


def obter_pedido_mdt(conexao, pedido_id: str):
    linha = conexao.execute("SELECT * FROM mdt_orders WHERE id = ?", (pedido_id,)).fetchone()
    if not linha:
        raise HTTPException(status_code=404, detail="Pedido de MDT nao encontrado")
    return linha


def orcamento_atual(conexao):
    exercicio = str(datetime.now(timezone.utc).year)
    linha = conexao.execute("SELECT * FROM budget WHERE exercicio = ?", (exercicio,)).fetchone()
    if not linha:
        raise HTTPException(status_code=404, detail="Orcamento do exercicio nao encontrado")
    return linha


def validar_abac_episodio(conexao, usuario: dict, episodio_id: str) -> None:
    if not episodio_permitido(conexao, usuario, episodio_id):
        raise HTTPException(status_code=403, detail="Acesso negado por unidade organizacional")


async def transmitir_painel(mensagem: dict) -> None:
    for cliente in list(PAINEL_CLIENTES):
        try:
            await cliente.send_json(mensagem)
        except Exception:
            PAINEL_CLIENTES.discard(cliente)


def gerar_hl7(pedido: dict, parametros: list[dict]) -> str:
    campos = [
        "MSH|^~\\&|HIS|HOSPITAL|MDT|HOSPITAL||OBX|1",
        f"OBR|1|{pedido['id']}||{pedido['tipo']}|||{pedido.get('concluido_em') or ''}",
    ]
    campos.extend(
        f"OBX|{indice}|ST|{parametro['parametro']}||{parametro['valor']}|{parametro.get('unidade') or ''}"
        for indice, parametro in enumerate(parametros, 1)
    )
    return "\r".join(campos)


def gerar_fhir(pedido: dict, parametros: list[dict]) -> dict:
    return {
        "resourceType": "DiagnosticReport",
        "id": pedido["id"],
        "status": "final" if pedido["estado"] in {"RESULTADO_DISPONIVEL", "VALIDADO"} else "preliminary",
        "code": {"text": pedido["tipo"]},
        "subject": {"reference": f"Patient/{pedido.get('patient_id') or 'desconhecido'}"},
        "conclusion": pedido.get("resultado"),
        "result": [
            {
                "display": parametro["parametro"],
                "valueQuantity": {"value": parametro["valor"], "unit": parametro.get("unidade") or "1"},
                "referenceRange": parametro.get("valor_referencia"),
            }
            for parametro in parametros
        ],
    }


@app.get("/health")
def health() -> dict:
    with conexao_aberta() as conexao:
        conexao.execute("SELECT 1").fetchone()
    dependencias = {}
    for nome, variavel, porta in (
        ("postgres", "POSTGRES_HOST", "5432"),
        ("redis", "REDIS_HOST", "6379"),
        ("rabbitmq", "RABBITMQ_HOST", "5672"),
    ):
        host = os.getenv(variavel)
        if not host:
            dependencias[nome] = "nao_configurado"
            continue
        try:
            with socket.create_connection((host, int(os.getenv(f"{variavel.split('_')[0]}_PORT", porta))), timeout=0.4):
                dependencias[nome] = "ok"
        except OSError:
            dependencias[nome] = "indisponivel"
    estado = "healthy" if all(valor != "indisponivel" for valor in dependencias.values()) else "degraded"
    return {"estado": estado, "db": "ok", "dependencias": dependencias, "versao": app.version}


@app.get("/metrics", include_in_schema=False)
def metrics() -> str:
    linhas = [
        "# HELP his_requisicoes_total Numero de requisicoes HTTP processadas.",
        "# TYPE his_requisicoes_total counter",
        f"his_requisicoes_total {METRICAS['requisicoes']}",
        "# HELP his_erros_total Numero de requisicoes com erro.",
        "# TYPE his_erros_total counter",
        f"his_erros_total {METRICAS['erros']}",
        "# HELP his_eventos_publicados_total Eventos do outbox publicados.",
        "# TYPE his_eventos_publicados_total counter",
        f"his_eventos_publicados_total {METRICAS['eventos_publicados']}",
    ]
    with conexao_aberta() as conexao:
        pendentes = conexao.execute(
            "SELECT COUNT(*) AS total FROM outbox WHERE estado = 'PENDENTE'"
        ).fetchone()["total"]
        alertas = conexao.execute("SELECT COUNT(*) AS total FROM alerts WHERE lido = 0").fetchone()["total"]
        internamentos = conexao.execute(
            "SELECT COUNT(*) AS total FROM episodes WHERE estado = 'INTERNADO_ATIVO'"
        ).fetchone()["total"]
    linhas.extend(
        [
            "# HELP his_outbox_pendente Eventos aguardando publicacao.",
            "# TYPE his_outbox_pendente gauge",
            f"his_outbox_pendente {pendentes}",
            "# HELP his_alertas_nao_lidos Alertas clinicos e operacionais nao lidos.",
            "# TYPE his_alertas_nao_lidos gauge",
            f"his_alertas_nao_lidos {alertas}",
            "# HELP his_internamentos_ativos Episodios em internamento ativo.",
            "# TYPE his_internamentos_ativos gauge",
            f"his_internamentos_ativos {internamentos}",
        ]
    )
    return "\n".join(linhas) + "\n"


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
    return {
        chave: usuario.get(chave)
        for chave in ("id", "username", "nome", "perfil", "unidade_codigo", "correlation_id")
    }


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


@app.post("/api/pacientes/{paciente_id}/alergias", status_code=201)
def registar_alergia(
    paciente_id: str,
    dados: AlergiaModel,
    usuario: dict = Depends(exigir("medico", "enfermeiro", "administrador")),
) -> dict:
    identificador = criar_id("ALG")
    with conexao_aberta() as conexao:
        if not conexao.execute("SELECT 1 FROM patients WHERE id = ?", (paciente_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Paciente nao encontrado")
        conexao.execute(
            "INSERT INTO alergias (id, patient_id, substancia, reacao, registado_por, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                identificador,
                paciente_id,
                dados.substancia.strip(),
                dados.reacao.strip(),
                usuario["id"],
                db.agora(),
            ),
        )
        registrar_auditoria(conexao, usuario, "ALERGIA_REGISTADA", identificador, novo=dados.model_dump())
        criar_alerta(conexao, "ALTO", f"Alergia registada: {dados.substancia} ({dados.reacao})")
        conexao.commit()
    return {"id": identificador}


@app.get("/api/pacientes/{paciente_id}/alergias")
def listar_alergias(
    paciente_id: str,
    usuario: dict = Depends(usuario_atual),
) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute("SELECT * FROM alergias WHERE patient_id = ? ORDER BY criado_em DESC", (paciente_id,)).fetchall()
        )


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
            "INSERT INTO episodes (id, patient_id, tipo, estado, criado_por, criado_em, atualizado_em, unidade_codigo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                episodio_id,
                dados.paciente_id,
                tipo,
                estado,
                usuario["id"],
                agora,
                agora,
                usuario.get("unidade_codigo"),
            ),
        )
        registrar_auditoria(conexao, usuario, "EPISODIO_CRIADO", episodio_id, novo={"tipo": tipo, "estado": estado})
        registrar_bi(conexao, "episodios", episodio_id, {"tipo": tipo, "estado": estado}, usuario)
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


@app.post("/api/episodios/{episodio_id}/check-in")
def registar_check_in(
    episodio_id: str,
    dados: CheckInModel,
    usuario: dict = Depends(exigir("enfermeiro", "medico", "administrador", "gestor")),
) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        if episodio["tipo"] != "AMBULATORIO":
            raise HTTPException(status_code=400, detail="Check-in so se aplica a episodio ambulatorial")
        estado = validar_transicao(episodio["estado"], "CHECK_IN_REALIZADO")
        conexao.execute(
            "UPDATE episodes SET estado = ?, atualizado_em = ? WHERE id = ?",
            (estado, db.agora(), episodio_id),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "CHECK_IN_REGISTADO",
            episodio_id,
            novo={"observacao": dados.observacao},
        )
        registrar_evento(conexao, "CheckInRealizado", {"episodio_id": episodio_id})
        conexao.commit()
    return {"estado": estado}


@app.post("/api/episodios/{episodio_id}/pre-consulta")
def registar_pre_consulta(
    episodio_id: str,
    dados: PreConsultaModel,
    usuario: dict = Depends(exigir("enfermeiro", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        estado = validar_transicao(episodio["estado"], "PRE_CONSULTA")
        identificador = criar_id("PRECON")
        conexao.execute(
            "INSERT INTO pre_consultas (id, episode_id, sinais_vitais, observacao, enfermeiro_id, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                identificador,
                episodio_id,
                dados.sinais_vitais.strip(),
                dados.observacao,
                usuario["id"],
                db.agora(),
            ),
        )
        conexao.execute(
            "UPDATE episodes SET estado = ?, atualizado_em = ? WHERE id = ?",
            (estado, db.agora(), episodio_id),
        )
        registrar_auditoria(conexao, usuario, "PRE_CONSULTA_REGISTADA", episodio_id, novo={"id": identificador})
        registrar_evento(conexao, "PreConsultaRegistada", {"episodio_id": episodio_id})
        conexao.commit()
    return {"id": identificador, "estado": estado}


@app.post("/api/episodios/{episodio_id}/atendimento")
def registar_atendimento(
    episodio_id: str,
    dados: NotaModel,
    usuario: dict = Depends(exigir("medico", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        if episodio["estado"] in ESTADOS_SEM_PRESCRICAO:
            raise HTTPException(status_code=400, detail="Episodio encerrado")
        estado = episodio["estado"]
        if episodio["tipo"] == "AMBULATORIO":
            if estado not in {"PRE_CONSULTA", "EM_CONSULTA"}:
                raise HTTPException(status_code=400, detail="Faz check-in e pre-consulta antes do atendimento")
            if estado == "PRE_CONSULTA":
                estado = validar_transicao(estado, "EM_CONSULTA")
        elif estado != "EM_ATENDIMENTO":
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


@app.post("/api/episodios/{episodio_id}/finalizar")
def finalizar_consulta(episodio_id: str, usuario: dict = Depends(exigir("medico", "administrador"))) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        estado = validar_transicao(episodio["estado"], "FINALIZADO")
        conexao.execute(
            "UPDATE episodes SET estado = ?, atualizado_em = ? WHERE id = ?",
            (estado, db.agora(), episodio_id),
        )
        registrar_auditoria(conexao, usuario, "CONSULTA_FINALIZADA", episodio_id)
        registrar_evento(conexao, "ConsultaFinalizada", {"episodio_id": episodio_id})
        conexao.commit()
    return {"estado": estado}


@app.post("/api/episodios/{episodio_id}/prescricoes", status_code=201)
def criar_prescricao(
    episodio_id: str,
    dados: PrescricaoModel,
    usuario: dict = Depends(exigir("medico", "administrador")),
) -> dict:
    validar_dose(dados.dose)
    with conexao_aberta() as conexao:
        validar_abac_episodio(conexao, usuario, episodio_id)
        episodio = obter_episodio(conexao, episodio_id)
        if episodio["estado"] in ESTADOS_SEM_PRESCRICAO:
            raise HTTPException(status_code=400, detail="Episodio encerrado para prescricao")
        nota = conexao.execute("SELECT 1 FROM notes WHERE episode_id = ? LIMIT 1", (episodio_id,)).fetchone()
        if not nota:
            raise HTTPException(status_code=400, detail="Regista o atendimento antes de prescrever")
        medicamento = dados.medicamento.strip()
        alergias = conexao.execute(
            "SELECT * FROM alergias WHERE patient_id = ? AND instr(lower(?), lower(substancia)) > 0",
            (episodio["patient_id"], medicamento),
        ).fetchall()
        risco = bool(alergias)
        if risco and not (dados.justificacao_risco or "").strip():
            raise HTTPException(
                status_code=409,
                detail="Acao de Risco: alergia registada. Exige justificacao escrita para prosseguir",
            )
        if risco:
            criar_alerta(
                conexao,
                "CRITICO",
                f"Prescricao com risco de alergia: {medicamento}. Justificacao: {dados.justificacao_risco}",
            )
        stock = conexao.execute("SELECT * FROM stock WHERE medicamento = ?", (medicamento,)).fetchone()
        if not stock:
            raise HTTPException(status_code=404, detail="Medicamento nao existe no stock")
        if stock["quantidade"] <= 0:
            raise HTTPException(status_code=400, detail="Medicamento sem stock disponivel")
        prescricao_id = criar_id("PRE")
        agora = db.agora()
        validade = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(timespec="seconds")
        conexao.execute(
            "INSERT INTO prescriptions (id, episode_id, medicamento, dose, prescritor_id, estado, criado_em, "
            "validade, risco_aceite, justificacao_risco, alergia_verificada) "
            "VALUES (?, ?, ?, ?, ?, 'PENDENTE', ?, ?, ?, ?, ?)",
            (
                prescricao_id,
                episodio_id,
                medicamento,
                dados.dose.strip(),
                usuario["id"],
                agora,
                validade,
                int(risco),
                (dados.justificacao_risco or "").strip() or None,
                int(risco),
            ),
        )
        for horario in dados.horarios or []:
            conexao.execute(
                "INSERT INTO aprazamentos (id, prescricao_id, horario, estado, criado_em) "
                "VALUES (?, ?, ?, 'PENDENTE', ?)",
                (criar_id("APZ"), prescricao_id, horario, agora),
            )
        if dados.dieta:
            conexao.execute(
                "INSERT INTO nutricao_dietas (id, episode_id, dieta, observacao, prescrita_por, criado_em) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    criar_id("NUT"),
                    episodio_id,
                    dados.dieta.strip(),
                    None,
                    usuario["id"],
                    agora,
                ),
            )
        registrar_auditoria(
            conexao,
            usuario,
            "PRESCRICAO_CRIADA",
            prescricao_id,
            novo={
                "medicamento": medicamento,
                "dose": dados.dose.strip(),
                "validade": validade,
                "risco_aceite": risco,
                "justificacao_risco": dados.justificacao_risco,
            },
        )
        registrar_evento(
            conexao,
            "PrescricaoCriada",
            {
                "prescricao_id": prescricao_id,
                "medicamento": medicamento,
                "episodio_id": episodio_id,
                "validade": validade,
                "risco_aceite": risco,
            },
        )
        registrar_bi(
            conexao,
            "prescricoes",
            prescricao_id,
            {"medicamento": medicamento, "risco_aceite": risco, "unidade": usuario.get("unidade_codigo")},
            usuario,
        )
        conexao.commit()
    return {
        "id": prescricao_id,
        "estado": "PENDENTE",
        "validade": validade,
        "risco_aceite": risco,
        "aprazamentos": len(dados.horarios or []),
    }


@app.get("/api/prescricoes/{prescricao_id}/aprazamentos")
def listar_aprazamentos(
    prescricao_id: str,
    usuario: dict = Depends(usuario_atual),
) -> list[dict]:
    with conexao_aberta() as conexao:
        obter_prescricao(conexao, prescricao_id)
        return em_lista(
            conexao.execute(
                "SELECT * FROM aprazamentos WHERE prescricao_id = ? ORDER BY horario",
                (prescricao_id,),
            ).fetchall()
        )


@app.post("/api/aprazamentos/{aprazamento_id}/administrar")
def administrar_aprazamento(
    aprazamento_id: str,
    usuario: dict = Depends(exigir("enfermeiro", "farmacia", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        aprazamento = conexao.execute("SELECT * FROM aprazamentos WHERE id = ?", (aprazamento_id,)).fetchone()
        if not aprazamento:
            raise HTTPException(status_code=404, detail="Aprazamento nao encontrado")
        if aprazamento["estado"] != "PENDENTE":
            raise HTTPException(status_code=400, detail="Aprazamento ja administrado")
        prescricao = obter_prescricao(conexao, aprazamento["prescricao_id"])
        if prescricao["validade"] and prescricao["validade"] < db.agora():
            raise HTTPException(status_code=400, detail="Prescricao expirada apos 24 horas")
        if prescricao["prescritor_id"] == usuario["id"]:
            raise HTTPException(status_code=403, detail="Segregacao de funcoes: quem prescreve nao administra")
        stock = conexao.execute(
            "SELECT * FROM stock WHERE medicamento = ?", (prescricao["medicamento"],)
        ).fetchone()
        if not stock or stock["quantidade"] < 1:
            raise HTTPException(status_code=400, detail="Stock insuficiente")
        nova_quantidade = stock["quantidade"] - 1
        administrado_em = db.agora()
        conexao.execute(
            "UPDATE aprazamentos SET estado = 'ADMINISTRADO', administrado_por = ?, administrado_em = ? WHERE id = ?",
            (usuario["id"], administrado_em, aprazamento_id),
        )
        conexao.execute("UPDATE stock SET quantidade = ? WHERE id = ?", (nova_quantidade, stock["id"]))
        restantes = conexao.execute(
            "SELECT COUNT(*) AS total FROM aprazamentos WHERE prescricao_id = ? AND estado = 'PENDENTE'",
            (prescricao["id"],),
        ).fetchone()["total"]
        if restantes == 0:
            conexao.execute(
                "UPDATE prescriptions SET estado = 'DISPENSADA' WHERE id = ?", (prescricao["id"],)
            )
        registrar_auditoria(
            conexao,
            usuario,
            "APRAZAMENTO_ADMINISTRADO",
            aprazamento_id,
            novo={"administrado_em": administrado_em, "stock_restante": nova_quantidade},
        )
        registrar_evento(
            conexao,
            "MedicacaoAdministrada",
            {"prescricao_id": prescricao["id"], "aprazamento_id": aprazamento_id},
        )
        conexao.commit()
    return {"id": aprazamento_id, "estado": "ADMINISTRADO", "quantidade_restante": nova_quantidade}


@app.get("/api/episodios/{episodio_id}/nutricao")
def listar_dietas(
    episodio_id: str,
    usuario: dict = Depends(usuario_atual),
) -> list[dict]:
    with conexao_aberta() as conexao:
        validar_abac_episodio(conexao, usuario, episodio_id)
        return em_lista(
            conexao.execute(
                "SELECT * FROM nutricao_dietas WHERE episode_id = ? ORDER BY criado_em DESC",
                (episodio_id,),
            ).fetchall()
        )


@app.post("/api/prescricoes/{prescricao_id}/dispensar")
def dispensar_prescricao(
    prescricao_id: str,
    usuario: dict = Depends(exigir("farmacia", "enfermeiro", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        prescricao = obter_prescricao(conexao, prescricao_id)
        if prescricao["estado"] != "PENDENTE":
            raise HTTPException(status_code=400, detail="Prescricao ja processada")
        if prescricao["validade"] and prescricao["validade"] < db.agora():
            raise HTTPException(status_code=400, detail="Prescricao expirada apos 24 horas")
        aprazamentos_pendentes = conexao.execute(
            "SELECT COUNT(*) AS total FROM aprazamentos WHERE prescricao_id = ? AND estado = 'PENDENTE'",
            (prescricao_id,),
        ).fetchone()["total"]
        if aprazamentos_pendentes:
            raise HTTPException(status_code=400, detail="Prescricao com aprazamento ativo: administrar por horario")
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
                "UPDATE internamentos SET estado = 'ENCERRADO', alta_em = ? WHERE episode_id = ? AND estado = 'ATIVO'",
                (db.agora(), episodio_id),
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
        estado = validar_transicao(episodio["estado"], "INTERNADO_ATIVO")
        conexao.execute(
            "UPDATE beds SET estado = 'OCUPADO', paciente_id = ?, episodio_id = ? WHERE id = ?",
            (episodio["patient_id"], episodio["id"], leito_id),
        )
        conexao.execute(
            "UPDATE episodes SET estado = ?, atualizado_em = ? WHERE id = ?",
            (estado, db.agora(), episodio["id"]),
        )
        internamento_id = criar_id("INT")
        conexao.execute(
            "INSERT INTO internamentos (id, episode_id, leito_id, motivo, estado, medico_id, criado_em) "
            "VALUES (?, ?, ?, ?, 'ATIVO', ?, ?)",
            (
                internamento_id,
                episodio["id"],
                leito_id,
                dados.motivo.strip(),
                usuario["id"],
                db.agora(),
            ),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "LEITO_ALOCADO",
            leito_id,
            anterior={"estado": leito["estado"]},
            novo={"episodio_id": episodio["id"]},
        )
        registrar_evento(
            conexao,
            "LeitoAlocado",
            {"leito": leito_id, "episodio_id": episodio["id"], "internamento_id": internamento_id},
        )
        conexao.commit()
    return {"id": leito_id, "estado": "OCUPADO", "internamento_id": internamento_id, "episodio_estado": estado}


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


@app.post("/api/eventos/publicar")
def publicar_eventos(usuario: dict = Depends(exigir("administrador", "ti"))) -> dict:
    resultado = publicar_pendentes()
    METRICAS["eventos_publicados"] += resultado["processados"]
    with conexao_aberta() as conexao:
        registrar_auditoria(
            conexao,
            usuario,
            "OUTBOX_PUBLICADO",
            "outbox",
            novo={"processados": resultado["processados"]},
        )
        conexao.commit()
    return resultado


@app.get("/api/dashboard")
def dashboard(usuario: dict = Depends(usuario_atual)) -> dict:
    with conexao_aberta() as conexao:
        episodios_ativos = conexao.execute(
            "SELECT COUNT(*) AS total FROM episodes WHERE estado NOT IN (?, ?, ?, ?, ?, ?)",
            tuple(sorted(ESTADOS_FINAIS)),
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
            "escalas_hoje": conexao.execute("SELECT COUNT(*) AS total FROM shifts WHERE data = date('now')").fetchone()["total"],
            "pedidos_rh_pendentes": conexao.execute(
                "SELECT COUNT(*) AS total FROM leave_requests WHERE estado IN ('PENDENTE_CHEFIA', 'PENDENTE_RH')"
            ).fetchone()["total"],
            "compras_pendentes": conexao.execute(
                "SELECT COUNT(*) AS total FROM purchase_requests WHERE estado NOT IN ('RECEBIDA', 'REJEITADA')"
            ).fetchone()["total"],
            "empenhos_ativos": conexao.execute(
                "SELECT COUNT(*) AS total FROM commitments WHERE estado = 'ATIVO'"
            ).fetchone()["total"],
            "mdt_pendentes": conexao.execute(
                "SELECT COUNT(*) AS total FROM mdt_orders WHERE estado IN ('PENDENTE', 'RESULTADO_DISPONIVEL')"
            ).fetchone()["total"],
            "internamentos_ativos": conexao.execute(
                "SELECT COUNT(*) AS total FROM internamentos WHERE estado = 'ATIVO'"
            ).fetchone()["total"],
            "cirurgias_em_curso": conexao.execute(
                "SELECT COUNT(*) AS total FROM cirurgias WHERE estado = 'EM_CIRURGIA'"
            ).fetchone()["total"],
            "equipamentos_bloqueados": conexao.execute(
                "SELECT COUNT(*) AS total FROM equipamentos WHERE estado = 'BLOQUEADO'"
            ).fetchone()["total"],
            "chamados_abertos": conexao.execute(
                "SELECT COUNT(*) AS total FROM chamados_manutencao WHERE estado = 'ABERTO'"
            ).fetchone()["total"],
        }


@app.post("/api/rh/funcionarios", status_code=201)
def criar_funcionario(
    dados: FuncionarioModel,
    usuario: dict = Depends(exigir("rh", "administrador")),
) -> dict:
    identificador = criar_id("FUN")
    with conexao_aberta() as conexao:
        conexao.execute(
            "INSERT INTO staff (id, nome, perfil_funcional, unidade) VALUES (?, ?, ?, ?)",
            (identificador, dados.nome.strip(), dados.perfil_funcional.strip(), dados.unidade.strip()),
        )
        registrar_auditoria(conexao, usuario, "FUNCIONARIO_CRIADO", identificador, novo=dados.model_dump())
        conexao.commit()
    return {"id": identificador, "nome": dados.nome.strip()}


@app.post("/api/cirurgias", status_code=201)
def criar_cirurgia(
    episodio_id: str,
    dados: CirurgiaModel,
    usuario: dict = Depends(exigir("medico", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        validar_abac_episodio(conexao, usuario, episodio_id)
        episodio = obter_episodio(conexao, episodio_id)
        estado = validar_transicao(episodio["estado"], "EM_CIRURGIA")
        if dados.lote_id:
            lote = conexao.execute("SELECT * FROM esterilizacoes WHERE id = ?", (dados.lote_id,)).fetchone()
            hoje = datetime.now(timezone.utc).date().isoformat()
            if not lote or lote["validade"] < hoje or lote["indicador_biologico"].upper() not in {"NEGATIVO", "OK", "VALIDADO"}:
                criar_alerta(conexao, "CRITICO", f"Lote esterilizado {dados.lote_id} vencido ou invalido")
                raise HTTPException(status_code=400, detail="Lote esterilizado vencido ou indicador biologico invalido")
        if dados.equipamento_id:
            equipamento = conexao.execute(
                "SELECT * FROM equipamentos WHERE id = ?", (dados.equipamento_id,)
            ).fetchone()
            hoje = datetime.now(timezone.utc).date().isoformat()
            if not equipamento or equipamento["estado"] != "ATIVO" or equipamento["proxima_manutencao"] < hoje:
                criar_alerta(
                    conexao,
                    "CRITICO",
                    f"Equipamento {dados.equipamento_id} indisponivel ou com manutencao vencida",
                )
                raise HTTPException(status_code=400, detail="Equipamento indisponivel ou com manutencao vencida")
        identificador = criar_id("CIR")
        conexao.execute(
            "INSERT INTO cirurgias (id, episode_id, descricao, checklist, equipamento_id, lote_id, estado, criado_por, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, 'EM_CIRURGIA', ?, ?)",
            (
                identificador,
                episodio_id,
                dados.descricao.strip(),
                dados.checklist.strip(),
                dados.equipamento_id,
                dados.lote_id,
                usuario["id"],
                db.agora(),
            ),
        )
        conexao.execute(
            "UPDATE episodes SET estado = ?, atualizado_em = ? WHERE id = ?",
            (estado, db.agora(), episodio_id),
        )
        registrar_auditoria(conexao, usuario, "CIRURGIA_INICIADA", identificador, novo={"descricao": dados.descricao})
        registrar_evento(conexao, "CirurgiaIniciada", {"cirurgia_id": identificador, "episodio_id": episodio_id})
        conexao.commit()
    return {"id": identificador, "estado": estado}


@app.post("/api/cirurgias/{cirurgia_id}/concluir")
def concluir_cirurgia(
    cirurgia_id: str,
    dados: ConcluirCirurgiaModel,
    usuario: dict = Depends(exigir("medico", "administrador")),
) -> dict:
    destino = dados.destino.strip().upper()
    if destino not in {"ENFERMARIA", "UCI"}:
        raise HTTPException(status_code=400, detail="Destino deve ser ENFERMARIA ou UCI")
    with conexao_aberta() as conexao:
        cirurgia = conexao.execute("SELECT * FROM cirurgias WHERE id = ?", (cirurgia_id,)).fetchone()
        if not cirurgia:
            raise HTTPException(status_code=404, detail="Cirurgia nao encontrada")
        if cirurgia["estado"] != "EM_CIRURGIA":
            raise HTTPException(status_code=400, detail="Cirurgia ja concluida")
        episodio = obter_episodio(conexao, cirurgia["episode_id"])
        estado = validar_transicao(episodio["estado"], "INTERNADO_ATIVO")
        leito = None
        if destino == "UCI":
            leito = conexao.execute(
                "SELECT * FROM beds WHERE unidade = 'UCI' AND estado = 'LIVRE' ORDER BY codigo LIMIT 1"
            ).fetchone()
            if not leito:
                raise HTTPException(status_code=409, detail="Sem leito de UCI disponivel")
            conexao.execute(
                "UPDATE beds SET estado = 'OCUPADO', paciente_id = ?, episodio_id = ? WHERE id = ?",
                (episodio["patient_id"], episodio["id"], leito["id"]),
            )
            conexao.execute(
                "UPDATE internamentos SET leito_id = ? WHERE episode_id = ? AND estado = 'ATIVO'",
                (leito["id"], episodio["id"]),
            )
        conexao.execute("UPDATE cirurgias SET estado = 'CONCLUIDA' WHERE id = ?", (cirurgia_id,))
        conexao.execute(
            "UPDATE episodes SET estado = ?, atualizado_em = ? WHERE id = ?",
            (estado, db.agora(), episodio["id"]),
        )
        registrar_auditoria(conexao, usuario, "CIRURGIA_CONCLUIDA", cirurgia_id, novo={"destino": destino})
        registrar_evento(
            conexao,
            "CirurgiaConcluida",
            {"cirurgia_id": cirurgia_id, "destino": destino, "leito": leito["id"] if leito else None},
        )
        conexao.commit()
    return {"id": cirurgia_id, "estado": estado, "destino": destino}


@app.get("/api/cirurgias")
def listar_cirurgias(usuario: dict = Depends(exigir("medico", "enfermeiro", "gestor", "auditoria", "administrador"))) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM cirurgias ORDER BY criado_em DESC").fetchall())


@app.post("/api/esterilizacoes", status_code=201)
def criar_esterilizacao(
    dados: EsterilizacaoModel,
    usuario: dict = Depends(exigir("enfermeiro", "farmacia", "logistica", "administrador")),
) -> dict:
    identificador = criar_id("EST")
    with conexao_aberta() as conexao:
        conexao.execute(
            "INSERT INTO esterilizacoes "
            "(id, lote, descricao, esterilizado_em, validade, indicador_biologico, responsavel_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                identificador,
                dados.lote.strip(),
                dados.descricao.strip(),
                dados.esterilizado_em,
                dados.validade,
                dados.indicador_biologico.strip(),
                usuario["id"],
            ),
        )
        registrar_auditoria(conexao, usuario, "ESTERILIZACAO_REGISTADA", identificador, novo={"lote": dados.lote})
        registrar_evento(conexao, "LoteEsterilizado", {"lote": dados.lote, "validade": dados.validade})
        conexao.commit()
    return {"id": identificador, "lote": dados.lote, "estado": "VALIDADO"}


@app.get("/api/esterilizacoes")
def listar_esterilizacoes(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM esterilizacoes ORDER BY esterilizado_em DESC").fetchall())


@app.post("/api/equipamentos", status_code=201)
def criar_equipamento(
    dados: EquipamentoModel,
    usuario: dict = Depends(exigir("gestor", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        conexao.execute(
            "INSERT INTO equipamentos (id, codigo, descricao, unidade, proxima_manutencao, estado) "
            "VALUES (?, ?, ?, ?, ?, 'ATIVO')",
            (
                dados.codigo,
                dados.codigo,
                dados.descricao.strip(),
                dados.unidade.strip(),
                dados.proxima_manutencao,
            ),
        )
        registrar_auditoria(conexao, usuario, "EQUIPAMENTO_CRIADO", dados.codigo, novo={"unidade": dados.unidade})
        conexao.commit()
    return {"id": dados.codigo, "estado": "ATIVO"}


@app.get("/api/equipamentos")
def listar_equipamentos(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM equipamentos ORDER BY codigo").fetchall())


@app.post("/api/manutencao/chamados", status_code=201)
def criar_chamado(
    dados: ChamadoModel,
    usuario: dict = Depends(usuario_atual),
) -> dict:
    prioridade = dados.prioridade.strip().upper()
    horas = {"CRITICA": 2, "ALTA": 24, "NORMAL": 72}
    if prioridade not in horas:
        raise HTTPException(status_code=400, detail="Prioridade deve ser CRITICA, ALTA ou NORMAL")
    identificador = criar_id("MAN")
    sla = (datetime.now(timezone.utc) + timedelta(hours=horas[prioridade])).isoformat(timespec="seconds")
    with conexao_aberta() as conexao:
        equipamento = conexao.execute("SELECT * FROM equipamentos WHERE id = ?", (dados.equipamento_id,)).fetchone()
        if not equipamento:
            raise HTTPException(status_code=404, detail="Equipamento nao encontrado")
        conexao.execute(
            "INSERT INTO chamados_manutencao "
            "(id, equipamento_id, descricao, prioridade, estado, sla, criado_por, criado_em) "
            "VALUES (?, ?, ?, ?, 'ABERTO', ?, ?, ?)",
            (
                identificador,
                dados.equipamento_id,
                dados.descricao.strip(),
                prioridade,
                sla,
                usuario["id"],
                db.agora(),
            ),
        )
        if prioridade == "CRITICA":
            criar_alerta(conexao, "CRITICO", f"Chamado critico {identificador} para {dados.equipamento_id}")
        registrar_auditoria(conexao, usuario, "CHAMADO_CRIADO", identificador, novo={"prioridade": prioridade})
        registrar_evento(conexao, "ChamadoManutencaoCriado", {"chamado_id": identificador, "sla": sla})
        conexao.commit()
    return {"id": identificador, "estado": "ABERTO", "sla": sla}


@app.post("/api/manutencao/chamados/{chamado_id}/concluir")
def concluir_chamado(chamado_id: str, usuario: dict = Depends(exigir("gestor", "administrador"))) -> dict:
    with conexao_aberta() as conexao:
        chamado = conexao.execute("SELECT * FROM chamados_manutencao WHERE id = ?", (chamado_id,)).fetchone()
        if not chamado:
            raise HTTPException(status_code=404, detail="Chamado nao encontrado")
        if chamado["estado"] != "ABERTO":
            raise HTTPException(status_code=400, detail="Chamado ja concluido")
        conexao.execute(
            "UPDATE chamados_manutencao SET estado = 'CONCLUIDO', concluido_em = ? WHERE id = ?",
            (db.agora(), chamado_id),
        )
        conexao.execute("UPDATE equipamentos SET estado = 'ATIVO' WHERE id = ?", (chamado["equipamento_id"],))
        registrar_auditoria(conexao, usuario, "CHAMADO_CONCLUIDO", chamado_id)
        registrar_evento(conexao, "ChamadoManutencaoConcluido", {"chamado_id": chamado_id})
        conexao.commit()
    return {"id": chamado_id, "estado": "CONCLUIDO"}


@app.get("/api/manutencao/chamados")
def listar_chamados(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM chamados_manutencao ORDER BY criado_em DESC").fetchall())


@app.get("/api/rh/funcionarios")
def listar_funcionarios(
    usuario: dict = Depends(exigir("rh", "chefia", "auditoria", "administrador")),
) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM staff ORDER BY unidade, nome").fetchall())


@app.post("/api/rh/escalas", status_code=201)
def criar_escala(
    dados: EscalaModel,
    usuario: dict = Depends(exigir("chefia", "rh", "administrador")),
) -> dict:
    turnos = {"MANHA", "TARDE", "NOITE"}
    turno = dados.turno.strip().upper()
    if turno not in turnos:
        raise HTTPException(status_code=400, detail="Turno deve ser MANHA, TARDE ou NOITE")
    with conexao_aberta() as conexao:
        funcionario = conexao.execute("SELECT 1 FROM staff WHERE id = ? AND ativo = 1", (dados.staff_id,)).fetchone()
        if not funcionario:
            raise HTTPException(status_code=404, detail="Funcionario nao encontrado")
        identificador = criar_id("ESC")
        conexao.execute(
            "INSERT INTO shifts (id, staff_id, data, turno, unidade, criado_por, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (identificador, dados.staff_id, dados.data, turno, dados.unidade.strip(), usuario["id"], db.agora()),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "ESCALA_CRIADA",
            identificador,
            novo={"staff_id": dados.staff_id, "data": dados.data, "turno": turno},
        )
        conexao.commit()
    return {"id": identificador, "estado": "PLANIFICADA"}


@app.get("/api/rh/escalas")
def listar_escalas(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute(
                "SELECT s.*, f.nome AS funcionario_nome FROM shifts s JOIN staff f ON f.id = s.staff_id "
                "ORDER BY s.data, s.turno"
            ).fetchall()
        )


@app.post("/api/rh/pedidos", status_code=201)
def criar_pedido_rh(dados: PedidoRhModel, usuario: dict = Depends(usuario_atual)) -> dict:
    tipos = {"FERIAS", "FALTA", "TROCA_TURNO"}
    tipo = dados.tipo.strip().upper()
    if tipo not in tipos:
        raise HTTPException(status_code=400, detail="Tipo deve ser FERIAS, FALTA ou TROCA_TURNO")
    with conexao_aberta() as conexao:
        funcionario = conexao.execute("SELECT 1 FROM staff WHERE id = ?", (dados.staff_id,)).fetchone()
        if not funcionario:
            raise HTTPException(status_code=404, detail="Funcionario nao encontrado")
        identificador = criar_id("RH")
        conexao.execute(
            "INSERT INTO leave_requests (id, staff_id, tipo, inicio, fim, justificacao, estado, criado_por, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, 'PENDENTE_CHEFIA', ?, ?)",
            (
                identificador,
                dados.staff_id,
                tipo,
                dados.inicio,
                dados.fim,
                dados.justificacao,
                usuario["id"],
                db.agora(),
            ),
        )
        registrar_auditoria(conexao, usuario, "PEDIDO_RH_CRIADO", identificador, novo={"tipo": tipo})
        conexao.commit()
    return {"id": identificador, "estado": "PENDENTE_CHEFIA"}


@app.get("/api/rh/pedidos")
def listar_pedidos_rh(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute(
                "SELECT p.*, f.nome AS funcionario_nome FROM leave_requests p JOIN staff f ON f.id = p.staff_id "
                "ORDER BY p.criado_em DESC"
            ).fetchall()
        )


@app.post("/api/rh/pedidos/{pedido_id}/aprovar")
def aprovar_pedido_rh(
    pedido_id: str,
    dados: ParecerModel,
    usuario: dict = Depends(exigir("chefia", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        pedido = obter_pedido_rh(conexao, pedido_id)
        if pedido["estado"] != "PENDENTE_CHEFIA":
            raise HTTPException(status_code=400, detail="Pedido nao esta pendente de chefia")
        if pedido["criado_por"] == usuario["id"]:
            raise HTTPException(status_code=403, detail="Segregacao de funcoes: nao podes aprovar o teu proprio pedido")
        estado = "PENDENTE_RH" if dados.aprovado else "REJEITADO"
        conexao.execute(
            "UPDATE leave_requests SET estado = ?, aprovado_por = ? WHERE id = ?",
            (estado, usuario["id"], pedido_id),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "PEDIDO_RH_APROVADO" if dados.aprovado else "PEDIDO_RH_REJEITADO",
            pedido_id,
            anterior={"estado": pedido["estado"]},
            novo={"estado": estado, "parecer": dados.parecer},
        )
        conexao.commit()
    return {"id": pedido_id, "estado": estado}


@app.post("/api/rh/pedidos/{pedido_id}/homologar")
def homologar_pedido_rh(
    pedido_id: str,
    usuario: dict = Depends(exigir("rh", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        pedido = obter_pedido_rh(conexao, pedido_id)
        if pedido["estado"] != "PENDENTE_RH":
            raise HTTPException(status_code=400, detail="Pedido nao esta pendente de RH")
        if pedido["aprovado_por"] == usuario["id"]:
            raise HTTPException(status_code=403, detail="Segregacao de funcoes: aprovacao e homologacao separadas")
        conexao.execute(
            "UPDATE leave_requests SET estado = 'HOMOLOGADO', homologado_por = ? WHERE id = ?",
            (usuario["id"], pedido_id),
        )
        registrar_auditoria(conexao, usuario, "PEDIDO_RH_HOMOLOGADO", pedido_id)
        registrar_evento(conexao, "PedidoRhHomologado", {"pedido_id": pedido_id})
        conexao.commit()
    return {"id": pedido_id, "estado": "HOMOLOGADO"}


@app.post("/api/compras/requisicoes", status_code=201)
def criar_requisicao(
    dados: RequisicaoModel,
    usuario: dict = Depends(usuario_atual),
) -> dict:
    identificador = criar_id("REQ")
    with conexao_aberta() as conexao:
        conexao.execute(
            "INSERT INTO purchase_requests (id, descricao, quantidade, valor, unidade, fornecedor, solicitante_id, estado, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'SOLICITADA', ?)",
            (
                identificador,
                dados.descricao.strip(),
                dados.quantidade,
                dados.valor,
                dados.unidade.strip(),
                dados.unidade.strip(),
                usuario["id"],
                db.agora(),
            ),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "REQUISICAO_CRIADA",
            identificador,
            novo={"valor": dados.valor, "quantidade": dados.quantidade},
        )
        registrar_evento(conexao, "RequisicaoCriada", {"requisicao_id": identificador, "valor": dados.valor})
        conexao.commit()
    return {"id": identificador, "estado": "SOLICITADA", "alto_valor": dados.valor > LIMITE_ALCADA_1}


@app.get("/api/compras/requisicoes")
def listar_requisicoes(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM purchase_requests ORDER BY criado_em DESC").fetchall())


@app.post("/api/compras/requisicoes/{requisicao_id}/validar-tecnica")
def validar_tecnica(
    requisicao_id: str,
    dados: ParecerModel,
    usuario: dict = Depends(exigir("medico", "enfermeiro", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        requisicao = obter_requisicao(conexao, requisicao_id)
        if requisicao["estado"] != "SOLICITADA":
            raise HTTPException(status_code=400, detail="Requisicao nao esta na fase de validacao tecnica")
        if requisicao["solicitante_id"] == usuario["id"]:
            raise HTTPException(status_code=403, detail="Segregacao de funcoes: quem solicita nao valida")
        estado = "VALIDADA_TECNICAMENTE" if dados.aprovado else "REJEITADA"
        conexao.execute(
            "UPDATE purchase_requests SET validador_tecnico_id = ?, estado = ? WHERE id = ?",
            (usuario["id"], estado, requisicao_id),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "VALIDACAO_TECNICA",
            requisicao_id,
            anterior={"estado": requisicao["estado"]},
            novo={"estado": estado, "parecer": dados.parecer},
        )
        conexao.commit()
    return {"id": requisicao_id, "estado": estado}


@app.post("/api/compras/requisicoes/{requisicao_id}/verificar-orcamento")
def verificar_orcamento(
    requisicao_id: str,
    usuario: dict = Depends(exigir("financeiro", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        requisicao = obter_requisicao(conexao, requisicao_id)
        if requisicao["estado"] != "VALIDADA_TECNICAMENTE":
            raise HTTPException(status_code=400, detail="Requisicao nao validada tecnicamente")
        orcamento = orcamento_atual(conexao)
        disponivel = orcamento["total"] - orcamento["executado"]
        if requisicao["valor"] > disponivel:
            raise HTTPException(status_code=400, detail="Sem cabimento orcamental")
        if requisicao["validador_tecnico_id"] == usuario["id"]:
            raise HTTPException(status_code=403, detail="Segregacao de funcoes: validador nao verifica orcamento")
        conexao.execute(
            "UPDATE purchase_requests SET verificado_orcamento_id = ?, estado = 'ORCAMENTO_VERIFICADO' WHERE id = ?",
            (usuario["id"], requisicao_id),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "CABIMENTO_VERIFICADO",
            requisicao_id,
            novo={"valor": requisicao["valor"], "disponivel": disponivel},
        )
        conexao.commit()
    return {"id": requisicao_id, "estado": "ORCAMENTO_VERIFICADO", "disponivel": disponivel}


@app.post("/api/compras/requisicoes/{requisicao_id}/parecer")
@app.post("/api/compras/requisicoes/{requisicao_id}/pareceres")
def parecer_conformidade(
    requisicao_id: str,
    dados: ParecerModel,
    usuario: dict = Depends(exigir("juridico", "auditoria", "administrador")),
) -> dict:
    tipo = (dados.tipo or "").strip().upper() or (
        "JURIDICO" if usuario["perfil"] == "juridico" else "AUDITORIA_INTERNA"
    )
    if tipo not in TIPO_PARECER_PERFIL:
        raise HTTPException(status_code=400, detail="Tipo de parecer invalido")
    if usuario["perfil"] not in {"administrador", TIPO_PARECER_PERFIL[tipo]}:
        raise HTTPException(status_code=403, detail=f"Perfil {TIPO_PARECER_PERFIL[tipo]} necessario")
    with conexao_aberta() as conexao:
        requisicao = obter_requisicao(conexao, requisicao_id)
        if requisicao["estado"] not in {"ORCAMENTO_VERIFICADO", "PARECER_CONFORME"}:
            raise HTTPException(status_code=400, detail="Requisicao nao esta na fase de parecer")
        conexao.execute(
            "INSERT INTO pareceres (purchase_id, tipo, parecer, aprovado, autor_id, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (requisicao_id, tipo, dados.parecer.strip(), int(dados.aprovado), usuario["id"], db.agora()),
        )
        favoraveis = {
            linha["tipo"]
            for linha in conexao.execute(
                "SELECT tipo FROM pareceres WHERE purchase_id = ? AND aprovado = 1", (requisicao_id,)
            ).fetchall()
        }
        desfavoraveis = conexao.execute(
            "SELECT 1 FROM pareceres WHERE purchase_id = ? AND aprovado = 0", (requisicao_id,)
        ).fetchone()
        if desfavoraveis:
            estado = "REJEITADA"
        elif {"JURIDICO", "AUDITORIA_INTERNA"}.issubset(favoraveis):
            estado = "PARECER_CONFORME"
        else:
            estado = "ORCAMENTO_VERIFICADO"
        conexao.execute(
            "UPDATE purchase_requests SET parecer_juridico_id = COALESCE(parecer_juridico_id, ?), estado = ? WHERE id = ?",
            (usuario["id"], estado, requisicao_id),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "PARECER_REGISTADO",
            requisicao_id,
            anterior={"estado": requisicao["estado"]},
            novo={"estado": estado, "tipo": tipo, "aprovado": dados.aprovado},
        )
        registrar_evento(conexao, "ParecerRegistado", {"requisicao_id": requisicao_id, "tipo": tipo})
        conexao.commit()
    return {"id": requisicao_id, "estado": estado, "pareceres_favoraveis": sorted(favoraveis)}


@app.get("/api/compras/requisicoes/{requisicao_id}/pareceres")
def listar_pareceres(
    requisicao_id: str,
    usuario: dict = Depends(exigir("juridico", "auditoria", "administrador", "financeiro")),
) -> list[dict]:
    with conexao_aberta() as conexao:
        obter_requisicao(conexao, requisicao_id)
        return em_lista(
            conexao.execute(
                "SELECT p.*, u.username AS autor FROM pareceres p JOIN users u ON u.id = p.autor_id "
                "WHERE p.purchase_id = ? ORDER BY p.criado_em",
                (requisicao_id,),
            ).fetchall()
        )


@app.post("/api/compras/requisicoes/{requisicao_id}/aprovar")
def aprovar_requisicao(
    requisicao_id: str,
    usuario: dict = Depends(exigir("administrador", "financeiro", "gestor")),
) -> dict:
    with conexao_aberta() as conexao:
        requisicao = obter_requisicao(conexao, requisicao_id)
        alto_valor = requisicao["valor"] > LIMITE_ALCADA_1
        estado_anterior = requisicao["estado"]
        if alto_valor:
            favoraveis = {
                linha["tipo"]
                for linha in conexao.execute(
                    "SELECT tipo FROM pareceres WHERE purchase_id = ? AND aprovado = 1", (requisicao_id,)
                ).fetchall()
            }
            if not {"JURIDICO", "AUDITORIA_INTERNA"}.issubset(favoraveis):
                raise HTTPException(status_code=422, detail="Pareceres Juridico e Auditoria Interna obrigatorios")
        estado_necessario = "PARECER_CONFORME" if alto_valor else "ORCAMENTO_VERIFICADO"
        if estado_anterior != estado_necessario:
            raise HTTPException(status_code=400, detail=f"Requisicao nao esta na fase de aprovacao ({estado_necessario})")
        if alto_valor and usuario["perfil"] != "administrador":
            raise HTTPException(status_code=403, detail="Alto valor exige aprovacao da Direcao Geral")
        if usuario["id"] in {requisicao["solicitante_id"], requisicao["verificado_orcamento_id"]}:
            raise HTTPException(status_code=403, detail="Segregacao de funcoes: aprovador ja participou do processo")
        orcamento = orcamento_atual(conexao)
        if requisicao["valor"] > orcamento["total"] - orcamento["executado"]:
            raise HTTPException(status_code=400, detail="Sem cabimento orcamental")
        conexao.execute(
            "UPDATE purchase_requests SET aprovador_id = ?, estado = 'EMPENHADA' WHERE id = ?",
            (usuario["id"], requisicao_id),
        )
        conexao.execute(
            "INSERT INTO commitments (id, purchase_id, valor, estado, criado_por, criado_em) "
            "VALUES (?, ?, ?, 'ATIVO', ?, ?)",
            (criar_id("EMP"), requisicao_id, requisicao["valor"], usuario["id"], db.agora()),
        )
        conexao.execute(
            "UPDATE budget SET executado = executado + ?, atualizado_por = ?, atualizado_em = ? WHERE id = ?",
            (requisicao["valor"], usuario["id"], db.agora(), orcamento["id"]),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "REQUISICAO_APROVADA",
            requisicao_id,
            anterior={"estado": estado_anterior},
            novo={"estado": "EMPENHADA", "valor": requisicao["valor"]},
        )
        registrar_evento(conexao, "RequisicaoAprovada", {"requisicao_id": requisicao_id})
        conexao.commit()
    return {"id": requisicao_id, "estado": "EMPENHADA"}


@app.post("/api/compras/requisicoes/{requisicao_id}/receber")
def receber_requisicao(
    requisicao_id: str,
    dados: RececaoModel,
    usuario: dict = Depends(exigir("logistica", "farmacia", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        requisicao = obter_requisicao(conexao, requisicao_id)
        if requisicao["estado"] != "EMPENHADA":
            raise HTTPException(status_code=400, detail="Requisicao nao esta empenhada")
        participantes = {
            requisicao["solicitante_id"],
            requisicao["aprovador_id"],
            requisicao["validador_tecnico_id"],
        }
        if usuario["id"] in participantes:
            raise HTTPException(status_code=403, detail="Segregacao de funcoes: rececao por terceiro")
        conexao.execute(
            "UPDATE purchase_requests SET rececionista_id = ?, estado = 'RECEBIDA' WHERE id = ?",
            (usuario["id"], requisicao_id),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "MERCADORIA_RECEBIDA",
            requisicao_id,
            novo={"conferencia": dados.conferencia},
        )
        registrar_evento(conexao, "MercadoriaRecebida", {"requisicao_id": requisicao_id})
        conexao.commit()
    return {"id": requisicao_id, "estado": "RECEBIDA"}


@app.get("/api/financeiro/orcamento")
def ver_orcamento(usuario: dict = Depends(usuario_atual)) -> dict:
    with conexao_aberta() as conexao:
        return dict(orcamento_atual(conexao))


@app.post("/api/financeiro/orcamento")
def atualizar_orcamento(
    dados: BudgetModel,
    usuario: dict = Depends(exigir("financeiro", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        orcamento = orcamento_atual(conexao)
        if dados.total < orcamento["executado"]:
            raise HTTPException(status_code=400, detail="Total nao pode ser inferior ao executado")
        conexao.execute(
            "UPDATE budget SET total = ?, atualizado_por = ?, atualizado_em = ? WHERE id = ?",
            (dados.total, usuario["id"], db.agora(), orcamento["id"]),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "ORCAMENTO_ATUALIZADO",
            orcamento["id"],
            anterior={"total": orcamento["total"]},
            novo={"total": dados.total},
        )
        conexao.commit()
    return {"id": orcamento["id"], "total": dados.total}


@app.get("/api/financeiro/empenhos")
def listar_empenhos(usuario: dict = Depends(exigir("financeiro", "auditoria", "administrador"))) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute(
                "SELECT c.*, r.descricao FROM commitments c JOIN purchase_requests r ON r.id = c.purchase_id "
                "ORDER BY c.criado_em DESC"
            ).fetchall()
        )


@app.get("/api/financeiro/relatorio")
def relatorio_financeiro(usuario: dict = Depends(exigir("financeiro", "auditoria", "administrador"))) -> dict:
    with conexao_aberta() as conexao:
        orcamento = orcamento_atual(conexao)
        empenhos = conexao.execute("SELECT COUNT(*) AS total, COALESCE(SUM(valor), 0) AS valor FROM commitments").fetchone()
        return {
            "exercicio": orcamento["exercicio"],
            "total": orcamento["total"],
            "executado": orcamento["executado"],
            "disponivel": orcamento["total"] - orcamento["executado"],
            "empenhos_ativos": empenhos["total"],
            "valor_empenhado": empenhos["valor"],
        }


@app.post("/api/mdt/pedidos", status_code=201)
def criar_pedido_mdt(
    dados: MdtPedidoModel,
    usuario: dict = Depends(exigir("medico", "administrador")),
) -> dict:
    tipo = dados.tipo.strip().upper()
    if tipo not in PERFIS_MDT:
        raise HTTPException(status_code=400, detail="Tipo deve ser LABORATORIO, IMAGEM ou FISIOTERAPIA")
    with conexao_aberta() as conexao:
        validar_abac_episodio(conexao, usuario, dados.episodio_id)
        obter_episodio(conexao, dados.episodio_id)
        identificador = criar_id("MDT")
        parametros = [parametro.model_dump() for parametro in dados.parametros or []]
        conexao.execute(
            "INSERT INTO mdt_orders (id, episode_id, tipo, descricao, medico_id, estado, parametros, criado_em) "
            "VALUES (?, ?, ?, ?, ?, 'PENDENTE', ?, ?)",
            (
                identificador,
                dados.episodio_id,
                tipo,
                dados.descricao.strip(),
                usuario["id"],
                json.dumps(parametros),
                db.agora(),
            ),
        )
        for parametro in parametros:
            conexao.execute(
                "INSERT INTO mdt_parametros (pedido_id, parametro, valor, unidade, valor_referencia, criticidade) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    identificador,
                    parametro["parametro"],
                    parametro["valor"],
                    parametro.get("unidade"),
                    parametro.get("valor_referencia"),
                    parametro.get("criticidade", "NORMAL"),
                ),
            )
        registrar_auditoria(
            conexao,
            usuario,
            "MDT_PEDIDO_CRIADO",
            identificador,
            novo={"tipo": tipo, "parametros": parametros},
        )
        registrar_evento(conexao, "PedidoMdtCriado", {"pedido_id": identificador, "tipo": tipo})
        conexao.commit()
    return {"id": identificador, "estado": "PENDENTE"}


@app.get("/api/mdt/pedidos")
def listar_pedidos_mdt(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute(
                "SELECT m.*, e.patient_id FROM mdt_orders m JOIN episodes e ON e.id = m.episode_id "
                "ORDER BY m.criado_em DESC"
            ).fetchall()
        )


@app.post("/api/mdt/pedidos/{pedido_id}/resultado")
def registar_resultado_mdt(
    pedido_id: str,
    dados: MdtResultadoModel,
    usuario: dict = Depends(usuario_atual),
) -> dict:
    with conexao_aberta() as conexao:
        pedido = obter_pedido_mdt(conexao, pedido_id)
        if pedido["estado"] != "PENDENTE":
            raise HTTPException(status_code=400, detail="Pedido nao esta pendente")
        perfil_necessario = PERFIS_MDT[pedido["tipo"]]
        if usuario["perfil"] != perfil_necessario and usuario["perfil"] != "administrador":
            raise HTTPException(status_code=403, detail=f"Perfil {perfil_necessario} necessario para este exame")
        if pedido["medico_id"] == usuario["id"]:
            raise HTTPException(status_code=403, detail="Segregacao de funcoes: prescritor nao valida resultado")
        concluido_em = db.agora()
        parametros = em_lista(
            conexao.execute("SELECT * FROM mdt_parametros WHERE pedido_id = ?", (pedido_id,)).fetchall()
        )
        pedido_atualizado = dict(pedido)
        pedido_atualizado.update(
            {"resultado": dados.resultado.strip(), "estado": "RESULTADO_DISPONIVEL", "concluido_em": concluido_em}
        )
        assinatura = assinar_documento(
            conexao, usuario, "LAUDO_MDT", pedido_id, dados.resultado.strip()
        )
        conexao.execute(
            "UPDATE mdt_orders SET resultado = ?, tecnico_id = ?, estado = 'RESULTADO_DISPONIVEL', "
            "concluido_em = ?, assinatura = ?, hl7 = ?, fhir = ? WHERE id = ?",
            (
                dados.resultado.strip(),
                usuario["id"],
                concluido_em,
                assinatura["assinatura"],
                gerar_hl7(pedido_atualizado, parametros),
                json.dumps(gerar_fhir(pedido_atualizado, parametros)),
                pedido_id,
            ),
        )
        if any(parametro["criticidade"] == "CRITICO" for parametro in parametros):
            criar_alerta(conexao, "CRITICO", f"Parametro critico no pedido MDT {pedido_id}")
        registrar_auditoria(
            conexao,
            usuario,
            "MDT_RESULTADO_REGISTADO",
            pedido_id,
            novo={"resultado": dados.resultado.strip()},
        )
        registrar_evento(conexao, "ResultadoMdtDisponivel", {"pedido_id": pedido_id})
        conexao.commit()
    return {"id": pedido_id, "estado": "RESULTADO_DISPONIVEL"}


@app.post("/api/mdt/pedidos/{pedido_id}/validar")
def validar_resultado_mdt(
    pedido_id: str,
    usuario: dict = Depends(exigir("medico", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        pedido = obter_pedido_mdt(conexao, pedido_id)
        if pedido["estado"] != "RESULTADO_DISPONIVEL":
            raise HTTPException(status_code=400, detail="Resultado ainda nao disponivel")
        conexao.execute(
            "UPDATE mdt_orders SET validado_por = ?, estado = 'VALIDADO' WHERE id = ?",
            (usuario["id"], pedido_id),
        )
        registrar_auditoria(conexao, usuario, "MDT_RESULTADO_VALIDADO", pedido_id)
        registrar_evento(conexao, "ResultadoMdtValidado", {"pedido_id": pedido_id})
        conexao.commit()
    return {"id": pedido_id, "estado": "VALIDADO"}


@app.get("/api/mdt/pedidos/{pedido_id}/exportar")
def exportar_mdt(
    pedido_id: str,
    formato: str = "FHIR",
    usuario: dict = Depends(usuario_atual),
) -> dict:
    with conexao_aberta() as conexao:
        pedido = obter_pedido_mdt(conexao, pedido_id)
        if pedido["estado"] not in {"RESULTADO_DISPONIVEL", "VALIDADO"}:
            raise HTTPException(status_code=400, detail="Resultado ainda nao disponivel")
        if formato.upper() == "HL7":
            return {"formato": "HL7", "conteudo": pedido["hl7"]}
        return {"formato": "FHIR", "conteudo": json.loads(pedido["fhir"]) if pedido["fhir"] else {}}


@app.get("/api/unidades")
def listar_unidades(
    cabecalho_unidade: str | None = None,
    usuario: dict = Depends(usuario_atual),
) -> list[dict]:
    with conexao_aberta() as conexao:
        unidades = em_lista(
            conexao.execute("SELECT * FROM unidades_organizacionais WHERE ativo = 1 ORDER BY nivel, codigo").fetchall()
        )
    if cabecalho_unidade and not unidade_permitida(usuario, cabecalho_unidade):
        raise HTTPException(status_code=403, detail="Unidade fora do contexto do utilizador")
    return unidades


@app.post("/api/documentos/assinar", status_code=201)
def assinar(
    dados: DocumentoAssinaturaModel,
    usuario: dict = Depends(usuario_atual),
) -> dict:
    tipo = dados.tipo_documento.strip().upper()
    permitidos = PERFIS_ASSINATURA.get(tipo)
    if not permitidos:
        raise HTTPException(status_code=400, detail="Tipo de documento desconhecido")
    if usuario["perfil"] != "administrador" and usuario["perfil"] not in permitidos:
        raise HTTPException(status_code=403, detail="Perfil sem permissao para assinar este documento")
    with conexao_aberta() as conexao:
        resultado = assinar_documento(conexao, usuario, tipo, dados.referencia_id, dados.conteudo.strip())
        conexao.commit()
    return resultado


@app.get("/api/documentos/assinados")
def listar_documentos_assinados(
    usuario: dict = Depends(exigir("auditoria", "administrador", "medico", "juridico")),
) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute(
                "SELECT id, tipo_documento, referencia_id, perfil_ativo, unidade_codigo, correlation_id, criado_em "
                "FROM documentos_assinados ORDER BY criado_em DESC"
            ).fetchall()
        )


@app.post("/api/episodios/{episodio_id}/evolucoes", status_code=201)
def registar_evolucao(
    episodio_id: str,
    dados: EvolucaoModel,
    usuario: dict = Depends(exigir("medico", "enfermeiro", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        if episodio["estado"] in ESTADOS_FINAIS:
            raise HTTPException(status_code=400, detail="Episodio encerrado para evolucao")
        identificador = criar_id("EVO")
        conexao.execute(
            "INSERT INTO evolucoes (id, episode_id, nota, conduta, proxima_avaliacao, autor_id, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                identificador,
                episodio_id,
                dados.nota.strip(),
                dados.conduta.strip(),
                dados.proxima_avaliacao.strip(),
                usuario["id"],
                db.agora(),
            ),
        )
        assinar_documento(conexao, usuario, "EVOLUCAO_CLINICA", identificador, dados.nota.strip())
        registrar_auditoria(conexao, usuario, "EVOLUCAO_REGISTADA", episodio_id, novo={"id": identificador})
        registrar_evento(conexao, "EvolucaoRegistada", {"episodio_id": episodio_id, "evolucao_id": identificador})
        conexao.commit()
    return {"id": identificador, "episodio_id": episodio_id}


@app.get("/api/episodios/{episodio_id}/evolucoes")
def listar_evolucoes(
    episodio_id: str,
    usuario: dict = Depends(usuario_atual),
) -> list[dict]:
    with conexao_aberta() as conexao:
        obter_episodio(conexao, episodio_id)
        return em_lista(
            conexao.execute(
                "SELECT e.*, u.username AS autor FROM evolucoes e JOIN users u ON u.id = e.autor_id "
                "WHERE e.episode_id = ? ORDER BY e.criado_em DESC",
                (episodio_id,),
            ).fetchall()
        )


@app.post("/api/episodios/{episodio_id}/balanco-hidrico", status_code=201)
def registar_balanco(
    episodio_id: str,
    dados: BalancoHidricoModel,
    usuario: dict = Depends(exigir("enfermeiro", "medico", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        obter_episodio(conexao, episodio_id)
        identificador = criar_id("BAL")
        saldo = dados.entradas_ml - dados.saidas_ml
        conexao.execute(
            "INSERT INTO balancos_hidricos (id, episode_id, entradas_ml, saidas_ml, dieta, turno, autor_id, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                identificador,
                episodio_id,
                dados.entradas_ml,
                dados.saidas_ml,
                dados.dieta.strip(),
                dados.turno.strip(),
                usuario["id"],
                db.agora(),
            ),
        )
        registrar_auditoria(
            conexao, usuario, "BALANCO_REGISTADO", episodio_id, novo={"id": identificador, "saldo_ml": saldo}
        )
        conexao.commit()
    return {"id": identificador, "saldo_ml": saldo}


@app.get("/api/episodios/{episodio_id}/balanco-hidrico")
def listar_balancos(episodio_id: str, usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute(
                "SELECT * FROM balancos_hidricos WHERE episode_id = ? ORDER BY criado_em DESC", (episodio_id,)
            ).fetchall()
        )


@app.post("/api/episodios/{episodio_id}/sumario-alta", status_code=201)
def criar_sumario_alta(
    episodio_id: str,
    dados: SumarioAltaModel,
    usuario: dict = Depends(exigir("medico", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        if episodio["estado"] in ESTADOS_FINAIS:
            raise HTTPException(status_code=400, detail="Episodio encerrado para sumario")
        identificador = criar_id("SUM")
        conexao.execute(
            "INSERT INTO sumarios_alta (id, episode_id, diagnostico, evolucao, orientacoes, medicamentos, medico_id, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                identificador,
                episodio_id,
                dados.diagnostico.strip(),
                dados.evolucao.strip(),
                dados.orientacoes.strip(),
                dados.medicamentos.strip(),
                usuario["id"],
                db.agora(),
            ),
        )
        assinar_documento(conexao, usuario, "SUMARIO_ALTA", identificador, dados.diagnostico.strip())
        registrar_auditoria(conexao, usuario, "SUMARIO_ALTA_CRIADO", episodio_id, novo={"id": identificador})
        registrar_evento(conexao, "SumarioAltaCriado", {"episodio_id": episodio_id, "sumario_id": identificador})
        conexao.commit()
    return {"id": identificador, "episodio_id": episodio_id, "assinado": True}


@app.get("/api/episodios/{episodio_id}/sumario-alta")
def ver_sumario_alta(episodio_id: str, usuario: dict = Depends(usuario_atual)) -> dict:
    with conexao_aberta() as conexao:
        linha = conexao.execute("SELECT * FROM sumarios_alta WHERE episode_id = ?", (episodio_id,)).fetchone()
        if not linha:
            raise HTTPException(status_code=404, detail="Sumario de alta nao encontrado")
        return dict(linha)


@app.post("/api/episodios/{episodio_id}/transferencia", status_code=201)
def transferir_episodio(
    episodio_id: str,
    dados: TransferenciaModel,
    usuario: dict = Depends(exigir("medico", "administrador", "chefe")),
) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        validar_transicao(episodio["estado"], "TRANSFERIDO")
        identificador = criar_id("GUIA")
        conexao.execute(
            "INSERT INTO guias_transferencia (id, episode_id, destino, motivo, veiculo, acompanhante_id, estado, "
            "criado_por, criado_em) VALUES (?, ?, ?, ?, ?, ?, 'EM_TRANSPORTE', ?, ?)",
            (
                identificador,
                episodio_id,
                dados.destino.strip(),
                dados.motivo.strip(),
                dados.veiculo.strip(),
                dados.acompanhante_id,
                usuario["id"],
                db.agora(),
            ),
        )
        conexao.execute("UPDATE episodes SET estado = 'TRANSFERIDO' WHERE id = ?", (episodio_id,))
        registrar_auditoria(
            conexao, usuario, "PACIENTE_TRANSFERIDO", episodio_id, anterior={"estado": episodio["estado"]},
            novo={"estado": "TRANSFERIDO", "destino": dados.destino.strip()},
        )
        registrar_evento(conexao, "TransferenciaCriada", {"guia_id": identificador, "destino": dados.destino.strip()})
        conexao.commit()
    return {"id": identificador, "estado": "TRANSFERIDO"}


@app.get("/api/episodios/{episodio_id}/transferencia")
def ver_transferencia(episodio_id: str, usuario: dict = Depends(usuario_atual)) -> dict:
    with conexao_aberta() as conexao:
        linha = conexao.execute("SELECT * FROM guias_transferencia WHERE episode_id = ?", (episodio_id,)).fetchone()
        if not linha:
            raise HTTPException(status_code=404, detail="Guia de transferencia nao encontrada")
        return dict(linha)


@app.post("/api/episodios/{episodio_id}/obito", status_code=201)
def registar_obito(
    episodio_id: str,
    dados: ObitoModel,
    usuario: dict = Depends(exigir("medico", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        episodio = obter_episodio(conexao, episodio_id)
        validar_transicao(episodio["estado"], "OBITO")
        identificador = criar_id("OBI")
        conexao.execute(
            "INSERT INTO obitos (id, episode_id, causa, data_obito, medico_id, criado_em) VALUES (?, ?, ?, ?, ?, ?)",
            (identificador, episodio_id, dados.causa.strip(), dados.data_obito.strip(), usuario["id"], db.agora()),
        )
        conexao.execute("UPDATE episodes SET estado = 'OBITO' WHERE id = ?", (episodio_id,))
        criar_alerta(conexao, "CRITICO", f"Obito registado no episodio {episodio_id}: {dados.causa.strip()}")
        registrar_auditoria(
            conexao, usuario, "OBITO_REGISTADO", episodio_id, anterior={"estado": episodio["estado"]},
            novo={"estado": "OBITO", "causa": dados.causa.strip()},
        )
        registrar_evento(conexao, "ObitoRegistado", {"episodio_id": episodio_id, "obito_id": identificador})
        conexao.commit()
    return {"id": identificador, "estado": "OBITO"}


@app.post("/api/consultas", status_code=201)
def agendar_consulta(
    dados: ConsultaAgendadaModel,
    usuario: dict = Depends(exigir("rececionista", "medico", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        paciente = conexao.execute("SELECT 1 FROM patients WHERE id = ?", (dados.patient_id,)).fetchone()
        if not paciente:
            raise HTTPException(status_code=404, detail="Paciente nao encontrado")
        identificador = criar_id("CONS")
        conexao.execute(
            "INSERT INTO consultas_agendadas (id, patient_id, especialidade, medico_id, data_hora, estado, "
            "retorno_de_id, criado_por, criado_em) VALUES (?, ?, ?, ?, ?, 'AGENDADO', ?, ?, ?)",
            (
                identificador,
                dados.patient_id,
                dados.especialidade.strip(),
                dados.medico_id,
                dados.data_hora.strip(),
                dados.retorno_de_id,
                usuario["id"],
                db.agora(),
            ),
        )
        sequencia = conexao.execute(
            "SELECT COUNT(*) AS total FROM consultas_agendadas WHERE UPPER(especialidade) = UPPER(?) "
            "AND substr(data_hora, 1, 10) = ?",
            (dados.especialidade.strip(), dados.data_hora.strip()[:10]),
        ).fetchone()["total"]
        senha = f"{dados.especialidade.strip()[:1].upper()}{sequencia:03d}"
        conexao.execute(
            "INSERT INTO painel_senhas (consulta_id, senha, estado) VALUES (?, ?, 'AGUARDANDO')",
            (identificador, senha),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "CONSULTA_AGENDADA",
            identificador,
            novo={"data_hora": dados.data_hora, "senha": senha},
        )
        registrar_evento(conexao, "ConsultaAgendada", {"consulta_id": identificador, "senha": senha})
        conexao.commit()
    return {"id": identificador, "estado": "AGENDADO"}


@app.get("/api/consultas")
def listar_consultas(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute(
                "SELECT c.*, p.nome AS paciente, u.nome AS medico FROM consultas_agendadas c "
                "JOIN patients p ON p.id = c.patient_id LEFT JOIN users u ON u.id = c.medico_id "
                "ORDER BY c.data_hora"
            ).fetchall()
        )


@app.get("/api/consultas/vagas")
def consultar_vagas(
    especialidade: str,
    data: str,
    usuario: dict = Depends(usuario_atual),
) -> dict:
    with conexao_aberta() as conexao:
        ocupadas = conexao.execute(
            "SELECT COUNT(*) AS total FROM consultas_agendadas WHERE UPPER(especialidade) = UPPER(?) "
            "AND substr(data_hora, 1, 10) = ? AND estado != 'CANCELADO'",
            (especialidade, data),
        ).fetchone()["total"]
    return {"especialidade": especialidade, "data": data, "vagas": max(0, 8 - ocupadas)}


@app.post("/api/consultas/{consulta_id}/check-in")
def check_in_consulta(
    consulta_id: str,
    usuario: dict = Depends(exigir("rececionista", "enfermeiro", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        consulta = conexao.execute("SELECT * FROM consultas_agendadas WHERE id = ?", (consulta_id,)).fetchone()
        if not consulta:
            raise HTTPException(status_code=404, detail="Consulta nao encontrada")
        if consulta["estado"] != "AGENDADO":
            raise HTTPException(status_code=400, detail="Consulta nao pode fazer check-in")
        conexao.execute("UPDATE consultas_agendadas SET estado = 'CHECK_IN_REALIZADO' WHERE id = ?", (consulta_id,))
        registrar_auditoria(conexao, usuario, "CHECK_IN_CONSULTA", consulta_id)
        conexao.commit()
    return {"id": consulta_id, "estado": "CHECK_IN_REALIZADO"}


@app.post("/api/consultas/{consulta_id}/retorno", status_code=201)
def marcar_retorno(
    consulta_id: str,
    dados: ConsultaAgendadaModel,
    usuario: dict = Depends(exigir("medico", "rececionista", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        anterior = conexao.execute("SELECT * FROM consultas_agendadas WHERE id = ?", (consulta_id,)).fetchone()
        if not anterior:
            raise HTTPException(status_code=404, detail="Consulta nao encontrada")
        identificador = criar_id("CONS")
        conexao.execute(
            "INSERT INTO consultas_agendadas (id, patient_id, especialidade, medico_id, data_hora, estado, "
            "retorno_de_id, criado_por, criado_em) VALUES (?, ?, ?, ?, ?, 'AGENDADO', ?, ?, ?)",
            (
                identificador,
                anterior["patient_id"],
                dados.especialidade.strip(),
                dados.medico_id or anterior["medico_id"],
                dados.data_hora.strip(),
                consulta_id,
                usuario["id"],
                db.agora(),
            ),
        )
        senha = f"R{int(identificador[-3:]):03d}" if identificador[-3:].isdigit() else f"R{secrets_token()}"
        conexao.execute(
            "INSERT INTO painel_senhas (consulta_id, senha, estado) VALUES (?, ?, 'AGUARDANDO')",
            (identificador, senha),
        )
        registrar_auditoria(
            conexao, usuario, "RETORNO_AGENDADO", identificador, novo={"origem": consulta_id, "senha": senha}
        )
        conexao.commit()
    return {"id": identificador, "estado": "AGENDADO", "retorno_de_id": consulta_id, "senha": senha}


def secrets_token() -> str:
    return uuid.uuid4().hex[:3].upper()


@app.post("/api/stock-setorial/movimentos", status_code=201)
def movimentar_stock_setorial(
    dados: MovimentoStockModel,
    usuario: dict = Depends(exigir("logistica", "farmacia", "nutricionista", "limpeza", "administrador")),
) -> dict:
    tipo = dados.tipo.strip().upper()
    if tipo not in {"ENTRADA", "SAIDA", "TRANSFERENCIA"}:
        raise HTTPException(status_code=400, detail="Tipo de movimento invalido")
    if tipo == "TRANSFERENCIA" and not dados.destino:
        raise HTTPException(status_code=400, detail="Transferencia exige destino")
    with conexao_aberta() as conexao:
        identificador = f"{dados.unidade_codigo}-{dados.item}"
        linha = conexao.execute("SELECT * FROM stock_setorial WHERE id = ?", (identificador,)).fetchone()
        if not linha:
            if tipo != "ENTRADA":
                raise HTTPException(status_code=404, detail="Item nao existe nesta unidade")
            conexao.execute(
                "INSERT INTO stock_setorial (id, unidade_codigo, item, quantidade, minimo) VALUES (?, ?, ?, 0, 0)",
                (identificador, dados.unidade_codigo, dados.item.strip()),
            )
            linha = conexao.execute("SELECT * FROM stock_setorial WHERE id = ?", (identificador,)).fetchone()
        if tipo in {"SAIDA", "TRANSFERENCIA"} and linha["quantidade"] < dados.quantidade:
            raise HTTPException(status_code=400, detail="Quantidade indisponivel no setor")
        delta = dados.quantidade if tipo == "ENTRADA" else -dados.quantidade
        conexao.execute("UPDATE stock_setorial SET quantidade = quantidade + ? WHERE id = ?", (delta, identificador))
        if tipo == "TRANSFERENCIA":
            destino_id = f"{dados.destino}-{dados.item}"
            conexao.execute(
                "INSERT INTO stock_setorial (id, unidade_codigo, item, quantidade, minimo) VALUES (?, ?, ?, 0, 0) "
                "ON CONFLICT(id) DO NOTHING",
                (destino_id, dados.destino, dados.item.strip()),
            )
            conexao.execute(
                "UPDATE stock_setorial SET quantidade = quantidade + ? WHERE id = ?", (dados.quantidade, destino_id)
            )
        movimento_id = criar_id("MOV")
        conexao.execute(
            "INSERT INTO movimentacoes_stock (id, stock_setorial_id, tipo, quantidade, origem, destino, "
            "responsavel_id, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                movimento_id,
                identificador,
                tipo,
                dados.quantidade,
                dados.unidade_codigo,
                dados.destino,
                usuario["id"],
                db.agora(),
            ),
        )
        registrar_auditoria(conexao, usuario, "STOCK_SETORIAL_MOVIMENTADO", identificador, novo={"tipo": tipo, "quantidade": dados.quantidade})
        conexao.commit()
    return {"id": movimento_id, "tipo": tipo}


@app.get("/api/stock-setorial")
def listar_stock_setorial(
    unidade_codigo: str | None = None,
    usuario: dict = Depends(usuario_atual),
) -> list[dict]:
    with conexao_aberta() as conexao:
        if unidade_codigo:
            return em_lista(
                conexao.execute("SELECT * FROM stock_setorial WHERE unidade_codigo = ?", (unidade_codigo,)).fetchall()
            )
        return em_lista(conexao.execute("SELECT * FROM stock_setorial ORDER BY unidade_codigo, item").fetchall())


@app.post("/api/contratos", status_code=201)
def criar_contrato(
    dados: ContratoModel,
    usuario: dict = Depends(exigir("compras", "juridico", "financeiro", "administrador")),
) -> dict:
    identificador = criar_id("CTR")
    with conexao_aberta() as conexao:
        conexao.execute(
            "INSERT INTO contratos (id, fornecedor, objeto, valor, inicio, fim, estado, criado_por, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, 'ATIVO', ?, ?)",
            (
                identificador,
                dados.fornecedor.strip(),
                dados.objeto.strip(),
                dados.valor,
                dados.inicio.strip(),
                dados.fim.strip(),
                usuario["id"],
                db.agora(),
            ),
        )
        assinar_documento(conexao, usuario, "CONTRATO_ALTA_VALOR", identificador, dados.objeto.strip())
        registrar_auditoria(conexao, usuario, "CONTRATO_CRIADO", identificador, novo={"valor": dados.valor})
        conexao.commit()
    return {"id": identificador, "estado": "ATIVO", "assinado": True}


@app.get("/api/contratos")
def listar_contratos(usuario: dict = Depends(exigir("compras", "juridico", "financeiro", "auditoria", "administrador"))) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM contratos ORDER BY criado_em DESC").fetchall())


@app.post("/api/cotacoes", status_code=201)
def criar_cotacao(
    dados: CotacaoModel,
    usuario: dict = Depends(exigir("compras", "administrador")),
) -> dict:
    identificador = criar_id("COT")
    with conexao_aberta() as conexao:
        conexao.execute(
            "INSERT INTO cotacoes (id, descricao, quantidade, estimativa, estado, criado_por, criado_em) "
            "VALUES (?, ?, ?, ?, 'ABERTA', ?, ?)",
            (identificador, dados.descricao.strip(), dados.quantidade, dados.estimativa, usuario["id"], db.agora()),
        )
        registrar_auditoria(conexao, usuario, "COTACAO_CRIADA", identificador, novo={"estimativa": dados.estimativa})
        conexao.commit()
    return {"id": identificador, "estado": "ABERTA"}


@app.get("/api/cotacoes")
def listar_cotacoes(usuario: dict = Depends(exigir("compras", "financeiro", "auditoria", "administrador"))) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM cotacoes ORDER BY criado_em DESC").fetchall())


@app.get("/api/cotacoes/{cotacao_id}/propostas")
def listar_propostas(
    cotacao_id: str,
    usuario: dict = Depends(exigir("compras", "financeiro", "auditoria", "administrador")),
) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute(
                "SELECT * FROM propostas_fornecedores WHERE cotacao_id = ? ORDER BY valor", (cotacao_id,)
            ).fetchall()
        )


@app.post("/api/cotacoes/{cotacao_id}/propostas", status_code=201)
def adicionar_proposta(
    cotacao_id: str,
    dados: PropostaModel,
    usuario: dict = Depends(exigir("compras", "administrador")),
) -> dict:
    identificador = criar_id("PROP")
    with conexao_aberta() as conexao:
        cotacao = conexao.execute("SELECT * FROM cotacoes WHERE id = ?", (cotacao_id,)).fetchone()
        if not cotacao:
            raise HTTPException(status_code=404, detail="Cotacao nao encontrada")
        conexao.execute(
            "INSERT INTO propostas_fornecedores (id, cotacao_id, fornecedor, valor, prazo, selecionada) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (identificador, cotacao_id, dados.fornecedor.strip(), dados.valor, dados.prazo.strip()),
        )
        registrar_auditoria(conexao, usuario, "PROPOSTA_REGISTADA", cotacao_id, novo={"fornecedor": dados.fornecedor})
        conexao.commit()
    return {"id": identificador, "cotacao_id": cotacao_id}


@app.post("/api/cotacoes/{cotacao_id}/selecionar")
def selecionar_proposta(
    cotacao_id: str,
    proposta_id: str,
    usuario: dict = Depends(exigir("compras", "financeiro", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        proposta = conexao.execute(
            "SELECT * FROM propostas_fornecedores WHERE id = ? AND cotacao_id = ?", (proposta_id, cotacao_id)
        ).fetchone()
        if not proposta:
            raise HTTPException(status_code=404, detail="Proposta nao encontrada")
        conexao.execute("UPDATE propostas_fornecedores SET selecionada = 0 WHERE cotacao_id = ?", (cotacao_id,))
        conexao.execute("UPDATE propostas_fornecedores SET selecionada = 1 WHERE id = ?", (proposta_id,))
        conexao.execute("UPDATE cotacoes SET estado = 'ADJUDICADA' WHERE id = ?", (cotacao_id,))
        registrar_auditoria(
            conexao, usuario, "PROPOSTA_SELECIONADA", cotacao_id,
            novo={"proposta_id": proposta_id, "valor": proposta["valor"]},
        )
        registrar_evento(conexao, "PropostaSelecionada", {"cotacao_id": cotacao_id, "proposta_id": proposta_id})
        conexao.commit()
    return {"cotacao_id": cotacao_id, "proposta_id": proposta_id, "estado": "ADJUDICADA"}


@app.post("/api/rh/folhas-salario", status_code=201)
def criar_folha_salario(
    dados: FolhaSalarioModel,
    usuario: dict = Depends(exigir("rh", "administrador")),
) -> dict:
    if dados.descontos > dados.salario_base:
        raise HTTPException(status_code=400, detail="Descontos superiores ao salario base")
    identificador = criar_id("FOL")
    liquido = round(dados.salario_base - dados.descontos, 2)
    with conexao_aberta() as conexao:
        conexao.execute(
            "INSERT INTO folhas_salario (id, funcionario, mes, salario_base, descontos, liquido, estado, "
            "criado_por, criado_em) VALUES (?, ?, ?, ?, ?, ?, 'CALCULADA', ?, ?)",
            (
                identificador,
                dados.funcionario.strip(),
                dados.mes.strip(),
                dados.salario_base,
                dados.descontos,
                liquido,
                usuario["id"],
                db.agora(),
            ),
        )
        registrar_auditoria(conexao, usuario, "FOLHA_CRIADA", identificador, novo={"liquido": liquido})
        conexao.commit()
    return {"id": identificador, "liquido": liquido, "estado": "CALCULADA"}


@app.get("/api/rh/folhas-salario")
def listar_folhas_salario(usuario: dict = Depends(exigir("rh", "financeiro", "auditoria", "administrador"))) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM folhas_salario ORDER BY mes DESC").fetchall())


@app.post("/api/rh/ponto", status_code=201)
def registar_ponto(
    dados: PontoModel,
    usuario: dict = Depends(exigir("rh", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        cursor = conexao.execute(
            "INSERT INTO registos_ponto (funcionario, data, entrada, saida) VALUES (?, ?, ?, ?)",
            (dados.funcionario.strip(), dados.data.strip(), dados.entrada.strip(), dados.saida),
        )
        identificador = cursor.lastrowid
        registrar_auditoria(conexao, usuario, "PONTO_REGISTADO", str(identificador), novo={"data": dados.data})
        conexao.commit()
    return {"id": identificador}


@app.get("/api/rh/ponto")
def listar_ponto(usuario: dict = Depends(exigir("rh", "administrador"))) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM registos_ponto ORDER BY data DESC, id DESC").fetchall())


@app.post("/api/manutencao/chamados/{chamado_id}/escalonar")
def escalonar_chamado(
    chamado_id: str,
    destino: str,
    usuario: dict = Depends(exigir("engenharia_clinica", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        chamado = conexao.execute("SELECT * FROM chamados_manutencao WHERE id = ?", (chamado_id,)).fetchone()
        if not chamado:
            raise HTTPException(status_code=404, detail="Chamado nao encontrado")
        if chamado["estado"] == "CONCLUIDO":
            raise HTTPException(status_code=400, detail="Chamado ja concluido")
        niveis = conexao.execute(
            "SELECT COUNT(*) AS total FROM escalonamentos_sla WHERE chamado_id = ?", (chamado_id,)
        ).fetchone()["total"]
        nivel = "DIRETOR_ADMINISTRATIVO" if niveis >= 1 else "ENGENHARIA_CLINICA"
        conexao.execute(
            "INSERT INTO escalonamentos_sla (chamado_id, nivel, destinatario, criado_em) VALUES (?, ?, ?, ?)",
            (chamado_id, nivel, destino.strip(), db.agora()),
        )
        conexao.execute("UPDATE chamados_manutencao SET estado = 'ESCALONADO' WHERE id = ?", (chamado_id,))
        criar_alerta(conexao, "ALTO", f"Chamado {chamado_id} escalonado para {destino.strip()}")
        registrar_auditoria(conexao, usuario, "SLA_ESCALONADO", chamado_id, novo={"destino": destino.strip()})
        registrar_evento(conexao, "SlaEscalonado", {"chamado_id": chamado_id, "destino": destino.strip()})
        conexao.commit()
    return {"chamado_id": chamado_id, "nivel": nivel, "estado": "ESCALONADO"}


@app.get("/api/manutencao/chamados/{chamado_id}/escalonamentos")
def listar_escalonamentos(
    chamado_id: str,
    usuario: dict = Depends(exigir("engenharia_clinica", "administrador", "auditoria")),
) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute("SELECT * FROM escalonamentos_sla WHERE chamado_id = ?", (chamado_id,)).fetchall()
        )


@app.get("/api/painel/senhas")
def listar_senhas(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(
            conexao.execute(
                "SELECT s.*, c.especialidade, p.nome AS paciente FROM painel_senhas s "
                "JOIN consultas_agendadas c ON c.id = s.consulta_id "
                "JOIN patients p ON p.id = c.patient_id "
                "ORDER BY s.id DESC LIMIT 30"
            ).fetchall()
        )


@app.post("/api/painel/chamar")
async def chamar_senha(
    senha_id: int,
    usuario: dict = Depends(exigir("rececionista", "enfermeiro", "medico", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        senha = conexao.execute("SELECT * FROM painel_senhas WHERE id = ?", (senha_id,)).fetchone()
        if not senha:
            raise HTTPException(status_code=404, detail="Senha nao encontrada")
        chamada_em = db.agora()
        conexao.execute(
            "UPDATE painel_senhas SET estado = 'CHAMADA', chamada_em = ? WHERE id = ?",
            (chamada_em, senha_id),
        )
        registrar_auditoria(conexao, usuario, "SENHA_CHAMADA", str(senha_id), novo={"senha": senha["senha"]})
        registrar_evento(conexao, "SenhaChamada", {"senha": senha["senha"], "consulta_id": senha["consulta_id"]})
        conexao.commit()
    await transmitir_painel(
        {"evento": "SenhaChamada", "senha": senha["senha"], "chamada_em": chamada_em}
    )
    return {"id": senha_id, "senha": senha["senha"], "estado": "CHAMADA"}


@app.websocket("/ws/painel")
async def websocket_painel(websocket: WebSocket) -> None:
    await websocket.accept()
    PAINEL_CLIENTES.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        PAINEL_CLIENTES.discard(websocket)


@app.post("/api/logistica/guias-remessa", status_code=201)
def criar_guia_remessa(
    dados: GuiaRemessaModel,
    usuario: dict = Depends(exigir("logistica", "enfermeiro", "farmacia", "administrador")),
) -> dict:
    if not unidade_permitida(usuario, dados.unidade_destino):
        raise HTTPException(status_code=403, detail="Unidade de destino fora do utilizador")
    identificador = criar_id("GRM")
    with conexao_aberta() as conexao:
        origem = usuario.get("unidade_codigo") or "DG"
        conexao.execute(
            "INSERT INTO guias_remessa (id, unidade_origem, unidade_destino, item, quantidade, estado, "
            "criado_por, criado_em) VALUES (?, ?, ?, ?, ?, 'EM_TRANSITO', ?, ?)",
            (
                identificador,
                origem,
                dados.unidade_destino.strip(),
                dados.item.strip(),
                dados.quantidade,
                usuario["id"],
                db.agora(),
            ),
        )
        assinar_documento(
            conexao,
            usuario,
            "GUIA_REMESSA",
            identificador,
            f"{origem}->{dados.unidade_destino}: {dados.item} x{dados.quantidade}",
        )
        registrar_evento(
            conexao,
            "GuiaRemessaCriada",
            {"guia_id": identificador, "destino": dados.unidade_destino.strip()},
        )
        registrar_bi(
            conexao,
            "guias_remessa",
            identificador,
            {"origem": origem, "destino": dados.unidade_destino.strip(), "item": dados.item},
            usuario,
        )
        conexao.commit()
    return {"id": identificador, "estado": "EM_TRANSITO"}


@app.get("/api/logistica/guias-remessa")
def listar_guias_remessa(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM guias_remessa ORDER BY criado_em DESC").fetchall())


@app.post("/api/compras/concursos", status_code=201)
def criar_concurso(
    dados: ConcursoModel,
    usuario: dict = Depends(exigir("compras", "administrador")),
) -> dict:
    identificador = criar_id("CONC")
    with conexao_aberta() as conexao:
        cotacao = conexao.execute("SELECT * FROM cotacoes WHERE id = ?", (dados.cotacao_id,)).fetchone()
        if not cotacao:
            raise HTTPException(status_code=404, detail="Cotacao nao encontrada")
        conexao.execute(
            "INSERT INTO concursos (id, cotacao_id, numero, estado, criado_por, criado_em) "
            "VALUES (?, ?, ?, 'ABERTO', ?, ?)",
            (identificador, dados.cotacao_id, dados.numero.strip(), usuario["id"], db.agora()),
        )
        conexao.execute("UPDATE cotacoes SET concurso_id = ? WHERE id = ?", (identificador, dados.cotacao_id))
        registrar_auditoria(conexao, usuario, "CONCURSO_CRIADO", identificador, novo={"numero": dados.numero})
        registrar_evento(conexao, "ConcursoCriado", {"concurso_id": identificador, "cotacao_id": dados.cotacao_id})
        conexao.commit()
    return {"id": identificador, "estado": "ABERTO"}


@app.get("/api/compras/concursos")
def listar_concursos(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM concursos ORDER BY criado_em DESC").fetchall())


@app.post("/api/compras/concursos/{concurso_id}/encerrar")
def encerrar_concurso(
    concurso_id: str,
    usuario: dict = Depends(exigir("compras", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        concurso = conexao.execute("SELECT * FROM concursos WHERE id = ?", (concurso_id,)).fetchone()
        if not concurso:
            raise HTTPException(status_code=404, detail="Concurso nao encontrado")
        if concurso["estado"] != "ABERTO":
            raise HTTPException(status_code=400, detail="Concurso ja encerrado")
        propostas = conexao.execute(
            "SELECT COUNT(*) AS total FROM propostas_fornecedores WHERE cotacao_id = ?",
            (concurso["cotacao_id"],),
        ).fetchone()["total"]
        if propostas < 2:
            raise HTTPException(status_code=400, detail="Concurso exige pelo menos duas propostas")
        conexao.execute("UPDATE concursos SET estado = 'ENCERRADO' WHERE id = ?", (concurso_id,))
        registrar_auditoria(conexao, usuario, "CONCURSO_ENCERRADO", concurso_id)
        registrar_evento(conexao, "ConcursoEncerrado", {"concurso_id": concurso_id})
        conexao.commit()
    return {"id": concurso_id, "estado": "ENCERRADO"}


@app.post("/api/financeiro/ordens-pagamento", status_code=201)
def criar_ordem_pagamento(
    dados: OrdemModel,
    usuario: dict = Depends(exigir("financeiro", "administrador")),
) -> dict:
    identificador = criar_id("OPG")
    with conexao_aberta() as conexao:
        requisicao = obter_requisicao(conexao, dados.purchase_id)
        if requisicao["estado"] not in {"EMPENHADA", "RECEBIDA"}:
            raise HTTPException(status_code=400, detail="Requisicao ainda nao empenhada")
        if requisicao["solicitante_id"] == usuario["id"]:
            raise HTTPException(status_code=403, detail="Segregacao de funcoes: solicitante nao pode pagar")
        conexao.execute(
            "INSERT INTO ordens_pagamento (id, purchase_id, fornecedor, valor, estado, aprovado_por, "
            "criado_por, criado_em) VALUES (?, ?, ?, ?, 'APROVADA', ?, ?, ?)",
            (
                identificador,
                dados.purchase_id,
                requisicao["fornecedor"],
                requisicao["valor"],
                usuario["id"],
                usuario["id"],
                db.agora(),
            ),
        )
        assinar_documento(
            conexao, usuario, "ORDEM_PAGAMENTO", identificador, f"{requisicao['fornecedor']}: {requisicao['valor']}"
        )
        registrar_auditoria(conexao, usuario, "ORDEM_PAGAMENTO_CRIADA", identificador)
        registrar_evento(conexao, "OrdemPagamentoCriada", {"ordem_id": identificador})
        conexao.commit()
    return {"id": identificador, "estado": "APROVADA"}


@app.get("/api/financeiro/ordens-pagamento")
def listar_ordens_pagamento(usuario: dict = Depends(exigir("financeiro", "auditoria", "administrador"))) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM ordens_pagamento ORDER BY criado_em DESC").fetchall())


@app.post("/api/compras/ordens-fornecimento", status_code=201)
def criar_ordem_fornecimento(
    dados: OrdemFornecimentoModel,
    usuario: dict = Depends(exigir("compras", "administrador")),
) -> dict:
    identificador = criar_id("OFN")
    with conexao_aberta() as conexao:
        requisicao = obter_requisicao(conexao, dados.purchase_id)
        if requisicao["solicitante_id"] == usuario["id"]:
            raise HTTPException(status_code=403, detail="Segregacao de funcoes: solicitante nao pode emitir ordem")
        conexao.execute(
            "INSERT INTO ordens_fornecimento (id, purchase_id, fornecedor, descricao, quantidade, estado, "
            "criado_por, criado_em) VALUES (?, ?, ?, ?, ?, 'EMITIDA', ?, ?)",
            (
                identificador,
                dados.purchase_id,
                requisicao["fornecedor"],
                dados.descricao.strip(),
                dados.quantidade,
                usuario["id"],
                db.agora(),
            ),
        )
        registrar_auditoria(conexao, usuario, "ORDEM_FORNECIMENTO_EMITIDA", identificador)
        registrar_evento(conexao, "OrdemFornecimentoEmitida", {"ordem_id": identificador})
        conexao.commit()
    return {"id": identificador, "estado": "EMITIDA"}


@app.get("/api/compras/ordens-fornecimento")
def listar_ordens_fornecimento(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM ordens_fornecimento ORDER BY criado_em DESC").fetchall())


@app.post("/api/rh/contratos-trabalho", status_code=201)
def criar_contrato_trabalho(
    dados: ContratoTrabalhoModel,
    usuario: dict = Depends(exigir("rh", "administrador")),
) -> dict:
    identificador = criar_id("CTRAB")
    with conexao_aberta() as conexao:
        if not conexao.execute("SELECT 1 FROM staff WHERE id = ?", (dados.staff_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Funcionario nao encontrado")
        conexao.execute(
            "INSERT INTO contratos_trabalho (id, staff_id, tipo, inicio, fim, salario_base, estado, "
            "criado_por, criado_em) VALUES (?, ?, ?, ?, ?, ?, 'ATIVO', ?, ?)",
            (
                identificador,
                dados.staff_id,
                dados.tipo.strip(),
                dados.inicio.strip(),
                dados.fim,
                dados.salario_base,
                usuario["id"],
                db.agora(),
            ),
        )
        assinar_documento(
            conexao,
            usuario,
            "CONTRATO_TRABALHO",
            identificador,
            f"{dados.staff_id}: {dados.tipo} - {dados.salario_base}",
        )
        registrar_auditoria(conexao, usuario, "CONTRATO_TRABALHO_CRIADO", identificador)
        conexao.commit()
    return {"id": identificador, "estado": "ATIVO"}


@app.get("/api/rh/contratos-trabalho")
def listar_contratos_trabalho(usuario: dict = Depends(exigir("rh", "administrador", "auditoria"))) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM contratos_trabalho ORDER BY criado_em DESC").fetchall())


@app.post("/api/folhas-salario/{folha_id}/processar")
def processar_folha(
    folha_id: str,
    usuario: dict = Depends(exigir("rh", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        folha = conexao.execute("SELECT * FROM folhas_salario WHERE id = ?", (folha_id,)).fetchone()
        if not folha:
            raise HTTPException(status_code=404, detail="Folha nao encontrada")
        staff = conexao.execute("SELECT * FROM staff WHERE nome = ?", (folha["funcionario"],)).fetchone()
        salario_base = folha["salario_base"]
        contrato = None
        if staff:
            contrato = conexao.execute(
                "SELECT * FROM contratos_trabalho WHERE staff_id = ? AND estado = 'ATIVO' ORDER BY inicio DESC LIMIT 1",
                (staff["id"],),
            ).fetchone()
            if contrato:
                salario_base = contrato["salario_base"]
        faltas = 0
        if staff:
            faltas = conexao.execute(
                "SELECT COUNT(*) AS total FROM leave_requests WHERE staff_id = ? AND estado IN ('APROVADO', 'HOMOLOGADO') "
                "AND tipo LIKE '%FALTA%' AND substr(inicio, 1, 7) = ?",
                (staff["id"], folha["mes"]),
            ).fetchone()["total"]
        descontos = folha["descontos"] + round(salario_base / 30 * faltas, 2)
        liquido = round(salario_base - descontos, 2)
        conexao.execute(
            "UPDATE folhas_salario SET salario_base = ?, descontos = ?, liquido = ?, estado = 'PROCESSADA' WHERE id = ?",
            (salario_base, descontos, liquido, folha_id),
        )
        registrar_auditoria(
            conexao,
            usuario,
            "FOLHA_PROCESSADA",
            folha_id,
            novo={"salario_base": salario_base, "descontos": descontos, "faltas": faltas, "liquido": liquido},
        )
        registrar_evento(conexao, "FolhaProcessada", {"folha_id": folha_id, "liquido": liquido})
        if staff:
            conexao.execute(
                "INSERT OR IGNORE INTO shifts (id, staff_id, data, turno, unidade, criado_por, criado_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    f"AJUSTE-{folha_id}",
                    staff["id"],
                    f"{folha['mes']}-01",
                    "AJUSTE_FOLHA",
                    staff["unidade"],
                    usuario["id"],
                    db.agora(),
                ),
            )
        registrar_bi(
            conexao,
            "folhas_salario",
            folha_id,
            {"liquido": liquido, "faltas": faltas, "unidade": usuario.get("unidade_codigo")},
            usuario,
        )
        conexao.commit()
    return {"id": folha_id, "salario_base": salario_base, "descontos": descontos, "liquido": liquido}


@app.get("/api/recibos/{folha_id}", response_class=HTMLResponse)
def recibo_folha(folha_id: str, usuario: dict = Depends(usuario_atual)) -> str:
    with conexao_aberta() as conexao:
        folha = conexao.execute("SELECT * FROM folhas_salario WHERE id = ?", (folha_id,)).fetchone()
        if not folha:
            raise HTTPException(status_code=404, detail="Folha nao encontrada")
        if usuario["perfil"] not in {"rh", "administrador", "auditoria"} and folha["funcionario"] != usuario["nome"]:
            raise HTTPException(status_code=403, detail="Sem permissao para este recibo")
    return (
        "<!doctype html><html lang='pt'><meta charset='utf-8'><title>Recibo</title>"
        f"<h1>Recibo de salario - {folha['mes']}</h1><p>Funcionario: {folha['funcionario']}</p>"
        f"<p>Base: {folha['salario_base']} | Descontos: {folha['descontos']} | Liquido: {folha['liquido']}</p>"
        f"<p>Estado: {folha['estado']}</p></html>"
    )


@app.post("/api/servicos-gerais", status_code=201)
def criar_servico_geral(
    dados: ServicoGeralModel,
    usuario: dict = Depends(usuario_atual),
) -> dict:
    area = dados.area.strip().upper()
    if area not in {"LAVANDARIA", "COZINHA", "SEGURANCA", "TI", "LIMPEZA"}:
        raise HTTPException(status_code=400, detail="Area invalida")
    identificador = criar_id("SG")
    with conexao_aberta() as conexao:
        conexao.execute(
            "INSERT INTO servicos_gerais (id, area, descricao, estado, criado_por, criado_em) "
            "VALUES (?, ?, ?, 'ABERTO', ?, ?)",
            (identificador, area, dados.descricao.strip(), usuario["id"], db.agora()),
        )
        registrar_auditoria(conexao, usuario, "SERVICO_GERAL_CRIADO", identificador, novo={"area": area})
        registrar_evento(conexao, "ServicoGeralCriado", {"id": identificador, "area": area})
        conexao.commit()
    return {"id": identificador, "area": area, "estado": "ABERTO"}


@app.get("/api/servicos-gerais")
def listar_servicos_gerais(usuario: dict = Depends(usuario_atual)) -> list[dict]:
    with conexao_aberta() as conexao:
        return em_lista(conexao.execute("SELECT * FROM servicos_gerais ORDER BY criado_em DESC").fetchall())


@app.get("/api/bi/indicadores")
def indicadores_bi(usuario: dict = Depends(exigir("gestor", "auditoria", "administrador"))) -> dict:
    with conexao_aberta() as conexao:
        total_atendimentos = conexao.execute("SELECT COUNT(*) AS total FROM episodes").fetchone()["total"]
        internamentos = conexao.execute(
            "SELECT COUNT(*) AS total FROM episodes WHERE estado = 'INTERNADO_ATIVO'"
        ).fetchone()["total"]
        stock_critico = conexao.execute(
            "SELECT COUNT(*) AS total FROM stock WHERE quantidade < minimo"
        ).fetchone()["total"]
        sla_excedido = conexao.execute(
            "SELECT COUNT(*) AS total FROM chamados_manutencao WHERE estado IN ('ESCALONADO', 'ABERTO')"
        ).fetchone()["total"]
        registos = em_lista(
            conexao.execute("SELECT origem, chave, unidade_codigo, criado_em FROM registos_bi ORDER BY id DESC LIMIT 100").fetchall()
        )
        for registo in registos:
            registo["chave"] = hashlib.sha256(registo["chave"].encode("utf-8")).hexdigest()[:12]
    return {
        "atendimentos": total_atendimentos,
        "internamentos_ativos": internamentos,
        "ruturas_stock": stock_critico,
        "sla_excedido": sla_excedido,
        "fonte": "data_mart local",
        "registos": registos,
    }


@app.get("/api/auditoria/exportar")
def exportar_auditoria(
    formato: str = "json",
    usuario: dict = Depends(exigir("auditoria", "administrador")),
) -> dict:
    with conexao_aberta() as conexao:
        registos = em_lista(conexao.execute("SELECT * FROM audit ORDER BY id").fetchall())
    if formato.lower() == "csv":
        linhas = ["id;user_id;perfil;acao;alvo;criado_em;hash"]
        linhas.extend(
            ";".join(
                str(registo.get(coluna) or "").replace(";", ",")
                for coluna in ("id", "user_id", "perfil", "acao", "alvo", "criado_em", "hash")
            )
            for registo in registos
        )
        return {"formato": "csv", "conteudo": "\n".join(linhas)}
    return {"formato": "json", "registos": registos, "total": len(registos)}


app.mount("/static", StaticFiles(directory=DIRETORIO_STATIC), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(DIRETORIO_STATIC / "index.html")

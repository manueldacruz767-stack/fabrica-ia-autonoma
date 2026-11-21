import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.migracoes import executar_migracoes

BASE = Path(__file__).resolve().parent.parent
CAMINHO_DB = Path(os.getenv("HIS_DB_PATH", BASE / "data" / "his.db"))

USUARIOS = (
    ("admin", "admin123", "administrador", "Administrador Geral"),
    ("medico", "medico123", "medico", "Dr. Antonio Silva"),
    ("enfermeiro", "enfermeiro123", "enfermeiro", "Enf. Maria Costa"),
    ("farmacia", "farmacia123", "farmacia", "Farm. Joaquim Nunes"),
    ("limpeza", "limpeza123", "limpeza", "Equipa de Higienizacao"),
    ("gestor", "gestor123", "gestor", "Gestor de Leitos"),
    ("auditor", "auditor123", "auditoria", "Auditoria Interna"),
    ("rh", "rh123", "rh", "Tecnico de RH"),
    ("chefe", "chefe123", "chefia", "Chefe de Servico"),
    ("compras", "compras123", "compras", "Compras e Aprovisionamento"),
    ("financeiro", "financeiro123", "financeiro", "Financas e Contabilidade"),
    ("juridico", "juridico123", "juridico", "Assessoria Juridica"),
    ("logistica", "logistica123", "logistica", "Logistica e Armazem"),
    ("laboratorio", "laboratorio123", "laboratorio", "Tecnico de Laboratorio"),
    ("imagiologia", "imagiologia123", "imagiologia", "Tecnico de Imagiologia"),
    ("fisioterapia", "fisioterapia123", "fisioterapia", "Fisioterapeuta"),
    ("rececionista", "rececionista123", "rececionista", "Rececionista"),
    ("diretor_clinico", "diretor_clinico123", "diretor_clinico", "Diretor Clinico"),
    ("diretor_enfermagem", "diretor_enfermagem123", "diretor_enfermagem", "Diretor de Enfermagem"),
    ("relacoes_publicas", "relacoes_publicas123", "relacoes_publicas", "Relacoes Publicas"),
    ("comissao_etica", "comissao_etica123", "comissao_etica", "Comissao de Etica"),
    ("direcao_pedagogica", "direcao_pedagogica123", "direcao_pedagogica", "Direcao Pedagogica"),
    ("engenharia_clinica", "engenharia_clinica123", "engenharia_clinica", "Engenharia Clinica"),
    ("nutricionista", "nutricionista123", "nutricionista", "Nutricao e Dietetica"),
    ("transportes", "transportes123", "transportes", "Transportes e Ambulancias"),
    ("seguranca", "seguranca123", "seguranca", "Seguranca Patrimonial"),
    ("ti", "ti123", "ti", "Tecnologias de Informacao"),
    ("lavandaria", "lavandaria123", "lavandaria", "Lavandaria"),
    ("cozinha", "cozinha123", "cozinha", "Cozinha"),
)

FUNCIONARIOS = (
    ("medico", "Dr. Antonio Silva", "medico", "Medicina"),
    ("enfermeiro", "Enf. Maria Costa", "enfermeiro", "Urgencia"),
    ("farmacia", "Farm. Joaquim Nunes", "farmacia", "Farmacia"),
    ("limpeza", "Equipa de Higienizacao", "limpeza", "Servicos Gerais"),
    ("gestor", "Gestor de Leitos", "gestor", "Administracao"),
    ("rh", "Tecnico de RH", "rh", "Recursos Humanos"),
    ("chefe", "Chefe de Servico", "chefia", "Urgencia"),
    ("compras", "Compras e Aprovisionamento", "compras", "Aprovisionamento"),
    ("financeiro", "Financas e Contabilidade", "financeiro", "Financas"),
    ("juridico", "Assessoria Juridica", "juridico", "Juridico"),
    ("logistica", "Logistica e Armazem", "logistica", "Armazem"),
    ("laboratorio", "Tecnico de Laboratorio", "laboratorio", "Laboratorio"),
    ("imagiologia", "Tecnico de Imagiologia", "imagiologia", "Imagiologia"),
    ("fisioterapia", "Fisioterapeuta", "fisioterapia", "Reabilitacao"),
    ("rececionista", "Rececionista", "rececionista", "Urgencia"),
    ("diretor_clinico", "Diretor Clinico", "diretor_clinico", "Direcao Clinica"),
    ("diretor_enfermagem", "Diretor de Enfermagem", "diretor_enfermagem", "Direcao de Enfermagem"),
    ("relacoes_publicas", "Relacoes Publicas", "relacoes_publicas", "Direcao Geral"),
    ("comissao_etica", "Comissao de Etica", "comissao_etica", "Etica"),
    ("direcao_pedagogica", "Direcao Pedagogica", "direcao_pedagogica", "Ensino"),
    ("engenharia_clinica", "Engenharia Clinica", "engenharia_clinica", "Engenharia"),
    ("nutricionista", "Nutricionista", "nutricionista", "Cozinha"),
    ("transportes", "Transportes", "transportes", "Transportes"),
    ("seguranca", "Seguranca", "seguranca", "Seguranca"),
    ("ti", "Tecnico TI", "ti", "TI"),
    ("lavandaria", "Lavandaria", "lavandaria", "Lavandaria"),
    ("cozinha", "Cozinha", "cozinha", "Cozinha"),
)

MEDICAMENTOS = (
    ("Paracetamol 500mg", 100, 20),
    ("Amoxicilina 500mg", 40, 10),
    ("Soro fisiologico 500ml", 60, 15),
    ("Adrenalina 1mg", 20, 5),
)

LEITOS = (
    ("UTI-01", "UCI"),
    ("UTI-02", "UCI"),
    ("OBS-01", "Urgencia"),
    ("OBS-02", "Urgencia"),
    ("A-01", "Enfermaria A"),
    ("A-02", "Enfermaria A"),
    ("A-03", "Enfermaria A"),
    ("A-04", "Enfermaria A"),
    ("A-05", "Enfermaria A"),
    ("A-06", "Enfermaria A"),
    ("A-07", "Enfermaria A"),
    ("A-08", "Enfermaria A"),
)

UNIDADES = (
    ("DG", "Direcao Geral", 1, None),
    ("DC", "Direcao Clinica", 2, "DG"),
    ("DE", "Direcao de Enfermagem", 2, "DG"),
    ("DA", "Direcao Administrativa e Financeira", 2, "DG"),
    ("URG", "Urgencia", 3, "DC"),
    ("UCI", "Cuidados Intensivos", 3, "DC"),
    ("ENF-A", "Enfermaria A", 3, "DE"),
    ("FARM", "Farmacia", 3, "DA"),
    ("LAB", "Laboratorio", 3, "DC"),
    ("IMG", "Imagiologia", 3, "DC"),
    ("REAB", "Reabilitacao", 3, "DC"),
    ("NUT", "Nutricao e Dietetica", 3, "DE"),
    ("APROV", "Aprovisionamento", 3, "DA"),
    ("FIN", "Financas", 3, "DA"),
    ("JUR", "Assessoria Juridica", 3, "DG"),
    ("AUD", "Auditoria Interna", 3, "DG"),
    ("ETICA", "Comissao de Etica", 3, "DG"),
    ("ENSINO", "Direcao Pedagogica", 3, "DG"),
    ("ENG", "Engenharia Clinica", 3, "DA"),
    ("LOG", "Logistica", 3, "DA"),
    ("TRANS", "Transportes", 3, "DA"),
    ("SEG", "Seguranca", 3, "DA"),
    ("TI", "Tecnologias de Informacao", 3, "DA"),
    ("LAV", "Lavandaria", 3, "DA"),
    ("COZ", "Cozinha", 3, "DA"),
)

UNIDADE_POR_PERFIL = {
    "administrador": "DG",
    "medico": "URG",
    "enfermeiro": "URG",
    "chefe": "URG",
    "rececionista": "URG",
    "farmacia": "FARM",
    "limpeza": "LOG",
    "gestor": "URG",
    "rh": "DG",
    "compras": "APROV",
    "financeiro": "FIN",
    "juridico": "JUR",
    "auditoria": "AUD",
    "logistica": "LOG",
    "laboratorio": "LAB",
    "imagiologia": "IMG",
    "fisioterapia": "REAB",
    "diretor_clinico": "DC",
    "diretor_enfermagem": "DE",
    "relacoes_publicas": "DG",
    "comissao_etica": "ETICA",
    "direcao_pedagogica": "ENSINO",
    "engenharia_clinica": "ENG",
    "nutricionista": "NUT",
    "transportes": "TRANS",
    "seguranca": "SEG",
    "ti": "TI",
    "lavandaria": "LAV",
    "cozinha": "COZ",
}


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ligacao() -> sqlite3.Connection:
    CAMINHO_DB.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(CAMINHO_DB, check_same_thread=False)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.execute("PRAGMA journal_mode = WAL")
    return conexao


def criar_salt() -> str:
    return secrets.token_hex(16)


def derivar_hash(senha: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), 120000).hex()


def inicializar() -> None:
    conexao = ligacao()
    try:
        conexao.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                nome TEXT NOT NULL,
                senha_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                perfil TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS elevations (
                token TEXT NOT NULL,
                episode_id TEXT NOT NULL,
                expira_em TEXT NOT NULL,
                justificacao TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS patients (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                documento TEXT,
                data_nascimento TEXT,
                desconhecido INTEGER NOT NULL DEFAULT 0,
                criado_por TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS episodes (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL REFERENCES patients(id),
                tipo TEXT NOT NULL,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS triages (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                queixa TEXT NOT NULL,
                sinais_vitais TEXT NOT NULL,
                cor TEXT NOT NULL,
                prioridade INTEGER NOT NULL,
                enfermeiro_id TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                autor_id TEXT NOT NULL,
                anamnese TEXT NOT NULL,
                hipotese TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS prescriptions (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                medicamento TEXT NOT NULL,
                dose TEXT NOT NULL,
                prescritor_id TEXT NOT NULL,
                estado TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS stock (
                id TEXT PRIMARY KEY,
                medicamento TEXT UNIQUE NOT NULL,
                quantidade INTEGER NOT NULL,
                minimo INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS beds (
                id TEXT PRIMARY KEY,
                codigo TEXT UNIQUE NOT NULL,
                unidade TEXT NOT NULL,
                estado TEXT NOT NULL,
                paciente_id TEXT,
                episodio_id TEXT
            );

            CREATE TABLE IF NOT EXISTS hygiene_tasks (
                id TEXT PRIMARY KEY,
                bed_id TEXT NOT NULL REFERENCES beds(id),
                estado TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                concluido_em TEXT
            );

            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                perfil TEXT,
                acao TEXT NOT NULL,
                alvo TEXT NOT NULL,
                anterior TEXT,
                novo TEXT,
                ip TEXT,
                criado_em TEXT NOT NULL,
                hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evento TEXT NOT NULL,
                payload TEXT NOT NULL,
                estado TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nivel TEXT NOT NULL,
                mensagem TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                lido INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS staff (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                perfil_funcional TEXT NOT NULL,
                unidade TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS shifts (
                id TEXT PRIMARY KEY,
                staff_id TEXT NOT NULL REFERENCES staff(id),
                data TEXT NOT NULL,
                turno TEXT NOT NULL,
                unidade TEXT NOT NULL,
                criado_por TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS leave_requests (
                id TEXT PRIMARY KEY,
                staff_id TEXT NOT NULL REFERENCES staff(id),
                tipo TEXT NOT NULL,
                inicio TEXT NOT NULL,
                fim TEXT NOT NULL,
                justificacao TEXT,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL,
                aprovado_por TEXT,
                homologado_por TEXT,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS purchase_requests (
                id TEXT PRIMARY KEY,
                descricao TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                valor REAL NOT NULL,
                unidade TEXT NOT NULL,
                solicitante_id TEXT NOT NULL,
                validador_tecnico_id TEXT,
                verificado_orcamento_id TEXT,
                parecer_juridico_id TEXT,
                aprovador_id TEXT,
                rececionista_id TEXT,
                estado TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS budget (
                id TEXT PRIMARY KEY,
                exercicio TEXT NOT NULL,
                total REAL NOT NULL,
                executado REAL NOT NULL DEFAULT 0,
                atualizado_por TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS commitments (
                id TEXT PRIMARY KEY,
                purchase_id TEXT NOT NULL REFERENCES purchase_requests(id),
                valor REAL NOT NULL,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mdt_orders (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                tipo TEXT NOT NULL,
                descricao TEXT NOT NULL,
                medico_id TEXT NOT NULL,
                estado TEXT NOT NULL,
                resultado TEXT,
                tecnico_id TEXT,
                validado_por TEXT,
                criado_em TEXT NOT NULL,
                concluido_em TEXT
            );

            CREATE TABLE IF NOT EXISTS pre_consultas (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                sinais_vitais TEXT NOT NULL,
                observacao TEXT,
                enfermeiro_id TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS internamentos (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                leito_id TEXT NOT NULL REFERENCES beds(id),
                motivo TEXT NOT NULL,
                estado TEXT NOT NULL,
                medico_id TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                alta_em TEXT
            );

            CREATE TABLE IF NOT EXISTS cirurgias (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                descricao TEXT NOT NULL,
                checklist TEXT NOT NULL,
                equipamento_id TEXT,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS equipamentos (
                id TEXT PRIMARY KEY,
                codigo TEXT UNIQUE NOT NULL,
                descricao TEXT NOT NULL,
                unidade TEXT NOT NULL,
                proxima_manutencao TEXT NOT NULL,
                estado TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS esterilizacoes (
                id TEXT PRIMARY KEY,
                lote TEXT UNIQUE NOT NULL,
                descricao TEXT NOT NULL,
                esterilizado_em TEXT NOT NULL,
                validade TEXT NOT NULL,
                indicador_biologico TEXT NOT NULL,
                responsavel_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chamados_manutencao (
                id TEXT PRIMARY KEY,
                equipamento_id TEXT NOT NULL REFERENCES equipamentos(id),
                descricao TEXT NOT NULL,
                prioridade TEXT NOT NULL,
                estado TEXT NOT NULL,
                sla TEXT NOT NULL,
                criado_por TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                concluido_em TEXT
            );

            CREATE TABLE IF NOT EXISTS unidades_organizacionais (
                codigo TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                nivel INTEGER NOT NULL,
                unidade_pai_codigo TEXT REFERENCES unidades_organizacionais(codigo),
                ativo INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS pareceres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id TEXT NOT NULL REFERENCES purchase_requests(id),
                tipo TEXT NOT NULL,
                parecer TEXT NOT NULL,
                aprovado INTEGER NOT NULL,
                autor_id TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documentos_assinados (
                id TEXT PRIMARY KEY,
                tipo_documento TEXT NOT NULL,
                referencia_id TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                hash_documento TEXT NOT NULL,
                assinatura TEXT NOT NULL,
                certificado_id TEXT NOT NULL,
                utilizador_id TEXT NOT NULL REFERENCES users(id),
                perfil_ativo TEXT NOT NULL,
                unidade_codigo TEXT,
                ip_origem TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sumarios_alta (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                diagnostico TEXT NOT NULL,
                evolucao TEXT NOT NULL,
                orientacoes TEXT NOT NULL,
                medicamentos TEXT NOT NULL,
                medico_id TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evolucoes (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                nota TEXT NOT NULL,
                conduta TEXT NOT NULL,
                proxima_avaliacao TEXT NOT NULL,
                autor_id TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS balancos_hidricos (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                entradas_ml INTEGER NOT NULL,
                saidas_ml INTEGER NOT NULL,
                dieta TEXT NOT NULL,
                turno TEXT NOT NULL,
                autor_id TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS guias_transferencia (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                destino TEXT NOT NULL,
                motivo TEXT NOT NULL,
                veiculo TEXT NOT NULL,
                acompanhante_id TEXT,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS obitos (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                causa TEXT NOT NULL,
                data_obito TEXT NOT NULL,
                medico_id TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS consultas_agendadas (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL REFERENCES patients(id),
                especialidade TEXT NOT NULL,
                medico_id TEXT REFERENCES users(id),
                data_hora TEXT NOT NULL,
                estado TEXT NOT NULL,
                retorno_de_id TEXT REFERENCES consultas_agendadas(id),
                criado_por TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS stock_setorial (
                id TEXT PRIMARY KEY,
                unidade_codigo TEXT NOT NULL REFERENCES unidades_organizacionais(codigo),
                item TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                minimo INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS movimentacoes_stock (
                id TEXT PRIMARY KEY,
                stock_setorial_id TEXT NOT NULL REFERENCES stock_setorial(id),
                tipo TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                origem TEXT,
                destino TEXT,
                responsavel_id TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS contratos (
                id TEXT PRIMARY KEY,
                fornecedor TEXT NOT NULL,
                objeto TEXT NOT NULL,
                valor REAL NOT NULL,
                inicio TEXT NOT NULL,
                fim TEXT NOT NULL,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cotacoes (
                id TEXT PRIMARY KEY,
                descricao TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                estimativa REAL NOT NULL,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS propostas_fornecedores (
                id TEXT PRIMARY KEY,
                cotacao_id TEXT NOT NULL REFERENCES cotacoes(id),
                fornecedor TEXT NOT NULL,
                valor REAL NOT NULL,
                prazo TEXT NOT NULL,
                selecionada INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS folhas_salario (
                id TEXT PRIMARY KEY,
                funcionario TEXT NOT NULL,
                mes TEXT NOT NULL,
                salario_base REAL NOT NULL,
                descontos REAL NOT NULL,
                liquido REAL NOT NULL,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS registos_ponto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                funcionario TEXT NOT NULL,
                data TEXT NOT NULL,
                entrada TEXT NOT NULL,
                saida TEXT
            );

            CREATE TABLE IF NOT EXISTS escalonamentos_sla (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chamado_id TEXT NOT NULL REFERENCES chamados_manutencao(id),
                nivel TEXT NOT NULL,
                destinatario TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS aprazamentos (
                id TEXT PRIMARY KEY,
                prescricao_id TEXT NOT NULL REFERENCES prescriptions(id),
                horario TEXT NOT NULL,
                estado TEXT NOT NULL,
                administrado_por TEXT REFERENCES users(id),
                administrado_em TEXT,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alergias (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL REFERENCES patients(id),
                substancia TEXT NOT NULL,
                reacao TEXT NOT NULL,
                registado_por TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS nutricao_dietas (
                id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL REFERENCES episodes(id),
                dieta TEXT NOT NULL,
                observacao TEXT,
                prescrita_por TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mdt_parametros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id TEXT NOT NULL REFERENCES mdt_orders(id),
                parametro TEXT NOT NULL,
                valor TEXT NOT NULL,
                unidade TEXT,
                valor_referencia TEXT,
                criticidade TEXT NOT NULL DEFAULT 'NORMAL'
            );

            CREATE TABLE IF NOT EXISTS guias_remessa (
                id TEXT PRIMARY KEY,
                unidade_origem TEXT NOT NULL REFERENCES unidades_organizacionais(codigo),
                unidade_destino TEXT NOT NULL REFERENCES unidades_organizacionais(codigo),
                item TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS concursos (
                id TEXT PRIMARY KEY,
                cotacao_id TEXT NOT NULL REFERENCES cotacoes(id),
                numero TEXT NOT NULL,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ordens_pagamento (
                id TEXT PRIMARY KEY,
                purchase_id TEXT NOT NULL REFERENCES purchase_requests(id),
                fornecedor TEXT NOT NULL,
                valor REAL NOT NULL,
                estado TEXT NOT NULL,
                aprovado_por TEXT REFERENCES users(id),
                criado_por TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ordens_fornecimento (
                id TEXT PRIMARY KEY,
                purchase_id TEXT NOT NULL REFERENCES purchase_requests(id),
                fornecedor TEXT NOT NULL,
                descricao TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS contratos_trabalho (
                id TEXT PRIMARY KEY,
                staff_id TEXT NOT NULL REFERENCES staff(id),
                tipo TEXT NOT NULL,
                inicio TEXT NOT NULL,
                fim TEXT,
                salario_base REAL NOT NULL,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS servicos_gerais (
                id TEXT PRIMARY KEY,
                area TEXT NOT NULL,
                descricao TEXT NOT NULL,
                estado TEXT NOT NULL,
                criado_por TEXT NOT NULL REFERENCES users(id),
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS painel_senhas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consulta_id TEXT NOT NULL REFERENCES consultas_agendadas(id),
                senha TEXT NOT NULL,
                estado TEXT NOT NULL,
                chamada_em TEXT
            );

            CREATE TABLE IF NOT EXISTS registos_bi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origem TEXT NOT NULL,
                chave TEXT NOT NULL,
                unidade_codigo TEXT,
                perfil TEXT,
                dados TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );
            """
        )

        for tabela, coluna, definicao in (
            ("users", "unidade_codigo", "TEXT"),
            ("audit", "perfil_ativo", "TEXT"),
            ("audit", "unidade_hospitalar", "TEXT"),
            ("audit", "dispositivo", "TEXT"),
            ("audit", "correlation_id", "TEXT"),
            ("outbox", "tentativas", "INTEGER NOT NULL DEFAULT 0"),
            ("outbox", "publicado_em", "TEXT"),
            ("outbox", "ultimo_erro", "TEXT"),
            ("prescriptions", "validade", "TEXT"),
            ("prescriptions", "risco_aceite", "INTEGER NOT NULL DEFAULT 0"),
            ("prescriptions", "justificacao_risco", "TEXT"),
            ("prescriptions", "alergia_verificada", "INTEGER NOT NULL DEFAULT 0"),
            ("cirurgias", "lote_id", "TEXT"),
            ("mdt_orders", "parametros", "TEXT"),
            ("mdt_orders", "assinatura", "TEXT"),
            ("mdt_orders", "hl7", "TEXT"),
            ("mdt_orders", "fhir", "TEXT"),
            ("cotacoes", "concurso_id", "TEXT"),
            ("episodes", "unidade_codigo", "TEXT"),
            ("purchase_requests", "fornecedor", "TEXT"),
        ):
            colunas = {linha["name"] for linha in conexao.execute(f"PRAGMA table_info({tabela})")}
            if coluna not in colunas:
                conexao.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")

        for codigo, nome, nivel, pai in UNIDADES:
            conexao.execute(
                "INSERT OR IGNORE INTO unidades_organizacionais "
                "(codigo, nome, nivel, unidade_pai_codigo, ativo) VALUES (?, ?, ?, ?, 1)",
                (codigo, nome, nivel, pai),
            )

        for username, senha, perfil, nome in USUARIOS:
            existente = conexao.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
            if not existente:
                salt = criar_salt()
                conexao.execute(
                    "INSERT INTO users (id, username, nome, senha_hash, salt, perfil) VALUES (?, ?, ?, ?, ?, ?)",
                    (username, username, nome, derivar_hash(senha, salt), salt, perfil),
                )

        for username, _senha, perfil, _nome in USUARIOS:
            unidade_codigo = UNIDADE_POR_PERFIL.get(perfil, "DG")
            conexao.execute("UPDATE users SET unidade_codigo = ? WHERE username = ?", (unidade_codigo, username))

        for unidade_codigo, item, quantidade, minimo in (
            ("FARM", "Paracetamol 500mg", 100, 20),
            ("FARM", "Soro fisiologico 500ml", 60, 15),
            ("COZ", "Refeicao padrao", 80, 20),
            ("LAV", "Roupa de cama", 120, 30),
            ("ENG", "Kit de calibrate", 10, 3),
        ):
            identificador = f"{unidade_codigo}-{item}"
            conexao.execute(
                "INSERT OR IGNORE INTO stock_setorial (id, unidade_codigo, item, quantidade, minimo) "
                "VALUES (?, ?, ?, ?, ?)",
                (identificador, unidade_codigo, item, quantidade, minimo),
            )

        for medicamento, quantidade, minimo in MEDICAMENTOS:
            conexao.execute(
                "INSERT OR IGNORE INTO stock (id, medicamento, quantidade, minimo) VALUES (?, ?, ?, ?)",
                (medicamento, medicamento, quantidade, minimo),
            )

        for codigo, unidade in LEITOS:
            conexao.execute(
                "INSERT OR IGNORE INTO beds (id, codigo, unidade, estado) VALUES (?, ?, ?, 'LIVRE')",
                (codigo, codigo, unidade),
            )

        for identificador, nome, perfil, unidade in FUNCIONARIOS:
            conexao.execute(
                "INSERT OR IGNORE INTO staff (id, nome, perfil_funcional, unidade) VALUES (?, ?, ?, ?)",
                (identificador, nome, perfil, unidade),
            )

        hoje = datetime.now(timezone.utc).date()
        for codigo, descricao, unidade, dias in (
            ("MON-01", "Monitor multiparametros", "UCI", 30),
            ("VEN-01", "Ventilador de UCI", "UCI", -2),
            ("AUT-01", "Autoclave central", "Esterilizacao", 60),
        ):
            conexao.execute(
                "INSERT OR IGNORE INTO equipamentos "
                "(id, codigo, descricao, unidade, proxima_manutencao, estado) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    codigo,
                    codigo,
                    descricao,
                    unidade,
                    (hoje + timedelta(days=dias)).isoformat(),
                    "BLOQUEADO" if dias < 0 else "ATIVO",
                ),
            )

        exercicio = str(datetime.now(timezone.utc).year)
        conexao.execute(
            "INSERT OR IGNORE INTO budget (id, exercicio, total, executado, atualizado_por, atualizado_em) "
            "VALUES (?, ?, 1000000, 0, 'sistema', ?)",
            (f"ORC-{exercicio}", exercicio, agora()),
        )
        conexao.commit()
        executar_migracoes(conexao)
    finally:
        conexao.close()

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

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
            """
        )

        for username, senha, perfil, nome in USUARIOS:
            existente = conexao.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
            if not existente:
                salt = criar_salt()
                conexao.execute(
                    "INSERT INTO users (id, username, nome, senha_hash, salt, perfil) VALUES (?, ?, ?, ?, ?, ?)",
                    (username, username, nome, derivar_hash(senha, salt), salt, perfil),
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
        conexao.commit()
    finally:
        conexao.close()

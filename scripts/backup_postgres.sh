#!/usr/bin/env bash
set -euo pipefail
umask 077

HOST="${POSTGRES_HOST:-localhost}"
PORTA="${POSTGRES_PORT:-5432}"
UTILIZADOR="${POSTGRES_USER:-his}"
BASE_DADOS="${POSTGRES_DB:-his}"
DESTINO="${BACKUP_DIR:-/backups}"
DIRETORIO_DADOS="${PGDATA:-/var/lib/postgresql/data}"
RETENCAO="${BACKUP_RETENTION_DAYS:-7}"
DATA="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$DESTINO"

if command -v pg_dump >/dev/null 2>&1; then
  FICHEIRO="$DESTINO/his-$DATA.dump"
  pg_dump -h "$HOST" -p "$PORTA" -U "$UTILIZADOR" -d "$BASE_DADOS" --format=custom --file="$FICHEIRO"
  echo "backup logico concluido: $FICHEIRO"
else
  echo "pg_dump indisponivel: backup logico ignorado" >&2
fi

if command -v wal-g >/dev/null 2>&1 && [ -d "$DIRETORIO_DADOS" ]; then
  PGDATA="$DIRETORIO_DADOS" PGHOST="$HOST" PGPORT="$PORTA" PGUSER="$UTILIZADOR" PGDATABASE="$BASE_DADOS" \
    wal-g backup-push "$DIRETORIO_DADOS"
  echo "backup WAL-G concluido"
else
  echo "wal-g indisponivel ou PGDATA ausente: backup continuo ignorado" >&2
fi

find "$DESTINO" -maxdepth 1 -type f -name 'his-*.dump' -mtime "+${RETENCAO}" -delete

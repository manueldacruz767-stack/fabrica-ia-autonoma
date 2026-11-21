#!/usr/bin/env bash
set -euo pipefail

BACKUP="${1:-}"
if [ -z "$BACKUP" ] || [ ! -f "$BACKUP" ]; then
  echo "Uso: scripts/restore_test.sh <caminho-do-backup.dump>" >&2
  exit 2
fi

IMAGEM="${POSTGRES_IMAGE:-postgres:16-alpine}"
NOME="his-restore-teste-$$"
TENTATIVAS=0

docker run -d --name "$NOME" \
  -e POSTGRES_DB=his \
  -e POSTGRES_USER=his \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  "$IMAGEM" >/dev/null

trap 'docker rm -f "$NOME" >/dev/null 2>&1 || true' EXIT

until docker exec "$NOME" pg_isready -U his -d his >/dev/null 2>&1; do
  TENTATIVAS=$((TENTATIVAS + 1))
  if [ "$TENTATIVAS" -ge 60 ]; then
    echo "postgres de teste nao ficou pronto" >&2
    exit 1
  fi
  sleep 1
done

docker cp "$BACKUP" "$NOME:/tmp/backup.dump" >/dev/null
docker exec "$NOME" pg_restore --no-owner --no-privileges -U his -d his /tmp/backup.dump

TABELAS="$(docker exec "$NOME" psql -U his -d his -tAc \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")"

case "$TABELAS" in
  ''|*[!0-9]*)
    echo "restauro invalido: contagem de tabelas inesperada" >&2
    exit 1
    ;;
esac

if [ "$TABELAS" -le 0 ]; then
  echo "restauro invalido: nenhuma tabela encontrada" >&2
  exit 1
fi

echo "restauro validado em container isolado: $TABELAS tabelas"

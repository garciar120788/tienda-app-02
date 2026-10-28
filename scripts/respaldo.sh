#!/usr/bin/env bash
# Genera un respaldo comprimido de la base de datos en ./backups
# Uso: ./scripts/respaldo.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
ARCHIVO="backups/tienda_$(date +%Y-%m-%d_%H%M%S).sql.gz"
docker compose exec -T db sh -c 'pg_dump --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  | gzip > "$ARCHIVO"
echo "Respaldo creado: $ARCHIVO ($(du -h "$ARCHIVO" | cut -f1))"

# Conserva solo los 30 respaldos más recientes
ls -1t backups/tienda_*.sql.gz 2>/dev/null | tail -n +31 | xargs -r rm --

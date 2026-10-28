#!/usr/bin/env bash
# Restaura un respaldo creado con respaldo.sh. REEMPLAZA los datos actuales.
# Uso: ./scripts/restaurar.sh backups/tienda_AAAA-MM-DD_HHMMSS.sql.gz
set -euo pipefail
cd "$(dirname "$0")/.."
ARCHIVO=${1:-}
if [ -z "$ARCHIVO" ] || [ ! -f "$ARCHIVO" ]; then
  echo "Uso: $0 backups/tienda_AAAA-MM-DD_HHMMSS.sql.gz"
  ls -1t backups/*.sql.gz 2>/dev/null | head -5 | sed 's/^/  disponible: /'
  exit 1
fi
read -r -p "Esto reemplazará TODOS los datos actuales con '$ARCHIVO'. ¿Continuar? (escribe SI): " OK
[ "$OK" = "SI" ] || { echo "Cancelado."; exit 1; }

docker compose stop web
gunzip -c "$ARCHIVO" | docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose start web
echo "Restauración completada."

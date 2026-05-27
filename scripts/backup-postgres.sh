#!/usr/bin/env bash
# Backup automatico PostgreSQL per Nextfolio.
# Uso: ./scripts/backup-postgres.sh
# Crontab suggerito: 0 3 * * * /opt/nextfolio/scripts/backup-postgres.sh >> /var/log/nextfolio-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/nextfolio/backups}"
CONTAINER="${POSTGRES_CONTAINER:-nextfolio_postgres}"
DB_USER="${POSTGRES_USER:-nextfolio}"
DB_NAME="${POSTGRES_DB:-nextfolio}"
KEEP_DAYS="${KEEP_DAYS:-30}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="nextfolio_${TIMESTAMP}.sql.gz"
FILEPATH="${BACKUP_DIR}/${FILENAME}"

echo "[$(date -Iseconds)] Starting backup → $FILEPATH"

docker exec "$CONTAINER" \
  pg_dump -U "$DB_USER" -d "$DB_NAME" --no-password \
  | gzip > "$FILEPATH"

SIZE=$(du -sh "$FILEPATH" | cut -f1)
echo "[$(date -Iseconds)] Backup complete: $FILENAME ($SIZE)"

# Rimuovi backup più vecchi di KEEP_DAYS giorni
DELETED=$(find "$BACKUP_DIR" -name "nextfolio_*.sql.gz" -mtime +"$KEEP_DAYS" -print -delete | wc -l)
if [ "$DELETED" -gt 0 ]; then
  echo "[$(date -Iseconds)] Removed $DELETED old backup(s) (older than ${KEEP_DAYS} days)"
fi

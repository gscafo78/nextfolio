#!/usr/bin/env bash
# Backup off-site: sincronizza i dump locali verso Backblaze B2 via rclone.
#
# Prerequisiti:
#   1. Installare rclone:  curl https://rclone.org/install.sh | sudo bash
#   2. Configurare remote: rclone config  (scegliere "b2" come tipo)
#      Inserire Account ID e Application Key di Backblaze B2.
#      Salvare il remote con nome "b2nextfolio" (o cambiare RCLONE_REMOTE sotto).
#   3. Creare il bucket B2 "nextfolio-backups" (o cambiare RCLONE_BUCKET).
#   4. Aggiungere al crontab (5 min dopo il backup locale):
#        5 2 * * * /opt/nextfolio/scripts/backup-offsite.sh >> /var/log/nextfolio-backup-offsite.log 2>&1
#
# Funzionamento:
#   - Carica solo i file nuovi o modificati (--update).
#   - Elimina sul remote i file non più presenti localmente (--delete-before)
#     per mantenere la stessa rotazione 30-giorni del backup locale.
#   - Imposta storage class COLD per ridurre i costi (B2 Lifecycle Rule alternativa).

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/nextfolio/backups}"
RCLONE_REMOTE="${RCLONE_REMOTE:-b2nextfolio}"
RCLONE_BUCKET="${RCLONE_BUCKET:-nextfolio-backups}"
RCLONE_PATH="${RCLONE_REMOTE}:${RCLONE_BUCKET}/postgres"

# Verifica dipendenza
if ! command -v rclone &>/dev/null; then
  echo "[ERROR] rclone non trovato. Installa con: curl https://rclone.org/install.sh | sudo bash"
  exit 1
fi

# Verifica che la directory locale esista e non sia vuota
if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "[ERROR] Directory backup non trovata: $BACKUP_DIR"
  exit 1
fi

BACKUP_COUNT=$(find "$BACKUP_DIR" -name "*.sql.gz" | wc -l)
if [[ "$BACKUP_COUNT" -eq 0 ]]; then
  echo "[WARN] Nessun file .sql.gz in $BACKUP_DIR — skip"
  exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Avvio sincronizzazione off-site → ${RCLONE_PATH}"

rclone sync "$BACKUP_DIR" "$RCLONE_PATH" \
  --update \
  --delete-before \
  --transfers 4 \
  --checkers 8 \
  --b2-upload-cutoff 10M \
  --progress \
  --log-level INFO

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sincronizzazione completata. File remoti: $(rclone size "${RCLONE_PATH}" 2>/dev/null | head -1)"

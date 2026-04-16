#!/bin/bash
# CompLai Database Backup Script
# Usage: ./scripts/backup.sh
# Cron: 0 2 * * * /path/to/complai-v2/scripts/backup.sh

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DATABASE_URL="${DATABASE_URL:-postgresql://complai:complai_secret@localhost:5432/complai_db}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/complai_backup_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# Dump and compress
pg_dump "$DATABASE_URL" | gzip > "$BACKUP_FILE"

# Verify backup
if [ -s "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date)] Backup complete: $BACKUP_FILE ($SIZE)"
else
    echo "[$(date)] ERROR: Backup file is empty!" >&2
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Upload to S3 if AWS CLI available
if command -v aws &> /dev/null && [ -n "${S3_BACKUP_BUCKET:-}" ]; then
    aws s3 cp "$BACKUP_FILE" "s3://${S3_BACKUP_BUCKET}/backups/"
    echo "[$(date)] Uploaded to S3: s3://${S3_BACKUP_BUCKET}/backups/"
fi

# Clean old backups
find "$BACKUP_DIR" -name "complai_backup_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete
echo "[$(date)] Cleaned backups older than ${RETENTION_DAYS} days"

echo "[$(date)] Backup process complete"

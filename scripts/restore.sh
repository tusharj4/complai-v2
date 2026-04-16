#!/bin/bash
# CompLai Database Restore Script
# Usage: ./scripts/restore.sh <backup_file.sql.gz>

set -euo pipefail

BACKUP_FILE="${1:?Usage: ./scripts/restore.sh <backup_file.sql.gz>}"
DATABASE_URL="${DATABASE_URL:-postgresql://complai:complai_secret@localhost:5432/complai_db}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

echo "[$(date)] WARNING: This will replace the current database!"
echo "Restoring from: $BACKUP_FILE"
read -p "Continue? (y/N) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "[$(date)] Starting restore..."
    gunzip -c "$BACKUP_FILE" | psql "$DATABASE_URL"
    echo "[$(date)] Restore complete"
else
    echo "Aborted."
fi

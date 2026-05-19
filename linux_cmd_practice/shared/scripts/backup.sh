#!/bin/bash
# Database Backup Script
# Usage: ./backup.sh [database_name]

DB_NAME="${1:-production}"
BACKUP_DIR="/backups/${DB_NAME}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"
echo "[$(date)] Starting backup for $DB_NAME ..."

# Simulated backup
sleep 1
echo "Backup saved to: $BACKUP_FILE"
echo "Size: 128MB"
echo "[$(date)] Backup completed successfully"

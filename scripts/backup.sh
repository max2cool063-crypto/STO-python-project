#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${1:-${BACKUP_ROOT}/${TIMESTAMP}}"
QUIESCE_APP="${BACKUP_QUIESCE_APP:-False}"

mkdir -p "${BACKUP_DIR}"

DB_DUMP="${BACKUP_DIR}/postgres.dump"
MEDIA_ARCHIVE="${BACKUP_DIR}/media.tar.gz"
MANIFEST="${BACKUP_DIR}/manifest.txt"

restart_app=false
cleanup() {
  if [[ "${restart_app}" == "true" ]]; then
    docker compose up -d web cron >/dev/null
  fi
}
trap cleanup EXIT

if [[ "${QUIESCE_APP}" == "True" ]]; then
  echo "Stopping web and cron for a DB/media-consistent backup..."
  docker compose stop web cron >/dev/null
  restart_app=true
fi

echo "Backing up PostgreSQL..."
docker compose exec -T db sh -ceu '
  pg_dump \
    --format=custom \
    --no-owner \
    --no-privileges \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB"
' > "${DB_DUMP}"

echo "Backing up media volume..."
docker compose run --rm --no-deps --entrypoint python web -c '
import sys
import tarfile

with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
    archive.add("/app/media", arcname=".")
' > "${MEDIA_ARCHIVE}"

GIT_COMMIT="$(git rev-parse HEAD 2>/dev/null || printf 'unknown')"
cat > "${MANIFEST}" <<EOF
created_at_utc=${TIMESTAMP}
git_commit=${GIT_COMMIT}
database_dump=postgres.dump
media_archive=media.tar.gz
quiesced_app=${QUIESCE_APP}
EOF

if command -v sha256sum >/dev/null 2>&1; then
  (cd "${BACKUP_DIR}" && sha256sum postgres.dump media.tar.gz manifest.txt > SHA256SUMS)
elif command -v shasum >/dev/null 2>&1; then
  (cd "${BACKUP_DIR}" && shasum -a 256 postgres.dump media.tar.gz manifest.txt > SHA256SUMS)
else
  echo "WARNING: sha256sum/shasum not found; checksum file was not created." >&2
fi

echo "Backup created: ${BACKUP_DIR}"
echo "Copy this directory to encrypted off-host storage and test restores regularly."

#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: RESTORE_CONFIRM=YES $0 <backup-directory>" >&2
  exit 2
fi

BACKUP_DIR="$1"
DB_DUMP="${BACKUP_DIR}/postgres.dump"
MEDIA_ARCHIVE="${BACKUP_DIR}/media.tar.gz"
CHECKSUMS="${BACKUP_DIR}/SHA256SUMS"

if [[ "${RESTORE_CONFIRM:-}" != "YES" ]]; then
  echo "Refusing destructive restore. Re-run with RESTORE_CONFIRM=YES." >&2
  exit 2
fi

for required in "${DB_DUMP}" "${MEDIA_ARCHIVE}"; do
  if [[ ! -f "${required}" ]]; then
    echo "Missing backup file: ${required}" >&2
    exit 2
  fi
done

if [[ -f "${CHECKSUMS}" ]]; then
  echo "Verifying backup checksums..."
  if command -v sha256sum >/dev/null 2>&1; then
    (cd "${BACKUP_DIR}" && sha256sum -c SHA256SUMS)
  elif command -v shasum >/dev/null 2>&1; then
    (cd "${BACKUP_DIR}" && shasum -a 256 -c SHA256SUMS)
  else
    echo "WARNING: checksum file exists but sha256sum/shasum is unavailable." >&2
  fi
fi

echo "Stopping application processes before restore..."
docker compose stop web cron mail >/dev/null || true

echo "Ensuring PostgreSQL and Redis are running..."
docker compose up -d db redis >/dev/null

until docker compose exec -T db sh -ceu 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; do
  sleep 2
done

echo "Recreating PostgreSQL database..."
docker compose exec -T db sh -ceu '
  dropdb --if-exists --force --maintenance-db=postgres -U "$POSTGRES_USER" "$POSTGRES_DB"
  createdb --maintenance-db=postgres -U "$POSTGRES_USER" "$POSTGRES_DB"
'

echo "Restoring PostgreSQL dump..."
docker compose exec -T db sh -ceu '
  pg_restore \
    --exit-on-error \
    --no-owner \
    --no-privileges \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB"
' < "${DB_DUMP}"

echo "Restoring media volume..."
docker compose run --rm --no-deps --entrypoint python web -c '
import pathlib
import shutil
import sys
import tarfile

root = pathlib.Path("/app/media")
root.mkdir(parents=True, exist_ok=True)
for child in root.iterdir():
    if child.is_dir() and not child.is_symlink():
        shutil.rmtree(child)
    else:
        child.unlink(missing_ok=True)

root_resolved = root.resolve()
with tarfile.open(fileobj=sys.stdin.buffer, mode="r|gz") as archive:
    for member in archive:
        if member.issym() or member.islnk():
            raise RuntimeError(f"Refusing link in media backup: {member.name}")
        target = (root / member.name).resolve()
        if target != root_resolved and root_resolved not in target.parents:
            raise RuntimeError(f"Unsafe media backup path: {member.name}")
        archive.extract(member, root)
' < "${MEDIA_ARCHIVE}"

echo "Applying migrations for the currently deployed code..."
docker compose run --rm migrate

echo "Starting application..."
# DB/Redis are already running and migrations succeeded above. Avoid invoking
# the one-shot migrate dependency a second time just to resume web/cron.
docker compose up -d --no-deps web cron mail

echo "Restore completed. Verify the site, recent appointments, and protected media before reopening traffic."

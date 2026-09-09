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

resume_web=false
resume_cron=false
resume_mail=false
cleanup() {
  # Restore exactly the running state observed before a quiesced snapshot.
  # Never start a service that was already stopped before backup began.
  if [[ "${resume_web}" == "true" ]]; then
    docker compose start web >/dev/null || true
  fi
  if [[ "${resume_cron}" == "true" ]]; then
    docker compose start cron >/dev/null || true
  fi
  if [[ "${resume_mail}" == "true" ]]; then
    docker compose start mail >/dev/null || true
  fi
}
trap cleanup EXIT

if [[ "${QUIESCE_APP}" == "True" ]]; then
  running_services="$(docker compose ps --services --filter status=running)"
  services_to_stop=()

  if grep -qx "web" <<<"${running_services}"; then
    resume_web=true
    services_to_stop+=(web)
  fi
  if grep -qx "cron" <<<"${running_services}"; then
    resume_cron=true
    services_to_stop+=(cron)
  fi
  if grep -qx "mail" <<<"${running_services}"; then
    resume_mail=true
    services_to_stop+=(mail)
  fi

  if (( ${#services_to_stop[@]} > 0 )); then
    echo "Stopping running application services for a DB/media-consistent backup..."
    docker compose stop "${services_to_stop[@]}" >/dev/null
  else
    echo "Application services are already stopped; taking backup without changing their state."
  fi
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
web_was_running=${resume_web}
cron_was_running=${resume_cron}
mail_was_running=${resume_mail}
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

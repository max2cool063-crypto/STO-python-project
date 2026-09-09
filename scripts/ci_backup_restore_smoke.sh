#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${CI_BACKUP_RESTORE_SMOKE:-}" != "YES" ]]; then
  echo "Refusing destructive smoke test. Set CI_BACKUP_RESTORE_SMOKE=YES." >&2
  exit 2
fi

# Always use a fresh namespace; never operate on the caller's deployment.
export COMPOSE_PROJECT_NAME="sto-ci-smoke-$(date +%s)-$$"
export COMPOSE_PATH_SEPARATOR=,
export COMPOSE_FILE=docker-compose.yml,docker-compose.smoke.yml
docker compose config --quiet
mkdir -p ./backups
backup_root_abs="$(cd ./backups && pwd -P)"
BACKUP_DIR="$(mktemp -d "${backup_root_abs}/ci-smoke.XXXXXX")"
cleanup() {
  docker compose down -v --remove-orphans >/dev/null 2>&1 || true
  if [[ "${BACKUP_DIR}" == "${backup_root_abs}"/ci-smoke.* ]]; then
    rm -rf -- "${BACKUP_DIR}"
  fi
}
trap cleanup EXIT

echo "Disposable Compose project: ${COMPOSE_PROJECT_NAME}"
docker compose build web
echo "Starting disposable PostgreSQL and Redis..."
docker compose up -d db redis >/dev/null
until docker compose exec -T db sh -ceu 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; do
  sleep 1
done

echo "Applying migrations and creating an appointment with a real image..."
docker compose run --rm migrate >/dev/null
docker compose run --rm --no-deps web python manage.py shell -c 'from scripts.backup_restore_fixture import seed; seed()' >/dev/null

# Backup must resume web without starting a cron that was stopped beforehand.
docker compose up -d web cron mail >/dev/null
docker compose stop cron mail >/dev/null
BACKUP_QUIESCE_APP=True bash scripts/backup.sh "${BACKUP_DIR}" >/dev/null
running_services="$(docker compose ps --services --filter status=running)"
grep -qx "web" <<<"${running_services}"
if grep -Eq '^(cron|mail)$' <<<"${running_services}"; then
  echo "Backup incorrectly started a background service that was stopped beforehand." >&2
  exit 1
fi

echo "Mutating the appointment, user and image after backup..."
docker compose run --rm --no-deps web python manage.py shell -c 'from scripts.backup_restore_fixture import mutate; mutate()' >/dev/null

echo "Restoring disposable backup..."
RESTORE_CONFIRM=YES bash scripts/restore.sh "${BACKUP_DIR}"

echo "Verifying database relations, exact image bytes and protected media access..."
docker compose run --rm --no-deps web python manage.py shell -c 'from scripts.backup_restore_fixture import verify; verify()'
echo "Backup/restore smoke test passed."

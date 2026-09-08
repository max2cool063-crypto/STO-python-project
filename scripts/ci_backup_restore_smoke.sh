#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${CI_BACKUP_RESTORE_SMOKE:-}" != "YES" ]]; then
  echo "Refusing destructive smoke test. Set CI_BACKUP_RESTORE_SMOKE=YES." >&2
  exit 2
fi

BACKUP_DIR="./backups/ci-smoke"
cleanup() {
  docker compose down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "${BACKUP_DIR}"
}
trap cleanup EXIT

cleanup
mkdir -p "${BACKUP_DIR}"

echo "Starting disposable PostgreSQL and Redis..."
docker compose up -d db redis >/dev/null
until docker compose exec -T db sh -ceu 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; do
  sleep 1
done

echo "Applying migrations and creating sentinel data..."
docker compose run --rm migrate >/dev/null
docker compose run --rm --no-deps web python manage.py shell -c '
from django.contrib.auth import get_user_model
get_user_model().objects.create_user(username="ci-restore-sentinel", password="ci-sentinel-password")
' >/dev/null
docker compose run --rm --no-deps --entrypoint python web -c '
from pathlib import Path
path = Path("/app/media/ci-restore-sentinel.txt")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("original", encoding="utf-8")
'

# Exercise quiesced backup with only web running. The backup must not start cron
# merely because it was asked to quiesce application services.
docker compose up -d web cron >/dev/null
docker compose stop cron >/dev/null
BACKUP_QUIESCE_APP=True bash scripts/backup.sh "${BACKUP_DIR}" >/dev/null
running_services="$(docker compose ps --services --filter status=running)"
grep -qx "web" <<<"${running_services}"
if grep -qx "cron" <<<"${running_services}"; then
  echo "Backup incorrectly started a cron service that was stopped beforehand." >&2
  exit 1
fi

echo "Mutating database and media after backup..."
docker compose run --rm --no-deps web python manage.py shell -c '
from django.contrib.auth import get_user_model
get_user_model().objects.filter(username="ci-restore-sentinel").delete()
' >/dev/null
docker compose run --rm --no-deps --entrypoint python web -c '
from pathlib import Path
Path("/app/media/ci-restore-sentinel.txt").write_text("mutated", encoding="utf-8")
'

echo "Restoring disposable backup..."
RESTORE_CONFIRM=YES bash scripts/restore.sh "${BACKUP_DIR}" >/dev/null

echo "Verifying restored database and media..."
docker compose run --rm --no-deps web python manage.py shell -c '
from django.contrib.auth import get_user_model
assert get_user_model().objects.filter(username="ci-restore-sentinel").count() == 1
' >/dev/null
docker compose run --rm --no-deps --entrypoint python web -c '
from pathlib import Path
assert Path("/app/media/ci-restore-sentinel.txt").read_text(encoding="utf-8") == "original"
'

echo "Backup/restore smoke test passed."

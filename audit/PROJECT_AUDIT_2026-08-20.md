# STO project audit — 2026-08-20

## Scope

Audit of the `fix/full-project-audit-2026-08-18` branch before merging into `main`.

## CI baseline

The latest pre-audit branch commit passed the repository GitHub Actions workflow `Django tests` (configuration check, migration check, and `booking.tests`).

## Findings

### Fixed before merge

- Manual station booking accepted an arbitrary global `Car.id` when an operator supplied `car_id` directly. The existing-car lookup is now scoped to vehicles already known by the current station. A regression test was added.

### Medium/low-priority follow-up

- Production security flags in `auto_booking/settings.py` are environment-controlled and default to development-safe values. Production deployment should explicitly enable HTTPS redirect, secure cookies, HSTS and proxy settings.
- `auto_booking/urls.py` serves media through Django. This is acceptable for the current single-container deployment, but a production reverse proxy/object storage layer is preferable as traffic grows.
- `booking/views/api.py` has an avoidable query pattern in `brands_with_models_api()` because the prefetched related manager is re-ordered per brand.
- `booking/views/booking.py` exposes raw exception text in a user-facing error message; production code should log the exception and show a generic message.
- `docker-compose.yml` runs migrations and collectstatic in the web startup command. This is workable for the current single web instance, but should become a separate deployment step before horizontal scaling.
- The cron loop suppresses management-command failures with `|| true`; operational failures can therefore be missed without external monitoring.
- `station_list.html` contains a large inline style/script block. The UI is working, but these should eventually be moved into versioned static assets for maintainability.
- There is no dedicated CI job for Docker image build/compose validation. The existing CI validates Django configuration, migrations and tests, but not the container build.

## Recommendation

After the security regression fix passes CI, merge this branch into `main`. Then use a separate branch from the merged `main` for the Django 5.2 LTS upgrade, keeping the framework upgrade isolated from UI/security work.

## Django 5.2 LTS upgrade — started

Branch: `chore/django-5-2-upgrade-2026-08-20`

Initial upgrade changes:

- Django pinned to `5.2.17`, the current Django 5.2 LTS patch release.
- `django-jazzmin` pinned to `3.0.2`, which supports Django 5.2.
- Removed the obsolete `USE_L10N` setting; it was removed in Django 5.0.
- Updated the Dockerfile and README to reflect Django 5.2 LTS.

The repository CI workflow is configured to run on pushes to `main` and on pull requests targeting `main`. This branch currently has no pull request, so the Django 5.2 test suite has not yet been executed by GitHub Actions for these changes.

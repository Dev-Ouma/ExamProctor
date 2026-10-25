# Staging stack

```
make up          # build, start, wait for health, seed (first run: ~5-10 min)
make test        # service + JS lint and tests
make test-moodle # PHPUnit for both plugins inside the moodle container
make down        # stop; make reset also deletes data volumes
```

| Service | URL | Notes |
| --- | --- | --- |
| Moodle 4.5.1+ (Build 20250131), PHP 8.1 | http://localhost:8080 | admin password: `MOODLE_ADMIN_PASSWORD` in `staging/.env` (generated, git-ignored) |
| ExamProctor service | http://localhost:8000/v1/health, `/v1/health/ready` | readiness checks Postgres, Redis, object store |

Seeded synthetic data: course `EP-STAGING-101`, quiz "Proctored practice quiz" (5 true/false, 15 min), users `epteacher`, `epinvigilator`, `epreviewer`, `epstudent01`..`epstudent20` (password `SEED_USER_PASSWORD`, default `Staging#2026`). Seed is idempotent.

Plugins are bind-mounted read-only from `moodle/`; after editing a plugin's version, run `docker compose -f staging/compose.yml --env-file staging/.env exec -u www-data moodle php admin/cli/upgrade.php --non-interactive`.

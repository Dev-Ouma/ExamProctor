# Runbooks

| Situation | Runbook |
| --- | --- |
| Releasing a new version, or undoing one | [deploy-and-rollback.md](deploy-and-rollback.md) |
| Proctoring must stop now (service fault, false flags, policy decision) | [kill-switch.md](kill-switch.md) |
| Service unhealthy or unreachable during an exam | [service-down.md](service-down.md) |
| Subject access, erasure, legal hold, retention | [data-requests.md](data-requests.md) |

Health: `https://<moodle>/examproctor-api/v1/health/ready` returns `{"status":"ok"}` when Postgres,
Redis and the object store all answer. `deploy/deploy.sh status user@host` shows versions.

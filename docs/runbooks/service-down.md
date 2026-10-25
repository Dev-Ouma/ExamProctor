# Service down or degraded during an exam

## Symptoms

- Students cannot pass the pre-check ("The connection to the proctoring service failed").
- Live wall shows "refreshing every 15 s" and stale "Not seen since" times.
- `/examproctor-api/v1/health/ready` is not `ok`.

## What students lose and what they do not

- Moodle answers are never at risk: they autosave to Moodle, not to the service.
- Students already sitting keep answering; snapshots queue in their browser (IndexedDB) and upload
  when the service returns. Gaps are recorded as connectivity, not misconduct.
- New starts are blocked while the service is down (the gate needs a service-signed ready record).

## Steps

1. `deploy/deploy.sh status user@host`. Look at which check fails.
2. Object store full or failing: `sudo docker compose logs --tail 50 objectstore`. "No writable
   volumes" means the volume limit; the compose file must have `-volume.max=0`.
3. Restart the failing container: `cd /opt/examproctor && sudo docker compose up -d <service>`.
4. If a deploy caused it: `deploy/deploy.sh rollback user@host`.
5. If not healthy within 10 minutes and students are waiting to start: turn on the kill switch
   ([kill-switch.md](kill-switch.md)) so the exam goes ahead unproctored, with the exams office's
   agreement, and record the window.
6. Afterwards: write up times, cause, sittings affected; check the outbox drained
   (`SELECT count(*) FROM webhook_outbox WHERE delivered_at IS NULL` should reach 0).

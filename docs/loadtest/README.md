# M7 load test results (2026-10-25)

Tool: `service/examproctor_service/simulate.py` (`make loadtest-up`, `make loadtest USERS=...`).
Each candidate runs the real API flow (exchange, consent, pre-check, camera every 30 s, screen every
30 s for 60 % desktop candidates, events every 5 s, heartbeat every 10 s, finish); 10 % misbehave on
a script. Webhooks go to a sink, not Moodle. Images are ~50 KB synthetic JPEGs.

Bench: one MacBook (12 cores, 24 GB). Docker VM 12 vCPU / 8 GB running Postgres, Redis, SeaweedFS,
4 API processes and 4 AI workers; the simulator ran on the same machine (6 processes).

| Candidates | API p95 | Uploads OK | Capture -> flag on wall p95 | Verdict |
| --- | --- | --- | --- | --- |
| 50 (x3 speed) | 11 ms | 100 % (573) | 2.4 s | pass |
| 1,000 | 15 ms | 100 % (8,851) | 3.9 s | **pass** |
| 3,000 | 22.9 s | 100 % (20,014) | 56 s | miss |
| 5,000 | 42.1 s | 100 % (73,930) | 84 s | miss |

Spec targets: API p95 < 300 ms, uploads >= 99 %, flag on the live wall p95 < 15 s.

## Why 3,000 and 5,000 missed

Profile at 3,000 candidates: Docker VM load average 9 on 12 vCPU, simulator 3.4 cores on the same
host, AI workers ~3.8 cores, API processes ~40 % each, Postgres 60 % with no lock waits. The bench
machine was saturated; the service processes were not. These runs therefore do not show a service
limit, and they do not prove 5,000 either. Gate D's load criterion stays **open**.

## Defects found and fixed by the load test

1. Replicas starting together crashed creating tables (`UniqueViolationError` on `pg_type`).
   Fixed: schema changes take a Postgres advisory lock.
2. SeaweedFS stopped accepting writes after 8 x 1 GB volumes ("No writable volumes and no free
   volumes left"), with 395 GB of disk free: 98.5 % of uploads failed in the first 5,000 run. This
   would have stopped agiledev after ~8 GB of evidence. Fixed: `-volume.max=0` (size from disk) in
   staging and on agiledev.
3. The live wall issued several queries per session. Fixed: two queries for the whole wall.
4. The first simulator measured its own event-loop lag. Fixed: candidates spread over processes.

## Next run (to close Gate D)

- Service stack on a dedicated host sized for the exam (suggest 16 vCPU / 32 GB; AI workers on
  their own host or with a CPU cap) and the simulator on a second machine on the same network.
- Repeat 1,000 / 3,000 / 5,000. If the API misses then, the first candidates are: `complete`
  re-reads each object to hash it (use store-side checksums), more API processes, and a larger
  asyncpg pool.
- Never run a full ramp against agiledev; it shares its host with production sites.

Raw reports: `5000-run2.md` (latest 5,000), `3000.md` (3,000 run).

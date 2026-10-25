# Go-live checklist

Tick each item with the date and who checked it. Items marked **owner** need an OUK decision.

## Before the pilot

- [x] Launch gate: attempt needs a service-signed ready record (M2; e2e `staging/seed/e2e_gate.php`).
- [x] Capture survives page changes and a 60 s network drop (M3; `capture.spec.ts`).
- [x] Review, decisions, appeals, exports, privacy export and erase (M5).
- [x] Live wall: warn, message, pause, resume, end reach the student (M6; `live.spec.ts`).
- [x] Security checklist R-01..R-07 (`docs/security-checklist.md`); HawkScan 0 high / 0 medium.
- [x] Accessibility WCAG 2.1 AA on ExamProctor screens (`a11y.spec.ts`).
- [x] Kill switch and rollback rehearsed (runbooks).
- [ ] Load test at 5,000 on a dedicated host (`docs/loadtest/README.md`; 1,000 passed on a laptop).
- [ ] Gate C: face-model licences recorded in `docs/licences.md` and bias report on OUK photos
      (`python -m examproctor_service.evaluate`).
- [x] Lawful basis: consent through the admission offer (OUK decision 2026-10-25; no separate DPA).
- [ ] DPIA record kept for the DPO (`docs/dpia-draft.md`). **owner**
- [ ] Degradation policy when the service is down: block new starts (current) or kill switch and
      continue. **owner**
- [ ] Moodle mobile app: proctored quizzes are blocked there; students told to use a browser.

## Production setup

- [ ] Dedicated service host (not shared with other production sites), sized from the load test.
- [ ] TLS, firewall: only nginx public; service, Postgres, Redis, object store on localhost.
- [ ] Fresh secrets generated on the host; signing key only in Moodle and the service.
- [ ] Moodle `mode` = live; capture intervals 30 s camera / 60 s screen.
- [ ] Backups: Postgres dump every 5 minutes of WAL or nightly dump plus WAL archive (RPO 5 min);
      object store volume backed up; restore rehearsed.
- [ ] Monitoring: health endpoint polled every minute with alerting; disk and memory alerts.
- [ ] Remove temporary access (e.g. `/etc/sudoers.d/90-claude-temp` on agiledev).
- [ ] `grunt amd` run for `quizaccess_examproctor` before release.
- [ ] nginx `limit_req` on `/examproctor-api/`.

## Pilot (see `docs/pilot-kit.md`)

- [ ] One course, real students who consented, all device types in the matrix.
- [ ] Reviewer sign-off that flags were useful and fair; feedback addressed.

## Go-live day

- [ ] Change freeze from 24 h before; `deploy/deploy.sh status` recorded.
- [ ] Invigilators briefed on the live wall and on the kill switch contact.
- [ ] Exams office has the runbooks and an on-call contact.

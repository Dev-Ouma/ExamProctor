# ExamProctor build plan (after Gate A)

Inputs: `examproctor-spec.md` (v0.3, approved), `docs/implementation-requirements.md`. Each milestone ends with tests shown, docs updated, commit, and a report under 15 lines.

## M1 Foundation (Gate B)
1. Repo layout per spec 13 (`moodle/`, `service/`, `client-sdk/`, `dashboards/`, `staging/`, `docs/`). Own git repo, not the umbrella `~/Dev` repo.
2. `staging/compose.yml`: Moodle 4.5 + PHP 8.3, MariaDB/Postgres for Moodle, FastAPI service, Postgres, Redis, MinIO. `make up` from scratch.
3. Seed script: synthetic courses, quizzes, students, invigilators, reviewers, roles.
4. Plugin skeletons `quizaccess_examproctor`, `local_examproctor`: version, lang, capabilities, settings, install/upgrade, empty privacy provider.
5. CI: phpcs (moodle-cs), PHPUnit, ruff + pytest, eslint + vitest, gitleaks, dependency audit.
Exit: both plugins install on the stack; CI green; owner runs `make up` locally.

## M2 Launch and gate
Launch JWT minting (RS256, 120 s, jti store); `/v1/sessions/exchange`, consent, precheck; signed `session.ready` webhook with nonce/timestamp; access rule blocks start without a ready record; Moodle app block (R1.4); pre-check UI in the SDK.
Tests: token single use and expiry; replayed webhook rejected; forged POST cannot start a proctored attempt.

## M3 Capture and evidence
Exam shell (R3) with same-origin frame and end detection; SDK capture loop, IndexedDB queue, presigned PUT, sha256; events and heartbeat ingest; MinIO SSE, object lock, retention job.
Tests: 60 s network drop survives; out-of-order and duplicate uploads; retention deletes in test; shell survives 20 page navigations with one screen prompt.

## M4 AI pipeline (Gate C)
Face detect / count / match (FACE_MODEL = DeepFace wrapper; underlying model licence verified per weights), head pose, image quality, focus and copy-paste sequence flags, scoring with reasons; evaluation set and bias report by lighting / skin tone / device.

## M5 Review and Moodle integration
Review dashboard; decisions and appeals; per-question flag badges; CSV (cursor) and PDF export; Moodle summary tables; privacy provider export and erase through the service.

## M6 Live invigilation
Live wall over WebSocket and Redis pub/sub; warn / message / pause / terminate with reasons; student notices.

## M7 Simulator and load (Gate D)
Headless candidates with fake media and scripted misbehaviour; ramp to 5,000; security checklist incl. R-01..R-07 regression tests; accessibility checks.

## M8 Pilot and readiness
Pilot kit, go-live checklist, runbooks, kill switch and rollback rehearsal, DPIA sign-off.

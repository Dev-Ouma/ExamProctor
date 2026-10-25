# ExamProctor: Design Spec and Architecture (v0.3, approved at Gate A on 2026-10-25)

Working name: **ExamProctor**. Third-party product names and branding must not appear in code, UI or user-facing docs.
Source requirements: OUK/LTI/PROC/2026/001 (Learning Technologies & Innovations Team, 29 April 2026), plus owner decisions: Moodle integration; automated AI flags + live invigilation + human review; 5,000 concurrent candidates; staging/test subsystem; plug-and-play Moodle plugin model; reverse-engineering of the reference product first, under the vendor's stated permission.

## 1. Status and change log

| Version        | Change                                                                                                                     |
| -------------- | -------------------------------------------------------------------------------------------------------------------------- |
| v0.1           | Initial architecture, AI pipeline, capacity, privacy, build plan                                                           |
| v0.2           | Adds Phase 0 reverse engineering, draft API contract, data model, scoring, NFRs, test strategy, acceptance criteria, risks |
| v0.2.1         | Product renamed to ExamProctor (plugin ids, headers, repo and file names updated)                                          |
| v0.3           | Reconciled with Phase 0 (delta D-01..D-21 approved): exam shell, server-verified gate, policy snapshot per attempt, strict/lenient mode, adaptive capture, new signals, Moodle-app block, async close, optional reference photos, open decisions resolved, sections 3.2 and 3.5 restored |

Sections 7 and 8 remain living drafts; changes go through this change log.

## 2. Goals and non-goals

Goals
1. Proctor Moodle quizzes from inside Moodle with no change to question banks or the gradebook workflow.
2. Cover laptops, Android and iOS (iOS has no screen capture: a platform limit).
3. Sustain **5,000 concurrent candidates** (25x the 200-student peak in the paper).
4. AI assists humans: it raises, ranks and explains flags. **It never fails or penalises a student by itself.**
5. One review surface for instructors and examination officers with exportable evidence (CSV/PDF).
6. Comply with the Kenya Data Protection Act 2019 and OUK records-management rules.
7. A staging/testing subsystem so every change is proven before a live exam.

Non-goals (v1): native iOS app, OS-level lockdown browser, voice biometrics, speech transcription.

## 3. Phase 0: Reverse engineering (first work item)

### 3.1 Purpose
Learn how the reference product integrates with Moodle and what its client does, then make ExamProctor interoperable and at least feature-equivalent, with an independent implementation.

### 3.2 Authorization
Analysis runs under the vendor's signed letter of 20 Oct 2026 (filed in `docs/authorization/`, not in the repo). Scope: analysis for interoperability and independent development only; no copying of vendor code, text, translations, images or design (Option A); no probing of vendor production, no vulnerability hunting in the vendor service, no use of vendor branding; findings stay confidential. Traffic and script analysis only through normal licensed use on OUK staging with synthetic or consenting-tester data.

### 3.3 Inputs (in order of value)
1. Moodle plugin ZIP (PHP, readable source).
2. HAR capture(s) of a full proctored test quiz on OUK's own staging Moodle (pre-checks, exam, submit, staff review).
3. Client script bundle(s) served to the attempt page.
4. Android app APK (if supplied).
5. Public vendor documentation.

### 3.4 Method and tools
- PHP plugin: read directly (structure, hooks, DB, capabilities, events, settings, privacy provider).
- JavaScript bundles, HAR captures, APK: analysed with REA (`rea-agents`) through Claude Code; raw outputs are stored as evidence. Command names are discovered from REA's own help and docs, not assumed.
- Static analysis first; runtime capture only in a sandbox or on OUK's own staging.

### 3.5 Deliverables
Confidential notes in `docs/re/` (00 inventory and authorization, 01 plugin structure, 02 API contract, 03 client behaviour, 04 Moodle integration, 05 Android app when supplied, 06 unknowns and risks, 07 delta vs spec, `evidence/`). The clean-room handoff `docs/implementation-requirements.md` is the only Phase 0 output that the build uses and the only one that is shareable.


### 3.6 Exit criteria (Gate A)
- Authorization file present and summarised.
- All deliverables written; every spec item mapped to keep/change/add/drop with a reason.
- Unknowns listed explicitly; no invented details.
- Spec updated to v0.3 and approved by the owner.

## 4. Architecture overview

```
 Student device (browser / installable web app)       Staff (instructor, invigilator, exam officer)
 ┌───────────────────────────────┐                     ┌──────────────────────────────┐
 │ Moodle quiz attempt page      │                     │ Moodle review page (plugin)   │
 │  + Proctor Client SDK (TS)    │                     │  embeds Review/Live dashboard │
 └──────┬──────────────┬─────────┘                     └───────────────┬──────────────┘
        │ launch token │ snapshots (presigned PUT), events (HTTPS/WS)  │ signed staff token
        ▼              ▼                                               ▼
 ┌──────────────┐   ┌──────────────────────── Proctoring Service ────────────────────────┐
 │ MOODLE       │   │ API (FastAPI) · Realtime gateway (WebSocket + Redis pub/sub)        │
 │ quizaccess_  │◄─►│ Session/Evidence services · Workers (AI pipeline) · Scheduler        │
 │  examproctor │   │ Postgres · Redis · S3-compatible object store (MinIO/S3)             │
 │ local_       │   └──────────────────────────────────────────────────────────────────────┘
 │  examproctor │ ◄── signed webhooks (ready, flag, closed, score) ──┘
 └──────────────┘
```

Two deployable halves:
- **Moodle side (PHP):** thin plugins that gate the quiz, mint launch tokens, keep a small per-attempt summary and render staff UI.
- **Service side (Python + TypeScript):** media intake, AI, live monitoring, evidence storage. Moodle holds no media.

Why the split: Moodle PHP workers and cron should not ingest millions of images; the service scales independently and protects exam performance.

## 5. Components

### 5.1 Moodle plugins
| Plugin                                | Type             | Responsibility                                                                                                                                                                                                                                                  |
| ------------------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quizaccess_examproctor`              | Quiz access rule | Quiz-form policy (enabled, camera, screen, identity check, strict mode, intervals); **blocks attempt start** until Moodle holds a service-signed ready record; snapshots the policy onto the attempt; hands the browser to the exam shell; **denies proctored attempts in the Moodle mobile app** with a link to the browser.                    |
| `local_examproctor`                   | Local plugin     | Site settings (service URL, App ID, key, staging/live mode); launch-token minting; signed webhook endpoint; event observers (attempt started/submitted/abandoned); summary tables; capabilities; **Privacy API provider**; review page embedding the dashboard. |
| `block_examproctor` (later, optional) | Block            | Course-level overview shortcut.                                                                                                                                                                                                                                 |

Capabilities: `local/examproctor:review`, `:invigilate`, `:configure`, `:exportevidence`; mapped to OUK roles in staging first. Every staff endpoint derives the course context from the attempt record itself, never from a caller-supplied course module id.

Policy modes: **strict** (a missing or unsupported required device blocks the start) and **lenient** (continue, record the gap as flag context; default for phones).

Optional identity anchor: institution-loaded reference photos (single upload, bulk ZIP by username, or from profile pictures), validated by a queued task (one face, quality, JPEG, size limit). Live capture at pre-check stays the default. Covered by the DPIA.

### 5.2 Client SDK (TypeScript) and exam shell
- **Exam shell:** after the gate, a persistent same-origin page hosts the SDK and frames the Moodle attempt pages, so camera and screen streams survive page loads with one permission prompt. The shell detects attempt end (submit, timeout, leaving the attempt) and stops capture before moving the top window on. Camera-only sessions may fall back to a per-page SDK.
- Identity step: consent (versioned, English and Swahili), camera/mic permission, reference-face capture and live match, optional 30-second room scan.
- Screen share must be a whole display (`displaySurface = monitor`); window or tab shares are rejected with a re-prompt.
- Background capture: camera snapshots (default 30 s), screen snapshots (default 60 s, desktop only, plus one on each focus loss), adaptive (denser after a flag, within a per-session budget); focus/visibility/fullscreen, copy/cut/paste, context menu, online/offline, resize, question shown, navigation clicks; copy/paste/context-menu/change events carry the question id and option id; aggregated input-rhythm summaries (never typed content).
- Weak-network resilience: small JPEGs (30-60 KB), IndexedDB queue, resumable retries, 10 s heartbeat; connectivity gaps are reported so they are not misread as cheating. Answer autosave remains Moodle's own.
- Device policy comes from the launch token.
- Targets: SDK bundle small enough not to slow the quiz page; CPU overhead low on entry-level Android phones.

### 5.3 Proctoring Service
API (sessions, uploads, events, review, export); realtime gateway (live wall, student notices); workers (AI pipeline); scheduler (retention, legal holds, outbox retries); stores (Postgres, Redis, S3-compatible object store, all encrypted at rest).

### 5.4 Dashboards (React + TypeScript)
- **Live wall:** sessions sorted by risk, status, warn/message/pause/terminate with logged reasons.
- **Review:** timeline, snapshot viewer, flags with evidence, integrity score with plain-language reasons, reviewer decision and notes, appeal handling.
- **Admin:** thresholds, retention, consent text, exports, audit log.

### 5.5 Device matrix
| Device                                   | Camera + face | Screen capture | Notes                                      |
| ---------------------------------------- | ------------- | -------------- | ------------------------------------------ |
| Windows / macOS (Chrome, Edge, Firefox*) | Yes           | Yes            | *Verified per browser in staging           |
| Android (Chrome / installable web app)   | Yes           | No             | Browser limit; native app is a later phase |
| iOS / iPadOS (Safari / Chrome)           | Yes           | No             | Apple platform limit                       |
| Moodle mobile app                        | No            | No             | Proctored quizzes blocked; open in browser |

## 6. Key flows

**Launch:** student opens quiz → access rule checks quiz policy → `local_examproctor` mints a launch JWT → SDK exchanges it for a session → consent and pre-checks → service webhooks `session.ready` → Moodle stores a ready record (user, quiz, session; expires after 10 min unused) → access rule lets `startattempt` proceed only with that record → policy snapshot written to the attempt → exam shell frames the attempt → timer starts. A client-supplied value alone never unlocks an attempt.

**Live:** SDK streams snapshots/events → service stores and enqueues analysis → flags reach the live wall → invigilator may warn/pause; every action is logged and shown to the student.

**Close:** Moodle observes `attempt_submitted`, `attempt_abandoned` and `attempt_becameoverdue` and enqueues a close through its outbox (never blocking the student's submit); the service finalises the session, computes the score and webhooks the summary; Moodle can also pull `GET /v1/attempts/{id}/review` if a webhook is missed; evidence stays in the service until retention expires (or a legal hold applies).

**Trust:** all Moodle ↔ service calls are signed with short expiry and replay protection; students never hold service credentials.

## 7. API contract (DRAFT, to be reconciled with Phase 0)

Common: JSON over HTTPS, `Authorization: Bearer <token>`, `X-Request-Id`, idempotency keys on writes, versioned under `/v1`.

**Launch JWT (Moodle → browser → service), claims:** `iss`, `aud`, `sub` (Moodle user id), `course_id`, `cmid`, `quiz_id`, `attempt_id`, `policy` {camera, screen, mic, room_scan, device_rules}, `iat`, `exp` (≤ 120 s), `jti` (one-time).

Student/SDK endpoints
| Method | Path                                       | Purpose                                                                                          |
| ------ | ------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| POST   | `/v1/sessions/exchange`                    | Trade launch token for session id, session token, policy and upload config                       |
| POST   | `/v1/sessions/{id}/consent`                | Record consent text version and timestamp                                                        |
| POST   | `/v1/sessions/{id}/precheck`               | Submit pre-check results (camera, mic, screen, network, reference face)                          |
| POST   | `/v1/sessions/{id}/uploads/presign`        | Request presigned PUT: kind (camera/screen/room_scan/reference), bytes, sha256, seq, captured_at |
| POST   | `/v1/sessions/{id}/uploads/{key}/complete` | Confirm upload                                                                                   |
| POST   | `/v1/sessions/{id}/events`                 | Batch events (focus, visibility, fullscreen, paste, input summary, connectivity)                 |
| POST   | `/v1/sessions/{id}/heartbeat`              | Liveness and client health                                                                       |
| WS     | `/v1/sessions/{id}/ws`                     | Notices from invigilators (warn, pause, resume, terminate)                                       |
| POST   | `/v1/sessions/{id}/finish`                 | Normal close                                                                                     |

Staff endpoints
| Method   | Path                                   | Purpose                                                   |
| -------- | -------------------------------------- | --------------------------------------------------------- |
| GET / WS | `/v1/live/sessions`, `/v1/live/stream` | Live wall data                                            |
| POST     | `/v1/sessions/{id}/actions`            | warn, message, pause, resume, terminate (reason required) |
| GET      | `/v1/attempts/{id}/review`             | Evidence, flags, score, timeline                          |
| POST     | `/v1/attempts/{id}/decision`           | Reviewer decision and notes                               |
| POST     | `/v1/exports`                          | CSV/PDF export job                                        |
| PUT      | `/v1/admin/exams/{cmid}`               | Register or update a quiz's proctoring policy             |

Service → Moodle webhooks (`/local/examproctor/webhook.php`)
Events: `session.ready`, `flag.raised`, `session.closed`, `score.updated`, `decision.recorded`.
Headers: `X-ExamProctor-Signature` (HMAC-SHA256 of timestamp + nonce + body), `X-ExamProctor-Timestamp`, `X-ExamProctor-Nonce`. Moodle rejects stale timestamps and reused nonces; the service retries from an outbox with backoff.

Error model: `{ "error": { "code", "message", "request_id" } }`; client retry rules documented per endpoint.

## 8. Data model (DRAFT)

Service (Postgres)
| Table             | Key fields                                                                                |
| ----------------- | ----------------------------------------------------------------------------------------- |
| `exams`           | cmid, quiz_id, policy_json, enabled, thresholds_json                                      |
| `sessions`        | id, exam_id, moodle_user_id, attempt_id, device_info, status, started_at, ended_at        |
| `consents`        | session_id, text_version, accepted_at                                                     |
| `reference_faces` | session_id, object_key, embedding_ref, quality                                            |
| `uploads`         | id, session_id, kind, object_key, sha256, bytes, seq, captured_at, analysed_at            |
| `events`          | id, session_id, type, payload_json, client_ts, server_ts                                  |
| `flags`           | id, session_id, type, severity, confidence, start_ts, end_ts, evidence_refs, context_json |
| `scores`          | session_id, integrity_score, band, reasons_json, computed_at, version                     |
| `reviews`         | attempt_id, reviewer_id, decision, notes, appeal_status, decided_at                       |
| `actions`         | id, session_id, actor_id, type, reason, created_at                                        |
| `audit_log`       | id, actor, action, target, ip, ts (append-only)                                           |
| `webhook_outbox`  | id, event, payload, attempts, next_try_at, delivered_at                                   |
| `legal_holds`     | session_id, reason, set_by, set_at, released_at                                           |

Moodle side: `local_examproctor_quiz` (cmid, enabled, policy), `local_examproctor_ready` (userid, quizid, session_id, expires), `local_examproctor_attempt` (attemptid, session_id, policy_snapshot, status, integrity_score, band, flag_count, updated), `local_examproctor_refphoto` (userid unique, fileid, source, validation_status, invalid_reason, updated), `local_examproctor_outbox` (event, payload, attempts, next_try_at, delivered_at).

Object store layout: `{env}/{exam}/{session}/{kind}/{seq}.jpg`; server-side encryption; objects immutable; lifecycle rules enforce retention.

## 9. AI pipeline and scoring

| Signal                    | Method (candidate)                          | Output                                                   |
| ------------------------- | ------------------------------------------- | -------------------------------------------------------- |
| Face absent               | Face detector on camera frames              | `NO_FACE` with duration                                  |
| Wrong person              | Embedding vs reference                      | `IDENTITY_MISMATCH` (confidence)                         |
| Multiple people           | Face/person count                           | `MULTIPLE_FACES`                                         |
| Looking away              | Landmark head pose, sustained only          | `ATTENTION_AWAY`                                         |
| Camera blocked/dark       | Image-quality checks                        | `CAMERA_OBSTRUCTED` (also prompts the student to fix it) |
| Tab/window change         | Browser events + auto screenshot            | `FOCUS_LOSS`                                             |
| Prohibited screen content | Screenshot OCR/classification (desktop)     | `SCREEN_ALERT`                                           |
| Talking                   | Voice-activity detection (no transcription) | `AUDIO_ACTIVITY`                                         |
| Input anomalies           | Per-student baseline vs bursts/inactivity   | `INPUT_ANOMALY`                                          |
| Copy-leave-paste          | Copy on a question → focus loss → return → paste or answer change on that question | `COPY_PASTE_SEQUENCE` (with question id) |
| Extra displays            | Screen capture metadata / display count     | `MULTIPLE_SCREENS`                                       |
| Context menu on question  | Right-click inside a question               | `CONTEXT_MENU_ON_QUESTION`                               |
| Blank capture             | Black/empty frames while capture is "on"    | `BLANK_CAPTURE`                                          |
| Automation                | Input timing/geometry inconsistent with a human | `AUTOMATION_SUSPECTED`                               |

List views show three bands (clear / review / high) derived from the continuous score. Each flag links to its evidence and, when known, its question.

**Integrity score (0-100, higher is better) and risk band:** `score = 100 - Σ(weight_type × severity × confidence × duration_factor)`, clipped to 0-100. Bands (configurable): `clear`, `review`, `high`. The score is a triage aid, **not a probability of cheating**. Every deduction links to specific flags and evidence; weights are per exam and versioned.

**Fairness guardrails**
- Human review is mandatory before any academic-integrity action; no automatic penalties anywhere.
- Flags carry context (lighting, device type, connectivity gaps) so reviewers can discount likely false positives.
- Appeals path and reviewer audit trail built in.
- Accuracy and bias testing across skin tones, lighting and low-end cameras is a release gate for face features.
- Any LLM use is limited to summarising flags for reviewers; it makes no decisions.

**Licensing:** many pretrained face-recognition weights are non-commercial only. Model, dataset and library licences are verified and recorded in `docs/licences.md` before production use (Gate C).

## 10. Capacity and non-functional requirements (5,000 concurrent)

Assumptions (confirmed by load tests): 2-hour exam; camera snapshot every 30 s; 60% of candidates on desktop also send screen snapshots every 30 s; ~50 KB per image; event/heartbeat every 10 s.

| Metric                    | Estimate                                                |
| ------------------------- | ------------------------------------------------------- |
| Camera uploads            | ~167 /s                                                 |
| Screen uploads            | ~100 /s                                                 |
| Heartbeats/events         | ~500 /s                                                 |
| Total requests            | ~800 /s; media bypasses the API via presigned PUTs      |
| Images per full sitting   | ~1.9M (≈267/s over 7,200 s)                             |
| Evidence per full sitting | ≈100 GB at ~50 KB per image                             |
| Student bandwidth         | ≈13-25 kbps average                                     |
| AI throughput             | ≈270 images/s sustained; worker sizing set by benchmark |

Targets to validate in M7 (initial proposals):
| Area                                     | Target                                                                                                                           |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| API latency under 5,000 sessions         | p95 < 300 ms                                                                                                                     |
| Upload success within retries            | ≥ 99%                                                                                                                            |
| Capture → flag visible on live wall      | p95 < 15 s                                                                                                                       |
| Added load time on the quiz attempt page | negligible; measured against a no-proctoring baseline                                                                            |
| Availability during exam windows         | ≥ 99.9%                                                                                                                          |
| Evidence integrity                       | sha256 verified end to end; objects immutable                                                                                    |
| Recovery                                 | RPO ≤ 5 min for metadata; documented RTO and rehearsed restore                                                                   |
| Degradation                              | If the service is down, policy decides: pause attempts or continue with a logged gap (owner decision); never lose Moodle answers |

Scaling levers: more API/worker replicas; adaptive sampling (denser on suspicion, sparser when calm); analysis may lag seconds without affecting the student.

## 11. Security and privacy (Kenya DPA 2019)

- Explicit, recorded consent before capture; plain-language notice in English and Swahili.
- **DPIA** completed before go-live; ODPC registration and processing records are OUK ICT/legal actions (owner: `DPIA_OWNER`).
- Face images and embeddings are sensitive personal data: encrypted in transit and at rest, role-restricted, every access logged.
- Data residency per the hosting decision (section 16).
- Retention default: 90 days after results are finalised; longer only under a recorded legal hold.
- Moodle Privacy API provider for subject access and erasure.
- Secure SDLC: dependency and secret scanning in CI, pen-test before go-live, secrets in a vault, no credentials in the client, least-privilege service accounts, signed releases of plugins.
- Reference-product analysis material (`docs/re/`), the authorization letter and vendor files are confidential, git-ignored, kept out of the shipped product and out of public repos.
- No data leaves OUK on install or upgrade; any telemetry is opt-in by an admin. Debug logging off in production.
- Staff report access is checked against the attempt's own course context.

## 12. Staging, test data and testing subsystem

- **Environment:** containerised stack (Moodle, its DB, the service, Postgres, Redis, MinIO) started with one command; **staging** and **live** configs selectable in plugin settings, with a visible staging banner.
- **Synthetic data only:** seed scripts create fake courses, quizzes, users and roles that mirror OUK's structure; synthetic faces/fake camera feeds for tests. No real student data or exam content in dev or CI.
- **Candidate simulator:** headless browsers with fake camera/screen feeds drive complete exams, including scripted misbehaviour (tab switching, second face, no face, camera blocked, disconnects).
- **Load tests:** ramp to 5,000 simulated candidates with pass/fail thresholds from section 10.
- **Automated suites:** unit, integration, plugin install/upgrade tests on the Moodle versions OUK runs, API contract tests, accessibility checks, security scans, AI accuracy/bias evaluation sets.
- **Chaos checks:** service outage mid-exam, network drops, clock skew, duplicate/out-of-order uploads, webhook replay.
- **Pilot gate:** real volunteers on Android, iOS and laptops before production enablement.
- **Rollout controls:** per-course enablement flag, global kill switch, independent rollback of plugins and service.

## 13. Stack, repo layout and operations

- Moodle plugins: PHP to Moodle coding standards; PHPUnit + Behat.
- Service: Python 3.12, FastAPI, Postgres, Redis, S3-compatible storage, queue-based workers.
- SDK and dashboards: TypeScript, React, Vite; Playwright end-to-end.
- Packaging: Docker Compose (dev/staging); Kubernetes-ready manifests for production.
- Observability: structured logs, metrics (request rate, upload success, queue lag, flag latency), traces, alerting on exam-window SLOs; dashboards for ICT on exam days.
- Runbooks: exam-day checklist, incident response, rollback, retention/legal-hold procedures.

```
examproctor/
  moodle/quizaccess_examproctor/
  moodle/local_examproctor/
  service/            # API, realtime gateway, workers, scheduler, migrations
  client-sdk/         # attempt-page SDK
  dashboards/         # live wall, review, admin
  staging/            # compose stack, seed data, simulator, load tests
  docs/
    authorization/    # vendor written permission
    re/               # Phase 0 reverse-engineering notes and evidence (confidential)
    licences.md
    dpia/  runbooks/  privacy-notice/
  re-inputs/          # supplied plugin ZIP, HAR, APK (not committed to shared repos)
```

## 14. Build plan and acceptance criteria

| Milestone | Deliverable                                                             | Acceptance criteria                                                                                                                                                                |
| --------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **P0**    | Reverse engineering (section 3)                                         | Gate A passed; spec v0.3 approved                                                                                                                                                  |
| **M1**    | Repo, staging stack, seed data, plugin skeletons, CI                    | Stack starts from scratch with one command; both plugins install and appear in Moodle admin; CI green (lint, unit, secret/dependency scan); Gate B                                 |
| **M2**    | Launch/token flow, session service, consent, pre-checks, reference face | Quiz cannot start until pre-checks pass; launch token is single-use and expires; signed `session.ready` unlocks the attempt; consent recorded                                      |
| **M3**    | Background capture, resilient uploads, evidence store, event ingest     | Snapshots/events arrive during an exam; uploads survive a 60 s network drop; sha256 verified; encrypted at rest; retention job deletes expired evidence in test                    |
| **M4**    | AI pipeline v1 and scoring                                              | Each flag type triggers on scripted cases; evaluation report with precision/recall by lighting/skin-tone/device groups; scores traceable to flags; Gate C (licences + bias report) |
| **M5**    | Review dashboard, Moodle integration, exports, privacy provider         | Reviewer can clear/escalate with notes and appeal status; CSV/PDF export correct; Moodle shows summary; subject-access export and erasure work                                     |
| **M6**    | Live invigilation wall and actions                                      | Flag appears on wall within the latency target; warn/pause/terminate reach the student and are logged with reasons                                                                 |
| **M7**    | Simulator, 5,000-user load test, security review                        | Load test meets section 10 targets or documents gaps with fixes; security checklist and accessibility checks pass; Gate D                                                          |
| **M8**    | Pilot and go-live readiness                                             | Pilot completed on all device types with feedback addressed; rollback and kill-switch rehearsed; runbooks and DPIA signed off                                                      |

## 15. Risks

| Risk                                        | Mitigation                                                                        |
| ------------------------------------------- | --------------------------------------------------------------------------------- |
| Vendor permission narrower than assumed     | Written permission reviewed at Gate 0; clean-room default; legal review for reuse |
| Server-side behaviour invisible to analysis | Record as unknowns; design from requirements; verify by tests                     |
| Face model licence or bias problems         | Licence check and bias evaluation gate before use                                 |
| False positives harming students            | Human-in-the-loop, context on flags, appeals, conservative thresholds             |
| Poor connectivity on mobile                 | Small uploads, queues, resumable retries, gap-aware flagging                      |
| Browser/OS changes break capture            | Per-browser tests in staging, feature detection, fallback messaging               |
| Privacy non-compliance                      | Consent, DPIA, minimisation, retention, audit, residency decision                 |
| Load estimate wrong                         | Early benchmarks (M3/M4), load test (M7), adaptive sampling                       |
| Moodle upgrade breaks plugins               | Version-matrix install/upgrade tests; follow Moodle APIs only                     |
| Service outage during exam                  | Defined degradation policy, kill switch, runbooks, HA deployment                  |

## 16. Decisions

| # | Topic | Decision (2026-10-25) |
| - | ----- | --------------------- |
| 1 | Moodle / PHP | Moodle 4.5+, PHP 8.3 |
| 2 | Hosting | KENET (Kenyan research network datacentre); data stays in Kenya |
| 3 | Retention | 90 days after results are finalised; longer only under legal hold |
| 4 | Face model | DeepFace wrapper; each underlying model's weight licence verified at Gate C before production |
| 5 | Mobile | Web-only v1 (installable web app); native Android later |
| 6 | DPIA owner | OUK (ICT/legal); appeals-policy signatory still to be named |
| 7 | Degradation | **Open.** Proposal: continue the exam with a logged gap; never pause Moodle answers |
| 8 | Vendor permission | Signed 20 Oct 2026; Option A, analysis only |
| 9 | LTI 1.3 | Later milestone (after M8); plugin-first for v1 |
| 10 | Repo | `github.com/Dev-Ouma/ExamProctor` (public); confidential paths git-ignored |

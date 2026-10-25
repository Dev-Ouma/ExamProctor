# ExamProctor: Master Prompt for Claude Code (with REA)

How to use: create an empty project folder (for example `~/dev/examproctor`), put this file and `examproctor-spec.md` in it, make sure REA is registered with Claude Code (`npx --yes rea-agents@latest setup`, restart Claude Code, check with `/mcp` and `rea doctor --json`), start `claude` inside the folder, then paste everything under the line below.

Fill the PROJECT VARIABLES block first. Anything left as TBD, the agent must ask about at the relevant gate instead of guessing.

---

## PROJECT VARIABLES (fill in)

```
MOODLE_VERSION        = 4.5+        # e.g. the exact version OUK runs
PHP_VERSION           = 8.3.36
HOSTING               = kenet        # on-prem | Kenyan datacentre | cloud region
RETENTION_DAYS        = 90         # after results are finalised
MOBILE_V1             = web-only   # web-only | native-android
FACE_MODEL            = deepface
DPIA_OWNER            = ouk
```

---

## ROLE

You are the lead engineer building **ExamProctor**, an online-exam proctoring system for the Open University of Kenya (OUK), integrated with Moodle, designed for **5,000 concurrent candidates**. The full design is in `examproctor-spec.md`; read it completely before doing anything. The project owner works at OUK and has stated that the vendor of the reference product permits analysis of it. You will start with a reverse-engineering phase (Phase 0), then build in milestones M1-M8.



##
## PHASE 0: REVERSE ENGINEERING (start here)

Goal: understand how the reference product integrates with Moodle and what the browser/client does, so that our design is interoperable and at least feature-equivalent, then reconcile the findings with the spec.

### 0.1 Inventory the inputs
List what is in `RE_INPUTS_DIR` and what is missing. Expected inputs, in order of value:
1. **Moodle plugin ZIP** (PHP; readable source): structure, `version.php`, `db/` (install.xml, access.php capabilities, events, services), `classes/`, `lang/`, settings, quiz integration, privacy provider, JS/AMD modules.
2. **HAR capture(s)** from the owner's own staging Moodle running a proctored test quiz (a full run: pre-checks, a few minutes of exam, submit, staff review). REA supports saved network captures (HAR).
3. **Client script bundle(s)** served to the attempt page (from the HAR or the plugin), analysed with REA's JavaScript analysis.
4. **Android app APK**, if the owner supplies one (REA supports APK analysis; it needs a JDK and headless JADX).
5. **Vendor public documentation** (read-only reference).
If input 1 is missing, tell the owner what to supply; continue with whatever else exists.

### 0.2 Analyse, one input at a time
For each input write notes into `docs/re/` as below. Use REA's tools for the JavaScript bundles, HAR captures and APK; read PHP directly.

| File                               | Content                                                                                                                                                                                                                              |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/re/01-plugin-structure.md`   | Plugin type(s), Moodle API hooks used, capabilities, DB tables/fields, events observed, scheduled tasks, settings, renamed/forced quiz settings, privacy provider, upgrade steps.                                                    |
| `docs/re/02-api-contract.md`       | Every observed endpoint: method, path, auth mechanism, request/response shape (field names, types, example with redacted values), status codes, retry/ordering behaviour, rate limits if visible.                                    |
| `docs/re/03-client-behavior.md`    | What the client captures and when: camera/screen intervals, image format/size/quality, upload mechanism, event types, heartbeat, permissions flow, consent screen, room scan, failure/offline handling, device-specific differences. |
| `docs/re/04-moodle-integration.md` | End-to-end launch and close flows as sequence descriptions: how a quiz is gated, how a session starts, how results return to Moodle, how staff open the review UI.                                                                   |
| `docs/re/05-android-app.md`        | (If APK provided) screens, permissions, how it differs from the web flow, how it hands off to Moodle.                                                                                                                                |
| `docs/re/06-unknowns-and-risks.md` | What could not be determined, what needs vendor documentation, what is server-side and invisible to us, licensing observations.                                                                                                      |
| `docs/re/evidence/`                | Raw REA outputs and redacted HAR excerpts referenced by the notes.                                                                                                                                                                   |

### 0.3 Reconcile with the spec
Produce `docs/re/07-delta-vs-spec.md`: a table of (spec item | finding | action: keep / change / add / drop | reason). Then update `examproctor-spec.md` to v0.3 with the agreed changes, and bump the change log. Keep our own naming (`quizaccess_examproctor`, `local_examproctor`, `ExamProctor`).

### 0.4 Clean-room handoff
Write `docs/implementation-requirements.md`: behavioural requirements and interface contracts for ExamProctor expressed in our own words, with no vendor code and no vendor strings. This document, not the raw vendor material, is what the implementation milestones are built from.

**GATE A:** present a short summary of findings, the delta table and the unknowns. Wait for the owner's approval before starting M1.

## PHASES 1-8: BUILD (milestones from the spec, section 14)

For each milestone: restate its acceptance criteria from the spec, implement, test, document, commit, then report in under 15 lines (what changed, how it was verified, open issues). Stop at each GATE.

- **M1 Foundation:** monorepo layout from the spec; one-command staging stack (Moodle + DB + service + Postgres + Redis + MinIO); seed script (synthetic courses, quizzes, users, roles); plugin skeletons that install and show in Moodle admin; CI (lint, unit tests, security scan). **GATE B:** owner confirms the stack runs on their machine.
- **M2 Launch and pre-checks:** launch JWT minting, session API, consent, camera/mic permission flow, reference-face capture, "ready" callback that unlocks the attempt.
- **M3 Capture and evidence:** client SDK background capture, IndexedDB queue, presigned uploads, event/heartbeat ingest, evidence storage with encryption and retention jobs.
- **M4 AI pipeline v1:** face present/absent/multiple, identity match, focus flags, image-quality flags, scoring with traceable reasons; evaluation set and metrics. **GATE C:** FACE_MODEL licence verified and bias/accuracy report reviewed by the owner.
- **M5 Review and Moodle integration:** review dashboard, reviewer decisions and appeals notes, CSV/PDF export, Moodle summary tables, privacy provider (export/erase).
- **M6 Live invigilation:** live wall, warn/message/pause/terminate with reason logging, student-side notices.
- **M7 Simulator and load:** candidate simulator (headless browsers with fake media, scripted misbehaviour), load test to 5,000, security review checklist, accessibility checks. **GATE D:** owner reviews load and security results.
- **M8 Pilot and readiness:** pilot kit (volunteer instructions, feedback form), go-live checklist, runbooks, rollback and kill-switch rehearsal.

## DEFINITION OF DONE (every milestone)
- Acceptance criteria in the spec pass, with test output shown.
- No secrets or real personal data committed; dependency licences recorded in `docs/licences.md`.
- Docs updated (`docs/`), spec change log updated if the design changed.
- Staging stack still starts from scratch with one command.

## HOW TO REPORT
Be concise and factual. Lead with what is done and verified; list what is not done and why; list decisions needed from the owner. Do not recap every step.

## FIRST ACTIONS (do these now, in order)
1. Read `examproctor-spec.md` fully.
2. Run the Authorization Gate (section 0).
3. Run `rea doctor --json` and report whether REA and any analysis providers are ready.
4. Inventory `RE_INPUTS_DIR` and report what is present and missing.
5. Begin Phase 0.2 with whatever inputs exist, starting with the plugin ZIP if present.

# 08 Implementation requirements (clean-room handoff)

Written in our own words. No third-party code, identifiers or strings. Build milestones M1-M8 from this file and the spec, not from the reference material. Status: approved at Gate A, 2026-10-25. Pairs with spec v0.3.

## R1 Quiz policy (Moodle, `quizaccess_examproctor`)

1. Quiz form section "ExamProctor" with: enabled; camera; screen; identity check; strict mode; capture intervals (advanced).
2. Rules: strict mode needs camera or screen; identity check needs camera.
3. One policy row per quiz. On attempt start, copy the policy into the attempt row. In-progress attempts use the copy.
4. Rule inactive when the plugin is not configured. When the request comes from the Moodle mobile app and the quiz is proctored: deny the attempt with a message and a browser link.

## R2 Launch gate

1. Pre-check page order: notice and consent → camera → screen (desktop) → identity → preview and final confirmation.
2. Consent text has a version id. English and Swahili.
3. Moodle mints a launch token (claims per spec 7, ≤ 120 s, single use).
4. The attempt may start only when Moodle holds a valid, unexpired, service-signed `ready` record for (user, quiz, session). A client value alone never unlocks the attempt.
5. Strict mode: missing or unsupported device blocks start. Lenient mode: continue, record the gap as context.
6. Screen share must be a whole display. Otherwise re-prompt.

## R3 Exam shell (capture continuity)

1. After the gate, the browser loads a persistent shell page (same origin as Moodle). The shell hosts the SDK and frames the Moodle attempt pages.
2. Streams persist across attempt page loads. The shell detects attempt end (submit, summary exit, timeout redirect) and stops capture, then moves the top window to the destination.
3. Camera-only sessions may run without the shell (per-page SDK), with a fresh camera prompt allowed.
4. The shell never reads answer content.

## R4 Capture

1. Camera and screen snapshots with policy intervals. Defaults 30 s and 60 s. Adaptive: shorter after a flag, up to a per-session budget.
2. Extra screen capture on focus loss.
3. Events: focus/blur, visibility, fullscreen, copy/cut/paste, context menu, online/offline, resize, question shown, nav clicks, aggregated input rhythm. Copy/paste/context-menu/change events carry the question id and option id. Never typed text.
4. Uploads per spec 7 (presigned, sha256, sequence numbers, IndexedDB queue, retries). Heartbeat 10 s. Clock offset measured at start.

## R5 Signals (adds to spec 9)

`COPY_PASTE_SEQUENCE`, `MULTIPLE_SCREENS`, `CONTEXT_MENU_ON_QUESTION`, `BLANK_CAPTURE`, `AUTOMATION_SUSPECTED`. Each flag links to evidence and, when known, the question.

## R6 Close

Observe attempt submitted, abandoned and overdue. Finalise asynchronously through the outbox. Never block the student's submit on the service.

## R7 Review

1. List view: score, band (clear / review / high), status; filter and sort.
2. Attempt view: timeline, images, flags, per-question flag badges, reviewer decision, notes, appeal.
3. CSV export paged by cursor, with per-slot marks; PDF export.
4. Every staff endpoint derives the course context from the attempt record and checks capability there.

## R8 Identity anchor (optional, behind a setting)

Institution may load reference photos (single, bulk ZIP by username, or from profile pictures). Each photo is validated (one face, quality, JPEG, size limit) by a queued task. Live capture remains default. Covered by the DPIA.

## R9 Trust and privacy

No data leaves the institution on install. Signed service calls (spec 7). Debug logging off in production. Privacy provider covers policy, attempt rows, reference photos and the service-held evidence (export and erase via service API).

# Feature triage: "OUK Smart Proctoring & Academic Integrity Platform" wishlist

Source: OUK concept note (kept in `docs/background/`, not in the repo). Triage date 2026-10-25.
Rule used: keep what fits the spec's principles (AI assists, humans decide; Kenya DPA 2019; web-first; 5,000 concurrent), defer what needs a later platform, refuse what a browser cannot do honestly or what would harm students without human review.

## Already in v1 (no change)

Face presence / absence / multiple faces, identity match, tab and focus tracking, copy-paste events, risk score with reasons, integrity flags, behaviour timeline, live wall, warn / message / pause / terminate, Moodle plugin launch, quiz-level settings, gradebook untouched, token auth, role-based capabilities, device matrix incl. the iOS screen limit, consent, audit log, retention, kill switch, load test to 5,000, staging/simulator, English + Swahili.

## Added to v1 (cheap, fits the design)

| Wishlist item | Where | Note |
| --- | --- | --- |
| Network quality assessment, device health check, readiness wizard | M2 pre-check (extend) / M3 | Upload test file, measure RTT and throughput; warn, never block unless strict |
| Multi-monitor detection | M3 / M4 | `screen.isExtended` (Window Management API) where available; flag `MULTIPLE_SCREENS` |
| Clipboard restriction (optional) | M3 | Per-quiz switch to block paste into answers; OUK already does this in-house |
| Live chat with candidates, incident escalation workflow | M6 | Chat = invigilator message thread; escalation = review status |
| Evidence timeline playback | M5 | Image sequence player (we store snapshots, not video) |
| AI incident summaries for reviewers | M5 | Allowed by spec 9 only as summaries; no decisions |
| Smart alert suppression / prioritisation | M6 | Sort and group flags on the live wall |
| Exam analytics: completion, flag trends, system health | M5 / M7 | Reports and Grafana-style ops dashboards |
| Audit investigator / read-only compliance roles | M5 | Extra capabilities on the existing model |
| Automatic session recovery, emergency reconnect | M3 | IndexedDB queue + exam shell resume |
| Virtual machine / automation hints | M4 | `AUTOMATION_SUSPECTED` signals only, low weight |

## Deferred (v2+, needs a separate decision)

LTI 1.3 (already decided: after M8); native Android app with push notifications and biometrics; liveness detection and deepfake analysis (needs model licence and bias study); student ID / national ID document checks (needs DPIA and a lawful basis); department-level scheduling and exam management outside Moodle (Moodle already does quiz timing and groups); faculty-level multi-tenancy; executive heat-maps; audio anomaly and background voice detection (spec non-goal for v1, consent and false-positive risk); video recording (bandwidth and storage cost vs snapshots).

## Not adopted (with reason)

| Item | Reason |
| --- | --- |
| Screenshot prevention, developer-tools restriction, background process / unauthorized application detection, browser lockdown | Browsers do not allow this. Only a lockdown client (SEB) can; OUK keeps SEB for supervised sittings. Claiming it in a web product would be false. |
| Eye-gaze tracking as its own flag | Webcam gaze estimation is unreliable on low-end cameras and penalises disability and lighting differences. Head-pose "sustained attention away" stays as context only. |
| Predictive cheating analysis, candidate trust index across exams, risk forecasting | Profiles students before they act; conflicts with fairness guardrails and DPA purpose limitation. |
| Automated disciplinary workflow | Spec principle: no automatic penalties; humans decide. Escalation workflow (above) covers the need. |
| Geo-location validation, IP intelligence, VPN / proxy detection, device fingerprinting | High privacy cost, weak evidence, penalises shared and mobile networks common in Kenya. Revisit only with a DPIA. |
| Secondary device detection | Not detectable from a browser; a camera view of the desk is the honest substitute (optional room scan). |
| Blockchain certificates, AR/VR exams, AI oral exams, SCORM proctoring | Outside the proctoring scope. |

## Product name

Wishlist suggests "OUK Smart Proctor", "OUK ExamShield", "OUK SecureExam". The working name stays **ExamProctor** in code; a display name can be set later in the plugin language strings without code changes.

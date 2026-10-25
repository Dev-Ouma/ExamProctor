# Data Protection Impact Assessment: draft for the DPO

Status: **draft, not signed**. Prepared from the system as built (2026-10-25) under the Kenya Data
Protection Act 2019 and its regulations. The DPO completes the risk ratings and signs.

## 1. Processing

| Item | Description |
| --- | --- |
| Purpose | Support academic integrity in online assessments by giving invigilators and reviewers evidence; humans make every decision. |
| Data subjects | Students sitting proctored quizzes; staff using the reports (names, actions). |
| Data | Moodle user id; camera snapshots (face, surroundings); whole-screen snapshots on computers; page events (focus, copy/paste, question shown; never typed content); device check results; face template derived from the admission photo or a live reference frame; flags, score, reviewer decisions, invigilator actions. |
| Special category | Biometric data (face templates) used for identity verification. |
| Lawful basis | To be confirmed by the DPO: performance of a public task (assessment) and explicit consent for biometric processing, with a non-biometric alternative. |
| Consent | Versioned consent text shown before every proctored attempt (English and Swahili); attempts cannot start without it. |
| Recipients | OUK staff with the review, invigilate or export capability for that quiz only. No third parties; no external AI service. |
| Location | OUK-controlled servers in Kenya. |
| Retention | Images deleted 90 days after the session ends unless on legal hold; flags, scores and decisions kept with the assessment record per the records schedule (DPO to set). |

## 2. Necessity and proportionality

- Snapshots, not video or audio (no microphone processing).
- Screen capture only on computers and only for quizzes that require it.
- AI only raises flags with reasons and confidence; no automatic penalties.
- Face templates are never shown to staff or exported.
- Students see themselves and the recording indicator at all times.

## 3. Risks and controls (DPO to rate likelihood and severity)

| Risk | Controls in place | Residual (DPO) |
| --- | --- | --- |
| Unfair flags (skin tone, lighting, cheap cameras, disability) | Flags carry context; human review mandatory; Gate C bias evaluation on OUK photos before production; appeals | |
| Over-collection from homes (family, documents on screen) | Snapshots at intervals; whole screen only on computers; staff access per quiz; audit log of every view | |
| Unauthorised access | Moodle capabilities; one-hour staff tokens per quiz; signed service calls; expiring image links; security checklist and DAST | |
| Function creep (profiling across exams) | No cross-exam risk scores; no predictive models (feature triage) | |
| Data subject rights | Moodle privacy export and erasure include service data; legal hold documented | |
| Breach | Encrypted object store volumes; secrets on host only; audit log; incident runbook | |
| Service failure affects grades | Answers saved by Moodle, never by the service; kill switch | |

## 4. Open items before sign-off

- Lawful basis wording and the non-biometric alternative for students who refuse face matching.
- Gate C bias report results.
- Records schedule for flags and decisions.
- Notice in the student privacy statement and course pages.

Signed (DPO): ____________________  Date: __________

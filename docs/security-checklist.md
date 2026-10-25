# Security checklist (M7, Gate D)

Status on 2026-10-25. Each risk from `docs/re/06-unknowns-and-risks.md` maps to the control that
fixes it and to the tests that keep it fixed. `security/test_checklist.py` holds static guards that
fail if a fix is removed; behaviour is tested where it lives.

Run the guards: `cd service && uv run --frozen pytest ../security -q`.

| Risk | Control | Tests |
| --- | --- | --- |
| R-01 Gate trusted a client checkbox | Attempt start needs a service-signed `session.ready` record, single use, 10 min expiry; the service decides readiness from its own pre-check evaluation | `rule_test::test_start_needs_a_signed_ready_record`, `gate_test::test_ready_record_expires_and_is_single_use`, `staging/seed/e2e_gate.php` (forged webhook rejected), checklist R-01 |
| R-02 Rule skipped in the Moodle app | Proctored quizzes are blocked in the app with a link to the browser | checklist R-02 |
| R-03 Cross-course staff access | Moodle resolves the quiz from the checked course module and mints a staff token for that quiz only; the service checks every session against the token's quiz and course and answers 404 otherwise | `test_review::test_other_quiz_session_looks_missing`, `test_review::test_list_is_scoped_to_the_token_quiz`, `test_live::test_live_wall_needs_invigilate`, checklist R-03 |
| R-04 Install phone-home | No outbound HTTP except signed calls to the configured service | checklist R-04 |
| R-05 Unsigned bearer token, no replay protection | HMAC-SHA256 over timestamp, nonce and body for webhooks; Moodle-to-service calls sign method, path, **query string** and body hash; nonces stored; outbox retries with backoff | `gate_test::test_stale_or_tampered_webhooks_are_rejected`, `test_privacy::test_query_string_is_part_of_the_signature`, `test_refphotos`, checklist R-05 |
| R-06 Slow vendor call inside submit | No service call in the submit path; closing is asynchronous (outbox, webhooks) | checklist R-06 |
| R-07 Debug on in production | No console output or debug switches in the SDK source or bundle | checklist R-07 |

Additional controls checked in this milestone:

- Staff WebSocket: the token is sent as the first message, never in a URL (URLs reach logs).
- Evidence links are presigned and expire after 10 minutes; face embeddings never leave the
  service in review or privacy exports.
- Every evidence view, decision, export, privacy request and live action is in the append-only
  `audit_log`.
- Schema changes take a Postgres advisory lock, so replicas starting together cannot corrupt the
  catalogue (found by the M7 load test).

Open items (owner decision or later milestone):

- DAST scan (StackHawk) needs an account and the `hawk` CLI on a workstation.
- `amd/build/badges.min.js` is hand-written; run `grunt amd` before production.
- Rate limiting at the edge (nginx `limit_req`) for `/examproctor-api/` is not configured yet.

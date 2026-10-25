"""Security checklist regression tests (M7, Gate D): R-01..R-07 from docs/re/06-unknowns-and-risks.md.

Behaviour is tested where it lives (service tests, Moodle PHPUnit, browser e2e); this file adds the
static guards that keep a fixed risk from quietly coming back, and checks the behavioural tests
still exist. Run from the repo root:

    cd service && uv run --frozen pytest ../security -q
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOODLE = ROOT / "moodle"
SDK = ROOT / "client-sdk" / "src"


def php_files() -> list[Path]:
    return [p for p in MOODLE.rglob("*.php") if "/tests/" not in str(p)]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def has_test(path: str, name: str) -> bool:
    return name in read(ROOT / path)


def test_r01_attempt_needs_a_server_signed_ready_record():
    rule = read(MOODLE / "quizaccess_examproctor" / "rule.php")
    assert "gate::find_ready" in rule or "find_ready" in rule
    assert has_test("moodle/quizaccess_examproctor/tests/rule_test.php", "test_start_needs_a_signed_ready_record")
    assert has_test("moodle/local_examproctor/tests/gate_test.php", "test_ready_record_expires_and_is_single_use")
    # The service only reports ready after its own pre-check evaluation, never on a client flag alone.
    api = read(ROOT / "service" / "examproctor_service" / "api.py")
    assert "reasons = evaluate(session.policy, body)" in api


def test_r02_mobile_app_is_blocked_not_skipped():
    rule = read(MOODLE / "quizaccess_examproctor" / "rule.php")
    body = rule[rule.index("public function prevent_access") :]
    body = body[: body.index("\n    }\n")]
    assert "mobileappblocked" in body
    # make() must not return null for the mobile app; skipping would be a bypass.
    make = rule[rule.index("public static function make") :]
    make = make[: make.index("\n    }\n")]
    assert "WS_SERVER" not in make and "mobile" not in make.lower()


def test_r03_staff_access_is_scoped_by_the_record_not_the_caller():
    review = read(ROOT / "service" / "examproctor_service" / "review.py")
    assert "session.quiz_id != staff.quiz_id or session.course_id != staff.course_id" in review
    assert has_test("service/tests/test_review.py", "test_other_quiz_session_looks_missing")
    report = read(MOODLE / "local_examproctor" / "report.php")
    # The quiz comes from the course module Moodle resolved and checked, never from a request param.
    assert "get_course_and_cm_from_cmid($cmid, 'quiz')" in report
    assert "optional_param('quizid'" not in report and "required_param('quizid'" not in report


def test_r04_no_phone_home():
    allowed = {"service_client.php"}
    offenders = []
    for path in php_files():
        text = read(path)
        if path.name in allowed:
            continue
        if re.search(r"new \\?curl\(|curl_init\(|file_get_contents\(['\"]https?://|download_file_content\(", text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"outbound HTTP outside service_client: {offenders}"
    install = MOODLE / "local_examproctor" / "db" / "install.php"
    if install.exists():
        assert "service_client" not in read(install)


def test_r05_signed_requests_with_replay_protection():
    verifier = read(MOODLE / "local_examproctor" / "classes" / "local" / "webhook_verifier.php")
    assert "hash_equals" in verifier and "nonce" in verifier.lower() and "WEBHOOK_MAX_SKEW" in verifier
    assert has_test("moodle/local_examproctor/tests/gate_test.php", "test_stale_or_tampered_webhooks_are_rejected")
    refphotos = read(ROOT / "service" / "examproctor_service" / "refphotos.py")
    assert "hmac.compare_digest" in refphotos and "request.url.query" in refphotos
    webhooks = read(ROOT / "service" / "examproctor_service" / "webhooks.py")
    assert "outbox" in webhooks.lower() or "mark_failed" in webhooks


def test_r06_nothing_slow_in_the_student_submit_path():
    events = read(MOODLE / "local_examproctor" / "db" / "events.php")
    assert "attempt_submitted" not in events or "service_client" not in read(
        MOODLE / "local_examproctor" / "classes" / "observer.php"
    )
    observer = read(MOODLE / "local_examproctor" / "classes" / "observer.php")
    assert "service_client" not in observer and "curl" not in observer


def test_r07_no_debug_output_in_the_sdk():
    offenders = [
        f"{p.name}:{i + 1}"
        for p in SDK.rglob("*.ts")
        for i, line in enumerate(read(p).splitlines())
        if re.search(r"console\.(log|debug|info)|debugger;|debug:\s*true", line)
    ]
    assert offenders == []
    bundle = read(MOODLE / "quizaccess_examproctor" / "amd" / "build" / "sdk.min.js")
    assert "console.log" not in bundle and "debugger" not in bundle


def test_secrets_never_in_urls_or_logs():
    live = read(ROOT / "service" / "examproctor_service" / "live.py")
    assert "receive_text" in live  # staff token arrives as the first WebSocket message
    api_ts = read(ROOT / "dashboards" / "src" / "api.ts")
    assert "ws.send(this.token)" in api_ts and "?token=" not in api_ts

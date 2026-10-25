<?php
// M2 end-to-end check of the launch gate against the running staging stack.
// Moodle mints a launch token -> service exchange, consent, pre-check -> signed session.ready webhook
// -> Moodle ready record -> attempt start consumes it and freezes the policy. Plus negative cases.
// Run: make e2e-gate. Uses synthetic user epstudent01. Exits 1 on the first failure.

define('CLI_SCRIPT', true);
require('/var/www/html/config.php');
require_once($CFG->dirroot . '/mod/quiz/locallib.php');
require_once($CFG->dirroot . '/mod/quiz/accessrule/examproctor/rule.php');

use local_examproctor\local\gate;
use local_examproctor\local\launch_token;
use mod_quiz\quiz_settings;

$service = getenv('EXAMPROCTOR_INTERNAL_URL');

function check(bool $ok, string $what): void {
    mtrace(($ok ? 'PASS ' : 'FAIL ') . $what);
    if (!$ok) {
        exit(1);
    }
}

function call(string $method, string $url, array|string|null $body = null, array $headers = []): array {
    // Raw cURL: Moodle's curl class blocks private Docker addresses by design.
    $ch = curl_init($url);
    $headers[] = 'Content-Type: application/json';
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST => $method,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_POSTFIELDS => $body === null ? null : (is_string($body) ? $body : json_encode($body)),
    ]);
    $raw = curl_exec($ch);
    $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return [$status, json_decode((string) $raw, true)];
}

$student = $DB->get_record('user', ['username' => 'epstudent01'], '*', MUST_EXIST);
$course = $DB->get_record('course', ['shortname' => 'EP-STAGING-101'], '*', MUST_EXIST);
$quizrecord = $DB->get_record('quiz', ['course' => $course->id, 'name' => 'Proctored practice quiz'], '*', MUST_EXIST);
\core\session\manager::set_user($student);

// Clean slate for this user so the script can be re-run.
$DB->delete_records('local_examproctor_ready', ['userid' => $student->id, 'quizid' => $quizrecord->id]);
foreach ($DB->get_records('quiz_attempts', ['userid' => $student->id, 'quiz' => $quizrecord->id]) as $old) {
    quiz_delete_attempt($old, $quizrecord);
}

$quizobj = quiz_settings::create($quizrecord->id, $student->id);
$rule = quizaccess_examproctor::make($quizobj, time(), false);
check($rule !== null, 'rule is active on the seeded quiz');
check(isset($rule->validate_preflight_check([], [], [], null)['examproctor']), 'start refused before pre-checks');

$quiz = $quizobj->get_quiz();
$token = launch_token::mint((int) $student->id, $quiz, (int) $quiz->cmid, $rule->policy());
[$status, $ex] = call('POST', "$service/v1/sessions/exchange", ['launch_token' => $token]);
check($status === 200 && !empty($ex['session_token']), 'service accepts the Moodle launch token');
[$status] = call('POST', "$service/v1/sessions/exchange", ['launch_token' => $token]);
check($status === 409, 'launch token cannot be reused');

$auth = ['Authorization: Bearer ' . $ex['session_token']];
$sid = $ex['session_id'];
[$status] = call('POST', "$service/v1/sessions/$sid/consent",
    ['text_version' => $ex['consent_text_version'], 'accepted' => true], $auth);
check($status === 200, 'consent recorded');

[$status, $pc] = call('POST', "$service/v1/sessions/$sid/precheck",
    ['camera' => 'ok', 'screen' => 'ok', 'screen_surface' => 'window', 'network_ok' => true], $auth);
check(($pc['status'] ?? '') === 'blocked', 'window share is blocked');
check(!gate::find_ready((int) $student->id, (int) $quiz->id), 'blocked pre-check unlocks nothing');

[$status, $pc] = call('POST', "$service/v1/sessions/$sid/precheck",
    ['camera' => 'ok', 'screen' => 'ok', 'screen_surface' => 'monitor', 'network_ok' => true], $auth);
check(($pc['status'] ?? '') === 'ready' && !empty($pc['ready_delivered']), 'whole-screen pre-check passes and webhook delivered');
$ready = gate::find_ready((int) $student->id, (int) $quiz->id);
check($ready !== null && $ready->sessionid === $sid, 'Moodle holds a ready record for this session');

// Forged webhook straight to Moodle.
$body = json_encode(['event' => 'session.ready', 'data' => ['moodle_user_id' => $student->id,
    'quiz_id' => $quiz->id, 'session_id' => 'forged']]);
[$status] = call('POST', 'http://localhost/local/examproctor/webhook.php', $body, [
    'Host: ' . parse_url($CFG->wwwroot, PHP_URL_HOST) . ':' . parse_url($CFG->wwwroot, PHP_URL_PORT),
    'X-ExamProctor-Timestamp: ' . time(), 'X-ExamProctor-Nonce: ' . bin2hex(random_bytes(16)),
    'X-ExamProctor-Signature: ' . str_repeat('0', 64),
]);
check($status === 401, 'forged webhook rejected');
check(!$DB->record_exists('local_examproctor_ready', ['sessionid' => 'forged']), 'forged webhook stored nothing');

check(!isset($rule->validate_preflight_check([], [], [], null)['examproctor']), 'start allowed after signed ready');
$attempt = quiz_prepare_and_start_new_attempt($quizobj, 1, null);
$link = $DB->get_record('local_examproctor_attempt', ['attemptid' => $attempt->id]);
check($link && $link->sessionid === $sid, 'attempt linked to the proctoring session');
check(json_decode($link->policy, true) == $rule->policy(), 'policy frozen on the attempt');
check(isset($rule->validate_preflight_check([], [], [], null)['examproctor']), 'ready record is single use');

mtrace('M2 gate end-to-end: all checks passed');

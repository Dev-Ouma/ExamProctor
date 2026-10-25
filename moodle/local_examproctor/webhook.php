<?php
// This file is part of Moodle - https://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// Moodle is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Moodle.  If not, see <https://www.gnu.org/licenses/>.

/**
 * Endpoint for signed webhooks from the ExamProctor service.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

// phpcs:ignore moodle.Files.RequireLogin.Missing -- Authenticated by HMAC signature, not a Moodle session.
define('NO_MOODLE_COOKIES', true);
define('NO_DEBUG_DISPLAY', true);

require(__DIR__ . '/../../config.php');

use local_examproctor\local\gate;
use local_examproctor\local\webhook_verifier;

/**
 * Send a JSON reply and stop.
 *
 * @param int $status HTTP status.
 * @param array $body response body.
 * @return void
 */
function local_examproctor_webhook_reply(int $status, array $body): void {
    http_response_code($status);
    header('Content-Type: application/json');
    echo json_encode($body);
    die();
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    local_examproctor_webhook_reply(405, ['error' => 'method_not_allowed']);
}

$body = file_get_contents('php://input');
$failure = webhook_verifier::verify(
    $_SERVER['HTTP_X_EXAMPROCTOR_TIMESTAMP'] ?? '',
    $_SERVER['HTTP_X_EXAMPROCTOR_NONCE'] ?? '',
    $_SERVER['HTTP_X_EXAMPROCTOR_SIGNATURE'] ?? '',
    $body
);
if ($failure !== null) {
    local_examproctor_webhook_reply(401, ['error' => $failure]);
}

$message = json_decode($body, true);
if (!is_array($message) || !isset($message['event'], $message['data']) || !is_array($message['data'])) {
    local_examproctor_webhook_reply(400, ['error' => 'bad_body']);
}

$data = $message['data'];
switch ($message['event']) {
    case 'session.ready':
        $userid = clean_param($data['moodle_user_id'] ?? 0, PARAM_INT);
        $quizid = clean_param($data['quiz_id'] ?? 0, PARAM_INT);
        $sessionid = clean_param($data['session_id'] ?? '', PARAM_ALPHANUMEXT);
        if (!$userid || !$quizid || $sessionid === '' || !$DB->record_exists('quiz', ['id' => $quizid])) {
            local_examproctor_webhook_reply(400, ['error' => 'bad_data']);
        }
        gate::record_ready($userid, $quizid, $sessionid, (array) ($data['policy'] ?? []), (array) ($data['context'] ?? []));
        local_examproctor_webhook_reply(200, ['ok' => true]);
        break;
    case 'score.updated':
        $sessionid = clean_param($data['session_id'] ?? '', PARAM_ALPHANUMEXT);
        $band = clean_param($data['band'] ?? '', PARAM_ALPHA);
        if ($sessionid === '' || !in_array($band, ['clear', 'review', 'high'], true)) {
            local_examproctor_webhook_reply(400, ['error' => 'bad_data']);
        }
        $DB->set_field_select(
            'local_examproctor_attempt',
            'integrityscore',
            (float) ($data['integrity_score'] ?? 0),
            'sessionid = ?',
            [$sessionid]
        );
        $DB->set_field_select('local_examproctor_attempt', 'band', $band, 'sessionid = ?', [$sessionid]);
        $questions = [];
        foreach ((array) ($data['questions'] ?? []) as $elementid => $count) {
            $elementid = clean_param($elementid, PARAM_ALPHANUMEXT);
            if ($elementid !== '') {
                $questions[$elementid] = (int) $count;
            }
        }
        $DB->set_field_select('local_examproctor_attempt', 'questionflags', json_encode($questions), 'sessionid = ?', [$sessionid]);
        $DB->set_field_select(
            'local_examproctor_attempt',
            'flagcount',
            (int) ($data['flag_count'] ?? 0),
            'sessionid = ?',
            [$sessionid]
        );
        $DB->set_field_select('local_examproctor_attempt', 'timemodified', time(), 'sessionid = ?', [$sessionid]);
        local_examproctor_webhook_reply(200, ['ok' => true]);
        break;
    case 'decision.recorded':
        $sessionid = clean_param($data['session_id'] ?? '', PARAM_ALPHANUMEXT);
        $kind = $data['kind'] ?? '';
        $value = clean_param($data['value'] ?? '', PARAM_ALPHAEXT);
        $allowed = [
            'decision' => ['no_issue', 'concern', 'refer_misconduct'],
            'appeal' => ['opened', 'upheld', 'overturned', 'withdrawn'],
        ];
        if ($sessionid === '' || !isset($allowed[$kind]) || !in_array($value, $allowed[$kind], true)) {
            local_examproctor_webhook_reply(400, ['error' => 'bad_data']);
        }
        $DB->set_field_select('local_examproctor_attempt', $kind, $value, 'sessionid = ?', [$sessionid]);
        $DB->set_field_select('local_examproctor_attempt', 'timemodified', time(), 'sessionid = ?', [$sessionid]);
        local_examproctor_webhook_reply(200, ['ok' => true]);
        break;
    default:
        // Unknown events are acknowledged so the service does not retry them forever.
        local_examproctor_webhook_reply(200, ['ok' => true, 'ignored' => $message['event']]);
}

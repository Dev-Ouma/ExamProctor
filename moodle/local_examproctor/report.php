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
 * Proctoring report for one quiz: session list, evidence timeline, decisions and appeals, and
 * the live wall for invigilators.
 *
 * Moodle checks the capability and mints a one-hour staff token for this quiz only; the
 * dashboard then reads evidence straight from the service.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

require(__DIR__ . '/../../config.php');

use local_examproctor\local\config;
use local_examproctor\local\staff_token;

$cmid = required_param('cmid', PARAM_INT);
[$course, $cm] = get_course_and_cm_from_cmid($cmid, 'quiz');
require_login($course, false, $cm);
$context = context_module::instance($cm->id);
if (!has_any_capability(['local/examproctor:review', 'local/examproctor:invigilate'], $context)) {
    require_capability('local/examproctor:review', $context);
}
$quiz = $DB->get_record('quiz', ['id' => $cm->instance], '*', MUST_EXIST);

$url = new moodle_url('/local/examproctor/report.php', ['cmid' => $cm->id]);
$PAGE->set_url($url);
$PAGE->set_context($context);
$PAGE->set_title(get_string('report', 'local_examproctor') . ': ' . format_string($quiz->name));
$PAGE->set_heading(format_string($course->fullname));
$PAGE->set_pagelayout('report');

// Names for everyone who could have a session in this quiz; the service only knows user ids.
$people = [];
$namefields = \core_user\fields::for_name()->get_sql('u', false, '', '', false)->selects;
$users = get_enrolled_users(context_course::instance($course->id), 'mod/quiz:attempt', 0, 'u.id, u.idnumber, ' . $namefields);
foreach ($users as $user) {
    $people[$user->id] = ['name' => fullname($user), 'idnumber' => $user->idnumber];
}
// Staff previews and unenrolled users still have sessions; name them from the ready records.
$readyusers = $DB->get_fieldset_select('local_examproctor_ready', 'DISTINCT userid', 'quizid = ?', [$quiz->id]);
foreach (array_diff($readyusers, array_keys($people)) as $userid) {
    $user = core_user::get_user($userid);
    $people[$userid] = ['name' => $user ? fullname($user) : '#' . $userid, 'idnumber' => $user->idnumber ?? ''];
}
$attempts = [];
$links = $DB->get_records('local_examproctor_attempt', ['quizid' => $quiz->id], '', 'id, sessionid, attemptid, userid');
foreach ($links as $link) {
    $attempts[$link->sessionid] = [
        'attemptid' => (int) $link->attemptid,
        'url' => (new moodle_url('/mod/quiz/review.php', ['attempt' => $link->attemptid]))->out(false),
    ];
    if (!isset($people[$link->userid])) {
        $user = core_user::get_user($link->userid);
        $people[$link->userid] = ['name' => $user ? fullname($user) : '#' . $link->userid, 'idnumber' => $user->idnumber ?? ''];
    }
}

$caps = staff_token::caps($context);
$dashboard = [
    'serviceUrl' => config::service_url(),
    'token' => staff_token::mint($USER, $quiz, $caps),
    'tokenTtl' => config::STAFF_TOKEN_TTL,
    'quizId' => (int) $quiz->id,
    'quizName' => format_string($quiz->name),
    'courseName' => format_string($course->fullname),
    'staging' => get_config('local_examproctor', 'mode') !== 'live',
    'caps' => $caps,
    'lang' => current_language(),
    'people' => (object) $people,
    'attempts' => (object) $attempts,
];

$assetversion = ['v' => get_config('local_examproctor', 'version')];
$PAGE->requires->css(new moodle_url('/local/examproctor/dashboard/review.css', $assetversion));
$PAGE->requires->js(new moodle_url('/local/examproctor/dashboard/review.js', $assetversion));
$PAGE->requires->js_init_code(
    'window.ExamProctorReview.mount(document.getElementById("local-examproctor-review"), ' . json_encode($dashboard) . ');'
);

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('report', 'local_examproctor') . ': ' . format_string($quiz->name));
if (!config::is_active()) {
    echo $OUTPUT->notification(get_string('report_notconfigured', 'local_examproctor'), 'warning');
}
echo html_writer::div(get_string('report_loading', 'local_examproctor'), '', ['id' => 'local-examproctor-review']);
echo $OUTPUT->footer();

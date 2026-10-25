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
 * English strings for local_examproctor.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$string['appid'] = 'Application ID';
$string['appid_desc'] = 'Identifier of this Moodle site at the ExamProctor service.';
$string['camerainterval'] = 'Camera snapshot interval (seconds)';
$string['camerainterval_desc'] = 'Seconds between camera snapshots. Default 30. Minimum 5.';
$string['examproctor:configure'] = 'Configure ExamProctor for a quiz';
$string['examproctor:exportevidence'] = 'Export ExamProctor evidence';
$string['examproctor:invigilate'] = 'Invigilate live ExamProctor sessions';
$string['examproctor:review'] = 'Review ExamProctor reports';
$string['killswitch'] = 'Kill switch';
$string['killswitch_desc'] = 'When ticked, ExamProctor is off for every quiz on this site. Quizzes run without proctoring.';
$string['mode'] = 'Mode';
$string['mode_desc'] = 'Staging shows a visible banner and uses the staging service.';
$string['mode_live'] = 'Live';
$string['mode_staging'] = 'Staging';
$string['pluginname'] = 'ExamProctor';
$string['privacy:metadata:attempt'] = 'Links each proctored quiz attempt to its proctoring session.';
$string['privacy:metadata:attempt:attemptid'] = 'The quiz attempt.';
$string['privacy:metadata:attempt:band'] = 'The review band (clear, review, high).';
$string['privacy:metadata:attempt:integrityscore'] = 'The integrity score, a triage aid for human reviewers.';
$string['privacy:metadata:attempt:sessionid'] = 'The proctoring session at the ExamProctor service.';
$string['privacy:metadata:attempt:userid'] = 'The student who made the attempt.';
$string['privacy:metadata:ready'] = 'Records that a student passed the pre-checks for a quiz.';
$string['privacy:metadata:ready:context'] = 'Device limits noted during the pre-checks, for example no screen capture on a phone.';
$string['privacy:metadata:ready:quizid'] = 'The quiz.';
$string['privacy:metadata:ready:sessionid'] = 'The proctoring session at the ExamProctor service.';
$string['privacy:metadata:ready:timecreated'] = 'When the pre-checks passed.';
$string['privacy:metadata:ready:userid'] = 'The student.';
$string['privacy:metadata:service'] = 'The ExamProctor service, hosted by OUK, receives the student and quiz identifiers to run proctoring.';
$string['privacy:metadata:service:quizid'] = 'The quiz.';
$string['privacy:metadata:service:userid'] = 'The Moodle user id.';
$string['screeninterval'] = 'Screen snapshot interval (seconds)';
$string['screeninterval_desc'] = 'Seconds between screen snapshots on computers. Default 60. Minimum 5. An extra snapshot is taken when the student leaves the quiz page.';
$string['serviceurl'] = 'Service URL';
$string['serviceurl_desc'] = 'Base URL of the ExamProctor service, for example https://proctor.example.ac.ke.';
$string['signingkey'] = 'Signing key';
$string['signingkey_desc'] = 'Shared secret used to sign launch tokens and verify service webhooks.';
$string['task_cleanup'] = 'Remove expired ExamProctor ready records and webhook nonces';

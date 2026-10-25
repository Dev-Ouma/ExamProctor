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
 * English strings for quizaccess_examproctor.
 *
 * @package    quizaccess_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$string['attemptsummary'] = 'Proctoring: integrity score {$a->score}, {$a->flags} flags. Open the proctoring report.';
$string['camera'] = 'Camera';
$string['camera_help'] = 'Take camera snapshots during the attempt and check that one person is present.';
$string['enabled'] = 'ExamProctor proctoring';
$string['enabled_help'] = 'Students must pass consent and device checks before the attempt starts. AI flags help reviewers; it never fails a student by itself.';
$string['flagsonquestion'] = '{$a} proctoring flags';
$string['identity'] = 'Identity check';
$string['identity_help'] = 'Capture a reference photo at the start and compare it with later snapshots.';
$string['identityneedscamera'] = 'The identity check needs the camera.';
$string['mobileappblocked'] = 'This quiz is proctored and cannot be taken in the Moodle app. Open it in a web browser: {$a}';
$string['notready'] = 'Finish the ExamProctor checks above before you start the attempt.';
$string['pluginname'] = 'ExamProctor';
$string['precheckheader'] = 'ExamProctor checks';
$string['precheckloading'] = 'Loading the proctoring checks…';
$string['privacy:metadata'] = 'The ExamProctor quiz access rule stores only per-quiz settings. Student data is stored by local_examproctor.';
$string['screen'] = 'Screen';
$string['screen_help'] = 'Take snapshots of the whole screen on laptops and desktops. Phones and tablets cannot share the screen.';
$string['strict'] = 'Strict mode';
$string['strict_help'] = 'If ticked, a student whose device cannot provide a required camera or screen cannot start. If not ticked, the student continues and the gap is noted for reviewers.';
$string['strictneedsdevice'] = 'Strict mode needs the camera or the screen.';

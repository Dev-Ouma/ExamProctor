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
$string['examproctor:managerefphotos'] = 'Manage ExamProctor reference photos';
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
$string['privacy:metadata:refphoto'] = 'Admission photo used to confirm identity during proctored quizzes.';
$string['privacy:metadata:refphoto:file'] = 'The photo file.';
$string['privacy:metadata:refphoto:source'] = 'How the photo was added.';
$string['privacy:metadata:refphoto:status'] = 'Whether the photo is usable for identity matching.';
$string['privacy:metadata:refphoto:timemodified'] = 'When the photo was last changed.';
$string['privacy:metadata:refphoto:userid'] = 'The student.';
$string['privacy:metadata:service'] = 'The ExamProctor service, hosted by OUK, receives the student and quiz identifiers to run proctoring.';
$string['privacy:metadata:service:photo'] = 'The admission photo and a face template made from it, for identity matching.';
$string['privacy:metadata:service:quizid'] = 'The quiz.';
$string['privacy:metadata:service:userid'] = 'The Moodle user id.';
$string['refphoto_badimage'] = 'The file is not a JPEG or PNG image of at most 2 MB.';
$string['refphoto_confirmdelete'] = 'Delete this reference photo here and at the proctoring service?';
$string['refphoto_delete'] = 'Delete';
$string['refphoto_deleted'] = 'Reference photo deleted.';
$string['refphoto_field'] = 'Student identified by';
$string['refphoto_field_email'] = 'Email';
$string['refphoto_field_id'] = 'Moodle user id';
$string['refphoto_field_idnumber'] = 'ID number (admission number)';
$string['refphoto_field_username'] = 'Username';
$string['refphoto_file'] = 'Photo (JPEG/PNG) or ZIP of photos';
$string['refphoto_nouser'] = 'No single student matches that identifier.';
$string['refphoto_photo'] = 'Photo';
$string['refphoto_revalidate'] = 'Check again';
$string['refphoto_search'] = 'Name, username or ID number';
$string['refphoto_source'] = 'Source';
$string['refphoto_status_error'] = 'Not checked yet (service unreachable)';
$string['refphoto_status_invalid'] = 'Not usable';
$string['refphoto_status_pending'] = 'Waiting for check';
$string['refphoto_status_valid'] = 'Usable';
$string['refphoto_upload'] = 'Upload';
$string['refphoto_value'] = 'Identifier';
$string['refphoto_value_help'] = 'For a single photo, the student\'s identifier. For a ZIP, leave empty: each file name (without extension) must be the identifier, for example OUK-2026-00123.jpg.';
$string['refphoto_zip_result'] = '{$a->saved} photos queued for checking, {$a->skipped} skipped.';
$string['refphotos'] = 'ExamProctor reference photos';
$string['refphotos_intro'] = 'Admission photos used to confirm a student\'s identity during proctored quizzes. Each photo is checked for one clear, large enough face. Students consented to this use at admission.';
$string['screeninterval'] = 'Screen snapshot interval (seconds)';
$string['screeninterval_desc'] = 'Seconds between screen snapshots on computers. Default 60. Minimum 5. An extra snapshot is taken when the student leaves the quiz page.';
$string['serviceinternalurl'] = 'Service URL for Moodle (server to server)';
$string['serviceinternalurl_desc'] = 'Optional. Use when Moodle reaches the service on an internal address. Empty means the service URL above.';
$string['serviceurl'] = 'Service URL';
$string['serviceurl_desc'] = 'Base URL of the ExamProctor service, for example https://proctor.example.ac.ke.';
$string['signingkey'] = 'Signing key';
$string['signingkey_desc'] = 'Shared secret used to sign launch tokens and verify service webhooks.';
$string['task_cleanup'] = 'Remove expired ExamProctor ready records and webhook nonces';
$string['task_retry_refphotos'] = 'Retry ExamProctor reference photos that failed to reach the service';

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

use local_examproctor\local\config;
use local_examproctor\local\gate;
use local_examproctor\local\launch_token;
use mod_quiz\form\preflight_check_form;
use mod_quiz\local\access_rule_base;
use mod_quiz\quiz_settings;

/**
 * ExamProctor quiz access rule: the launch gate.
 *
 * A proctored attempt can start only when Moodle holds a service-signed ready record for this user and quiz.
 * The browser never unlocks an attempt by itself.
 *
 * @package    quizaccess_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class quizaccess_examproctor extends access_rule_base {
    /** @var string[] Policy switches stored per quiz, in form order. */
    private const SWITCHES = ['camera', 'screen', 'identity', 'strict'];

    /**
     * Return an instance of this rule if it applies to the quiz, else null.
     *
     * @param quiz_settings $quizobj the quiz.
     * @param int $timenow the time that should be considered as 'now'.
     * @param bool $canignoretimelimits whether the user may ignore time limits.
     * @return access_rule_base|null
     */
    public static function make(quiz_settings $quizobj, $timenow, $canignoretimelimits) {
        if (empty($quizobj->get_quiz()->examproctor_enabled) || !config::is_active()) {
            return null;
        }
        return new self($quizobj, $timenow);
    }

    /**
     * Policy sent to the service in the launch token.
     *
     * @return array
     */
    public function policy(): array {
        $policy = [];
        foreach (self::SWITCHES as $name) {
            $policy[$name] = !empty($this->quiz->{'examproctor_' . $name});
        }
        return $policy;
    }

    /**
     * Proctored quizzes cannot run inside the Moodle mobile app.
     *
     * @return string|false
     */
    public function prevent_access() {
        if (\core_useragent::is_moodle_app()) {
            $url = new moodle_url('/mod/quiz/view.php', ['id' => $this->quiz->cmid]);
            return get_string('mobileappblocked', 'quizaccess_examproctor', $url->out(false));
        }
        return false;
    }

    /**
     * Pre-checks are needed before a new attempt. A resumed attempt is already linked to its session.
     *
     * @param int|null $attemptid
     * @return bool
     */
    public function is_preflight_check_required($attemptid) {
        return empty($attemptid);
    }

    /**
     * Add the pre-check panel. The SDK runs consent and device checks against the service.
     *
     * @param preflight_check_form $quizform
     * @param MoodleQuickForm $mform
     * @param int|null $attemptid
     * @return void
     */
    public function add_preflight_check_form_fields(preflight_check_form $quizform, MoodleQuickForm $mform, $attemptid) {
        global $PAGE, $USER;

        $token = launch_token::mint((int) $USER->id, $this->quiz, (int) $this->quiz->cmid, $this->policy());
        $mform->addElement('header', 'examproctorheader', get_string('precheckheader', 'quizaccess_examproctor'));
        $mform->addElement('static', 'examproctor', '',
            html_writer::div(get_string('precheckloading', 'quizaccess_examproctor'), '', ['id' => 'examproctor-precheck']));
        $PAGE->requires->js_call_amd('quizaccess_examproctor/sdk', 'mountPrecheck', [[
            'container' => '#examproctor-precheck',
            'serviceUrl' => config::service_url(),
            'launchToken' => $token,
            'lang' => current_language(),
            'staging' => get_config('local_examproctor', 'mode') !== 'live',
        ]]);
    }

    /**
     * Server-side gate: refuse the start unless the service has signed a ready record.
     *
     * @param array $data form data.
     * @param array $files form files.
     * @param array $errors errors from other rules; kept as they are.
     * @param int|null $attemptid
     * @return array
     */
    public function validate_preflight_check($data, $files, $errors, $attemptid) {
        global $USER;
        if (!gate::find_ready((int) $USER->id, (int) $this->quiz->id)) {
            $errors['examproctor'] = get_string('notready', 'quizaccess_examproctor');
        }
        return $errors;
    }

    /**
     * Add the policy fields to the quiz settings form.
     *
     * @param mod_quiz_mod_form $quizform
     * @param MoodleQuickForm $mform
     * @return void
     */
    public static function add_settings_form_fields(mod_quiz_mod_form $quizform, MoodleQuickForm $mform) {
        $mform->addElement('selectyesno', 'examproctor_enabled', get_string('enabled', 'quizaccess_examproctor'));
        $mform->addHelpButton('examproctor_enabled', 'enabled', 'quizaccess_examproctor');
        $defaults = ['camera' => 1, 'screen' => 0, 'identity' => 0, 'strict' => 0];
        foreach (self::SWITCHES as $name) {
            $field = 'examproctor_' . $name;
            $mform->addElement('advcheckbox', $field, get_string($name, 'quizaccess_examproctor'));
            $mform->addHelpButton($field, $name, 'quizaccess_examproctor');
            $mform->setDefault($field, $defaults[$name]);
            $mform->hideIf($field, 'examproctor_enabled', 'eq', 0);
        }
        $mform->hideIf('examproctor_identity', 'examproctor_camera', 'notchecked');
    }

    /**
     * Policy rules: strict needs a device; identity needs the camera.
     *
     * @param array $errors
     * @param array $data
     * @param array $files
     * @param mod_quiz_mod_form $quizform
     * @return array
     */
    public static function validate_settings_form_fields(array $errors, array $data, $files, mod_quiz_mod_form $quizform) {
        if (!empty($data['examproctor_enabled'])) {
            if (!empty($data['examproctor_strict']) && empty($data['examproctor_camera']) && empty($data['examproctor_screen'])) {
                $errors['examproctor_strict'] = get_string('strictneedsdevice', 'quizaccess_examproctor');
            }
            if (!empty($data['examproctor_identity']) && empty($data['examproctor_camera'])) {
                $errors['examproctor_identity'] = get_string('identityneedscamera', 'quizaccess_examproctor');
            }
        }
        return $errors;
    }

    /**
     * Save the policy row for a quiz.
     *
     * @param stdClass $quiz form data with the quiz id.
     * @return void
     */
    public static function save_settings($quiz) {
        global $DB;
        $record = (object) ['quizid' => $quiz->id, 'enabled' => empty($quiz->examproctor_enabled) ? 0 : 1];
        foreach (self::SWITCHES as $name) {
            $record->$name = empty($quiz->{'examproctor_' . $name}) ? 0 : 1;
        }
        if ($existing = $DB->get_record('quizaccess_examproctor', ['quizid' => $quiz->id])) {
            $record->id = $existing->id;
            $DB->update_record('quizaccess_examproctor', $record);
        } else {
            $DB->insert_record('quizaccess_examproctor', $record);
        }
    }

    /**
     * Delete the policy row when the quiz is deleted.
     *
     * @param stdClass $quiz
     * @return void
     */
    public static function delete_settings($quiz) {
        global $DB;
        $DB->delete_records('quizaccess_examproctor', ['quizid' => $quiz->id]);
    }

    /**
     * Load the policy with the quiz settings.
     *
     * @param int $quizid
     * @return array
     */
    public static function get_settings_sql($quizid) {
        return [
            'examproctor.enabled AS examproctor_enabled, examproctor.camera AS examproctor_camera, '
                . 'examproctor.screen AS examproctor_screen, examproctor.identity AS examproctor_identity, '
                . 'examproctor.strict AS examproctor_strict',
            'LEFT JOIN {quizaccess_examproctor} examproctor ON examproctor.quizid = quiz.id',
            [],
        ];
    }
}

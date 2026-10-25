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

namespace quizaccess_examproctor;

use local_examproctor\local\gate;
use mod_quiz\quiz_settings;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->dirroot . '/mod/quiz/accessrule/examproctor/rule.php');
require_once($CFG->dirroot . '/mod/quiz/mod_form.php');

/**
 * Tests for the ExamProctor launch gate rule.
 *
 * @package    quizaccess_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 * @covers     \quizaccess_examproctor
 */
final class rule_test extends \advanced_testcase {
    /**
     * Create a quiz with a proctoring policy and an active site configuration.
     *
     * @param array $policy
     * @return \stdClass quiz record
     */
    private function proctored_quiz(array $policy = []): \stdClass {
        global $DB;
        $this->resetAfterTest();
        set_config('signingkey', str_repeat('k', 40), 'local_examproctor');
        set_config('serviceurl', 'https://proctor.example.invalid', 'local_examproctor');
        $quiz = $this->getDataGenerator()->create_module('quiz', ['course' => $this->getDataGenerator()->create_course()->id]);
        // Creating the quiz already saved a default policy row through save_settings().
        $row = $DB->get_record('quizaccess_examproctor', ['quizid' => $quiz->id], 'id', MUST_EXIST);
        $DB->update_record('quizaccess_examproctor', (object) array_merge(
            ['id' => $row->id, 'enabled' => 1, 'camera' => 1, 'screen' => 1, 'identity' => 0, 'strict' => 0],
            $policy
        ));
        return $quiz;
    }

    public function test_rule_is_registered(): void {
        $this->assertArrayHasKey('examproctor', \core_component::get_plugin_list('quizaccess'));
    }

    public function test_not_applied_when_disabled_or_kill_switch_on(): void {
        $quiz = $this->proctored_quiz(['enabled' => 0]);
        $this->assertNull(\quizaccess_examproctor::make(quiz_settings::create($quiz->id), time(), false));

        $quiz = $this->proctored_quiz();
        set_config('killswitch', 1, 'local_examproctor');
        $this->assertNull(\quizaccess_examproctor::make(quiz_settings::create($quiz->id), time(), false));
    }

    public function test_policy_comes_from_quiz_settings(): void {
        $quiz = $this->proctored_quiz(['strict' => 1]);
        $rule = \quizaccess_examproctor::make(quiz_settings::create($quiz->id), time(), false);

        $this->assertSame(
            ['camera' => true, 'screen' => true, 'identity' => false, 'strict' => true,
                'camera_interval_s' => 30, 'screen_interval_s' => 60],
            $rule->policy()
        );
    }

    public function test_start_needs_a_signed_ready_record(): void {
        $quiz = $this->proctored_quiz();
        $user = $this->getDataGenerator()->create_user();
        $this->setUser($user);
        $rule = \quizaccess_examproctor::make(quiz_settings::create($quiz->id), time(), false);

        $this->assertTrue($rule->is_preflight_check_required(null));
        $this->assertFalse($rule->is_preflight_check_required(12));
        $this->assertArrayHasKey('examproctor', $rule->validate_preflight_check([], [], [], null));

        gate::record_ready((int) $user->id, (int) $quiz->id, 'sess', $rule->policy());
        $this->assertSame([], $rule->validate_preflight_check([], [], [], null));
    }

    public function test_other_rules_errors_are_kept(): void {
        $quiz = $this->proctored_quiz();
        $this->setUser($this->getDataGenerator()->create_user());
        $rule = \quizaccess_examproctor::make(quiz_settings::create($quiz->id), time(), false);

        $errors = $rule->validate_preflight_check([], [], ['quizpassword' => 'wrong'], null);

        $this->assertSame('wrong', $errors['quizpassword']);
    }

    public function test_settings_validation(): void {
        $form = $this->getMockBuilder(\mod_quiz_mod_form::class)->disableOriginalConstructor()->getMock();
        $base = ['examproctor_enabled' => 1, 'examproctor_camera' => 0, 'examproctor_screen' => 0];

        $errors = \quizaccess_examproctor::validate_settings_form_fields([], $base + ['examproctor_strict' => 1], [], $form);
        $this->assertArrayHasKey('examproctor_strict', $errors);
        $errors = \quizaccess_examproctor::validate_settings_form_fields([], $base + ['examproctor_identity' => 1], [], $form);
        $this->assertArrayHasKey('examproctor_identity', $errors);
    }

    public function test_save_and_delete_settings(): void {
        global $DB;
        $this->resetAfterTest();
        $data = (object) ['id' => 99, 'examproctor_enabled' => 1, 'examproctor_camera' => 1, 'examproctor_screen' => 0,
            'examproctor_identity' => 1, 'examproctor_strict' => 0];

        \quizaccess_examproctor::save_settings($data);
        $data->examproctor_screen = 1;
        \quizaccess_examproctor::save_settings($data);

        $row = $DB->get_record('quizaccess_examproctor', ['quizid' => 99], '*', MUST_EXIST);
        $this->assertEquals([1, 1, 1, 1, 0], [$row->enabled, $row->camera, $row->screen, $row->identity, $row->strict]);
        \quizaccess_examproctor::delete_settings((object) ['id' => 99]);
        $this->assertFalse($DB->record_exists('quizaccess_examproctor', ['quizid' => 99]));
    }
}

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

use mod_quiz\quiz_settings;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->dirroot . '/mod/quiz/accessrule/examproctor/rule.php');

/**
 * Tests for the ExamProctor access rule skeleton.
 *
 * @package    quizaccess_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 * @covers     \quizaccess_examproctor
 */
final class rule_test extends \advanced_testcase {
    public function test_rule_is_registered(): void {
        $rules = \core_component::get_plugin_list('quizaccess');
        $this->assertArrayHasKey('examproctor', $rules);
    }

    public function test_make_returns_null_until_gate_exists(): void {
        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course();
        $quiz = $this->getDataGenerator()->create_module('quiz', ['course' => $course->id]);
        $quizobj = quiz_settings::create($quiz->id);

        $this->assertNull(\quizaccess_examproctor::make($quizobj, time(), false));
    }
}

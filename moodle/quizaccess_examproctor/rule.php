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

use mod_quiz\local\access_rule_base;
use mod_quiz\quiz_settings;

/**
 * ExamProctor quiz access rule.
 *
 * M1 skeleton: the rule installs and registers, but does not yet apply to any quiz.
 * The launch gate (ready record check, policy snapshot, Moodle app block) arrives in M2.
 *
 * @package    quizaccess_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class quizaccess_examproctor extends access_rule_base {
    /**
     * Return an instance of this rule if it applies to the quiz, else null.
     *
     * @param quiz_settings $quizobj the quiz.
     * @param int $timenow the time that should be considered as 'now'.
     * @param bool $canignoretimelimits whether the user may ignore time limits.
     * @return access_rule_base|null
     */
    public static function make(quiz_settings $quizobj, $timenow, $canignoretimelimits) {
        return null;
    }
}

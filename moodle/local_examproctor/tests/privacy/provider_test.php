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

namespace local_examproctor\privacy;

use core_privacy\local\request\approved_contextlist;
use core_privacy\local\request\writer;
use local_examproctor\local\gate;

/**
 * Privacy provider tests.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 * @covers     \local_examproctor\privacy\provider
 */
final class provider_test extends \core_privacy\tests\provider_testcase {
    public function test_export_and_delete_for_user(): void {
        global $DB;
        $this->resetAfterTest();
        $gen = $this->getDataGenerator();
        [$alice, $bob] = [$gen->create_user(), $gen->create_user()];
        $quiz = $gen->create_module('quiz', ['course' => $gen->create_course()->id]);
        $context = \context_module::instance($quiz->cmid);
        gate::record_ready((int) $alice->id, (int) $quiz->id, 'sa', ['camera' => true]);
        gate::record_ready((int) $bob->id, (int) $quiz->id, 'sb', ['camera' => true]);

        $contexts = provider::get_contexts_for_userid((int) $alice->id);
        $this->assertEquals([$context->id], $contexts->get_contextids());

        provider::export_user_data(new approved_contextlist($alice, 'local_examproctor', [$context->id]));
        $this->assertTrue(writer::with_context($context)->has_any_data());

        provider::delete_data_for_user(new approved_contextlist($alice, 'local_examproctor', [$context->id]));
        $this->assertFalse($DB->record_exists('local_examproctor_ready', ['userid' => $alice->id]));
        $this->assertTrue($DB->record_exists('local_examproctor_ready', ['userid' => $bob->id]));
    }
}

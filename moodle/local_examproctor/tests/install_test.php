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

namespace local_examproctor;

/**
 * Install and settings tests for local_examproctor.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 * @coversNothing
 */
final class install_test extends \advanced_testcase {
    public function test_capabilities_are_installed(): void {
        foreach (['review', 'invigilate', 'configure', 'exportevidence'] as $name) {
            $this->assertNotEmpty(get_capability_info("local/examproctor:{$name}"), $name);
        }
    }

    public function test_defaults_to_staging_mode_with_kill_switch_off(): void {
        $this->resetAfterTest();
        $this->assertSame('staging', get_config('local_examproctor', 'mode'));
        $this->assertEmpty(get_config('local_examproctor', 'killswitch'));
    }
}

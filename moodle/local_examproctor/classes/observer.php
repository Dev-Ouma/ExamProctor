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

use local_examproctor\local\gate;

/**
 * Quiz event observers.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class observer {
    /**
     * Link a new attempt to the session whose pre-checks unlocked it.
     *
     * @param \mod_quiz\event\attempt_started $event
     * @return void
     */
    public static function attempt_started(\mod_quiz\event\attempt_started $event): void {
        $attempt = $event->get_record_snapshot('quiz_attempts', $event->objectid);
        gate::link_attempt((int) $attempt->id, (int) $attempt->userid, (int) $attempt->quiz);
    }

    /**
     * Remove a deleted user's reference photo, here and at the service.
     *
     * @param \core\event\user_deleted $event
     * @return void
     */
    public static function user_deleted(\core\event\user_deleted $event): void {
        \local_examproctor\local\refphotos::delete((int) $event->objectid);
    }
}

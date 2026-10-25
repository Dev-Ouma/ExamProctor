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

namespace local_examproctor\task;

use local_examproctor\local\refphotos;

/**
 * Retry reference photos that failed to reach the service.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class retry_refphotos extends \core\task\scheduled_task {
    /**
     * Task name.
     *
     * @return string
     */
    public function get_name(): string {
        return get_string('task_retry_refphotos', 'local_examproctor');
    }

    /**
     * Run the task.
     *
     * @return void
     */
    public function execute(): void {
        global $DB;
        $stale = time() - 10 * MINSECS;
        $rows = $DB->get_records_select(
            'local_examproctor_refphoto',
            "status = 'error' OR (status = 'pending' AND timemodified < ?)",
            [$stale],
            'timemodified',
            'userid',
            0,
            500
        );
        foreach ($rows as $row) {
            refphotos::push((int) $row->userid);
        }
        mtrace('Retried ' . count($rows) . ' reference photos');
    }
}

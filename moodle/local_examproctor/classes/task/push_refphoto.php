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
 * Push one queued reference photo to the service (bulk imports).
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class push_refphoto extends \core\task\adhoc_task {
    /**
     * Run the task.
     *
     * @return void
     */
    public function execute(): void {
        $userid = (int) ($this->get_custom_data()->userid ?? 0);
        if ($userid && refphotos::get($userid)) {
            refphotos::push($userid);
        }
    }
}

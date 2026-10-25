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

namespace local_examproctor\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * List reference photos, optionally by status, paged by user id.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class refphoto_list extends external_api {
    /**
     * Parameters.
     *
     * @return external_function_parameters
     */
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'status' => new external_value(PARAM_ALPHA, 'Filter: pending, valid, invalid, error; empty for all', VALUE_DEFAULT, ''),
            'afteruserid' => new external_value(PARAM_INT, 'Cursor: return users with a larger id', VALUE_DEFAULT, 0),
            'limit' => new external_value(PARAM_INT, 'Page size, at most 500', VALUE_DEFAULT, 100),
        ]);
    }

    /**
     * List.
     *
     * @param string $status
     * @param int $afteruserid
     * @param int $limit
     * @return array
     */
    public static function execute(string $status = '', int $afteruserid = 0, int $limit = 100): array {
        global $DB;
        $params = self::validate_parameters(
            self::execute_parameters(),
            ['status' => $status, 'afteruserid' => $afteruserid, 'limit' => $limit]
        );
        $context = \context_system::instance();
        self::validate_context($context);
        require_capability('local/examproctor:managerefphotos', $context);
        $where = 'userid > :after';
        $sqlparams = ['after' => $params['afteruserid']];
        if ($params['status'] !== '') {
            $where .= ' AND status = :status';
            $sqlparams['status'] = $params['status'];
        }
        $rows = $DB->get_records_select(
            'local_examproctor_refphoto',
            $where,
            $sqlparams,
            'userid',
            '*',
            0,
            max(1, min(500, $params['limit']))
        );
        return ['photos' => array_values(array_map([refphoto_get::class, 'describe'], $rows))];
    }

    /**
     * Result.
     *
     * @return external_single_structure
     */
    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'photos' => new external_multiple_structure(refphoto_get::record_structure()),
        ]);
    }
}

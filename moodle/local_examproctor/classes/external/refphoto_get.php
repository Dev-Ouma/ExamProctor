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
use core_external\external_single_structure;
use core_external\external_value;
use local_examproctor\local\refphotos;

/**
 * Read a student's reference photo status.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class refphoto_get extends external_api {
    /**
     * Parameters.
     *
     * @return external_function_parameters
     */
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'field' => new external_value(PARAM_ALPHA, 'Identifier type: id, username, idnumber or email'),
            'value' => new external_value(PARAM_RAW, 'Identifier value'),
        ]);
    }

    /**
     * Get the record.
     *
     * @param string $field
     * @param string $value
     * @return array
     */
    public static function execute(string $field, string $value): array {
        ['field' => $field, 'value' => $value] = self::validate_parameters(
            self::execute_parameters(),
            ['field' => $field, 'value' => $value]
        );
        $context = \context_system::instance();
        self::validate_context($context);
        require_capability('local/examproctor:managerefphotos', $context);
        $user = refphotos::find_user($field, $value);
        $record = $user ? refphotos::get((int) $user->id) : null;
        if (!$record) {
            throw new \invalid_parameter_exception('No reference photo for that identifier');
        }
        return self::describe($record);
    }

    /**
     * Public shape of a record.
     *
     * @param \stdClass $record
     * @return array
     */
    public static function describe(\stdClass $record): array {
        return [
            'userid' => (int) $record->userid,
            'status' => $record->status,
            'reason' => $record->reason ?? '',
            'facepx' => (int) ($record->facepx ?? 0),
            'source' => $record->source,
            'timemodified' => (int) $record->timemodified,
        ];
    }

    /**
     * Structure shared by save, get and list.
     *
     * @return external_single_structure
     */
    public static function record_structure(): external_single_structure {
        return new external_single_structure([
            'userid' => new external_value(PARAM_INT, 'Moodle user id'),
            'status' => new external_value(PARAM_ALPHA, 'pending, valid, invalid or error'),
            'reason' => new external_value(PARAM_ALPHANUMEXT, 'Why the photo is invalid, if it is'),
            'facepx' => new external_value(PARAM_INT, 'Detected face size in pixels'),
            'source' => new external_value(PARAM_ALPHA, 'upload, zip, cli or api'),
            'timemodified' => new external_value(PARAM_INT, 'Last change'),
        ]);
    }

    /**
     * Result.
     *
     * @return external_single_structure
     */
    public static function execute_returns(): external_single_structure {
        return self::record_structure();
    }
}

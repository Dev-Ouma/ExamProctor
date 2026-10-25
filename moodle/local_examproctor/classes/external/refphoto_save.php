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
 * Create or replace a student's reference photo (for the admissions system).
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class refphoto_save extends external_api {
    /**
     * Parameters.
     *
     * @return external_function_parameters
     */
    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'field' => new external_value(PARAM_ALPHA, 'Identifier type: id, username, idnumber or email'),
            'value' => new external_value(PARAM_RAW, 'Identifier value'),
            'image' => new external_value(PARAM_RAW, 'Base64 JPEG or PNG, at most 2 MB decoded'),
            'sync' => new external_value(PARAM_BOOL, 'Validate now (true) or queue (false)', VALUE_DEFAULT, true),
        ]);
    }

    /**
     * Save the photo.
     *
     * @param string $field
     * @param string $value
     * @param string $image
     * @param bool $sync
     * @return array
     */
    public static function execute(string $field, string $value, string $image, bool $sync = true): array {
        ['field' => $field, 'value' => $value, 'image' => $image, 'sync' => $sync] = self::validate_parameters(
            self::execute_parameters(),
            ['field' => $field, 'value' => $value, 'image' => $image, 'sync' => $sync]
        );
        $context = \context_system::instance();
        self::validate_context($context);
        require_capability('local/examproctor:managerefphotos', $context);
        $user = refphotos::find_user($field, $value);
        if (!$user) {
            throw new \invalid_parameter_exception('No unique user matches that identifier');
        }
        $bytes = base64_decode($image, true);
        if ($bytes === false) {
            throw new \invalid_parameter_exception('Image is not valid base64');
        }
        return refphoto_get::describe(refphotos::save((int) $user->id, $bytes, 'api', $sync));
    }

    /**
     * Result.
     *
     * @return external_single_structure
     */
    public static function execute_returns(): external_single_structure {
        return refphoto_get::record_structure();
    }
}

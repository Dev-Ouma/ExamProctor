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

/**
 * Library callbacks for local_examproctor.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

/**
 * Serve reference photos to reference photo managers only.
 *
 * @param stdClass $course
 * @param stdClass $cm
 * @param context $context
 * @param string $filearea
 * @param array $args
 * @param bool $forcedownload
 * @param array $options
 * @return bool false if the file is not served
 */
function local_examproctor_pluginfile($course, $cm, $context, $filearea, $args, $forcedownload, array $options = []) {
    if ($filearea !== 'refphoto' || $context->contextlevel !== CONTEXT_SYSTEM) {
        return false;
    }
    require_login();
    require_capability('local/examproctor:managerefphotos', $context);
    $itemid = (int) array_shift($args);
    $file = get_file_storage()->get_file($context->id, 'local_examproctor', 'refphoto', $itemid, '/', (string) array_pop($args));
    if (!$file) {
        return false;
    }
    send_stored_file($file, 0, 0, $forcedownload, $options + ['cacheability' => 'private']);
}

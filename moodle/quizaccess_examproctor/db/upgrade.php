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
 * Upgrade steps for quizaccess_examproctor.
 *
 * @package    quizaccess_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

/**
 * Upgrade quizaccess_examproctor.
 *
 * @param int $oldversion the version we are upgrading from.
 * @return bool
 */
function xmldb_quizaccess_examproctor_upgrade($oldversion) {
    global $DB;
    $dbman = $DB->get_manager();

    if ($oldversion < 2026102600) {
        // M2: per-quiz policy table.
        if (!$dbman->table_exists('quizaccess_examproctor')) {
            $dbman->install_one_table_from_xmldb_file(__DIR__ . '/install.xml', 'quizaccess_examproctor');
        }
        upgrade_plugin_savepoint(true, 2026102600, 'quizaccess', 'examproctor');
    }

    return true;
}

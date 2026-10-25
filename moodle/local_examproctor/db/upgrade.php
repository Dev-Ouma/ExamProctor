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
 * Upgrade steps for local_examproctor.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

/**
 * Upgrade local_examproctor.
 *
 * @param int $oldversion the version we are upgrading from.
 * @return bool
 */
function xmldb_local_examproctor_upgrade($oldversion) {
    global $DB;
    $dbman = $DB->get_manager();

    if ($oldversion < 2026102600) {
        // M2: launch gate tables, created from install.xml definitions.
        $installxml = __DIR__ . '/install.xml';
        foreach (['local_examproctor_ready', 'local_examproctor_attempt', 'local_examproctor_nonce'] as $name) {
            if (!$dbman->table_exists($name)) {
                $dbman->install_one_table_from_xmldb_file($installxml, $name);
            }
        }
        upgrade_plugin_savepoint(true, 2026102600, 'local', 'examproctor');
    }

    if ($oldversion < 2026102800) {
        // M4: institutional reference photos.
        if (!$dbman->table_exists('local_examproctor_refphoto')) {
            $dbman->install_one_table_from_xmldb_file(__DIR__ . '/install.xml', 'local_examproctor_refphoto');
        }
        upgrade_plugin_savepoint(true, 2026102800, 'local', 'examproctor');
    }

    if ($oldversion < 2026102900) {
        // M5: reviewer decision and appeal status on the attempt summary.
        $table = new xmldb_table('local_examproctor_attempt');
        $fields = [
            new xmldb_field('decision', XMLDB_TYPE_CHAR, '20', null, null, null, null, 'flagcount'),
            new xmldb_field('appeal', XMLDB_TYPE_CHAR, '20', null, null, null, null, 'decision'),
        ];
        foreach ($fields as $field) {
            if (!$dbman->field_exists($table, $field)) {
                $dbman->add_field($table, $field);
            }
        }
        upgrade_plugin_savepoint(true, 2026102900, 'local', 'examproctor');
    }

    return true;
}

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
 * Site settings for local_examproctor.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

if ($hassiteconfig) {
    $settings = new admin_settingpage('local_examproctor', get_string('pluginname', 'local_examproctor'));
    $ADMIN->add('localplugins', $settings);

    $settings->add(new admin_setting_configselect(
        'local_examproctor/mode',
        get_string('mode', 'local_examproctor'),
        get_string('mode_desc', 'local_examproctor'),
        'staging',
        [
            'staging' => get_string('mode_staging', 'local_examproctor'),
            'live' => get_string('mode_live', 'local_examproctor'),
        ]
    ));
    $settings->add(new admin_setting_configcheckbox(
        'local_examproctor/killswitch',
        get_string('killswitch', 'local_examproctor'),
        get_string('killswitch_desc', 'local_examproctor'),
        0
    ));
    $settings->add(new admin_setting_configtext(
        'local_examproctor/serviceurl',
        get_string('serviceurl', 'local_examproctor'),
        get_string('serviceurl_desc', 'local_examproctor'),
        '',
        PARAM_URL
    ));
    $settings->add(new admin_setting_configtext(
        'local_examproctor/appid',
        get_string('appid', 'local_examproctor'),
        get_string('appid_desc', 'local_examproctor'),
        '',
        PARAM_ALPHANUMEXT
    ));
    $settings->add(new admin_setting_configpasswordunmask(
        'local_examproctor/signingkey',
        get_string('signingkey', 'local_examproctor'),
        get_string('signingkey_desc', 'local_examproctor'),
        ''
    ));
}

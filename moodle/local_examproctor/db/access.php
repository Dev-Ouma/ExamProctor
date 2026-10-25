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
 * Capabilities for local_examproctor.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$capabilities = [
    'local/examproctor:review' => [
        'riskbitmask' => RISK_PERSONAL,
        'captype' => 'read',
        'contextlevel' => CONTEXT_MODULE,
        'archetypes' => [
            'editingteacher' => CAP_ALLOW,
            'manager' => CAP_ALLOW,
        ],
    ],
    'local/examproctor:invigilate' => [
        'riskbitmask' => RISK_PERSONAL,
        'captype' => 'write',
        'contextlevel' => CONTEXT_MODULE,
        'archetypes' => [
            'manager' => CAP_ALLOW,
        ],
    ],
    'local/examproctor:configure' => [
        'riskbitmask' => RISK_CONFIG,
        'captype' => 'write',
        'contextlevel' => CONTEXT_MODULE,
        'archetypes' => [
            'editingteacher' => CAP_ALLOW,
            'manager' => CAP_ALLOW,
        ],
    ],
    'local/examproctor:exportevidence' => [
        'riskbitmask' => RISK_PERSONAL | RISK_DATALOSS,
        'captype' => 'read',
        'contextlevel' => CONTEXT_MODULE,
        'archetypes' => [
            'manager' => CAP_ALLOW,
        ],
    ],
];

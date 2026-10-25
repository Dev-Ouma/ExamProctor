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
 * Web service functions for local_examproctor (reference photo CRUD for the admissions system).
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$functions = [
    'local_examproctor_refphoto_save' => [
        'classname' => \local_examproctor\external\refphoto_save::class,
        'description' => 'Create or replace a student reference photo.',
        'type' => 'write',
        'capabilities' => 'local/examproctor:managerefphotos',
    ],
    'local_examproctor_refphoto_get' => [
        'classname' => \local_examproctor\external\refphoto_get::class,
        'description' => 'Get a student reference photo status.',
        'type' => 'read',
        'capabilities' => 'local/examproctor:managerefphotos',
    ],
    'local_examproctor_refphoto_delete' => [
        'classname' => \local_examproctor\external\refphoto_delete::class,
        'description' => 'Delete a student reference photo.',
        'type' => 'write',
        'capabilities' => 'local/examproctor:managerefphotos',
    ],
    'local_examproctor_refphoto_list' => [
        'classname' => \local_examproctor\external\refphoto_list::class,
        'description' => 'List reference photos by status.',
        'type' => 'read',
        'capabilities' => 'local/examproctor:managerefphotos',
    ],
];

$services = [
    'ExamProctor reference photos' => [
        'functions' => array_keys($functions),
        'restrictedusers' => 1,
        'enabled' => 0,
        'shortname' => 'local_examproctor_refphotos',
    ],
];

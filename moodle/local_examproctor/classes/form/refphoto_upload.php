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

namespace local_examproctor\form;

use local_examproctor\local\refphotos;

defined('MOODLE_INTERNAL') || die();

require_once($CFG->libdir . '/formslib.php');

/**
 * Upload one photo, or a ZIP of photos named by student identifier.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class refphoto_upload extends \moodleform {
    /**
     * Form definition.
     *
     * @return void
     */
    protected function definition(): void {
        $mform = $this->_form;
        $fields = array_combine(refphotos::IDENTIFIERS, array_map(
            fn($f) => get_string('refphoto_field_' . $f, 'local_examproctor'),
            refphotos::IDENTIFIERS
        ));
        $mform->addElement('select', 'field', get_string('refphoto_field', 'local_examproctor'), $fields);
        $mform->setDefault('field', 'idnumber');
        $mform->addElement('text', 'value', get_string('refphoto_value', 'local_examproctor'));
        $mform->setType('value', PARAM_RAW_TRIMMED);
        $mform->addHelpButton('value', 'refphoto_value', 'local_examproctor');
        $mform->addElement('filepicker', 'photo', get_string('refphoto_file', 'local_examproctor'), null, [
            'accepted_types' => ['.jpg', '.jpeg', '.png', '.zip'],
            'maxbytes' => 512 * 1024 * 1024,
        ]);
        $mform->addRule('photo', null, 'required');
        $this->add_action_buttons(false, get_string('refphoto_upload', 'local_examproctor'));
    }
}

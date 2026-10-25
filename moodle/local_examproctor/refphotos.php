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
 * Manage institutional reference photos (admission photos used for identity matching).
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

require(__DIR__ . '/../../config.php');
require_once($CFG->libdir . '/adminlib.php');

use local_examproctor\form\refphoto_upload;
use local_examproctor\local\refphotos;

admin_externalpage_setup('local_examproctor_refphotos');
$context = context_system::instance();
require_capability('local/examproctor:managerefphotos', $context);

$action = optional_param('action', '', PARAM_ALPHA);
$userid = optional_param('userid', 0, PARAM_INT);
$status = optional_param('status', '', PARAM_ALPHA);
$search = optional_param('search', '', PARAM_RAW_TRIMMED);
$page = optional_param('page', 0, PARAM_INT);
$baseurl = new moodle_url('/local/examproctor/refphotos.php', ['status' => $status, 'search' => $search]);

if ($action !== '' && $userid) {
    require_sesskey();
    if ($action === 'delete') {
        refphotos::delete($userid);
        redirect($baseurl, get_string('refphoto_deleted', 'local_examproctor'));
    }
    if ($action === 'revalidate' && refphotos::get($userid)) {
        $record = refphotos::push($userid);
        redirect($baseurl, get_string('refphoto_status_' . $record->status, 'local_examproctor'));
    }
}

$form = new refphoto_upload($baseurl);
$notice = '';
if ($data = $form->get_data()) {
    $filename = $form->get_new_filename('photo');
    $content = (string) $form->get_file_content('photo');
    if (strtolower(pathinfo($filename, PATHINFO_EXTENSION)) === 'zip') {
        $tmp = make_request_directory() . '/photos.zip';
        file_put_contents($tmp, $content);
        $result = refphotos::import_zip($tmp, $data->field, 'zip');
        $notice = get_string(
            'refphoto_zip_result',
            'local_examproctor',
            ['saved' => count($result['saved']), 'skipped' => count($result['skipped'])]
        );
        foreach (array_slice($result['skipped'], 0, 50, true) as $name => $reason) {
            $notice .= html_writer::empty_tag('br') . s($name) . ': ' . s($reason);
        }
    } else if ($user = refphotos::find_user($data->field, (string) $data->value)) {
        try {
            $record = refphotos::save((int) $user->id, $content, 'upload', true);
            $notice = get_string('refphoto_status_' . $record->status, 'local_examproctor') .
                ($record->reason ? ' (' . s($record->reason) . ')' : '');
        } catch (invalid_parameter_exception $e) {
            $notice = get_string('refphoto_badimage', 'local_examproctor');
        }
    } else {
        $notice = get_string('refphoto_nouser', 'local_examproctor');
    }
}

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('refphotos', 'local_examproctor'));
echo html_writer::tag('p', get_string('refphotos_intro', 'local_examproctor'));
if ($notice !== '') {
    echo $OUTPUT->notification($notice, 'info');
}
$counts = $DB->get_records_sql_menu('SELECT status, COUNT(1) FROM {local_examproctor_refphoto} GROUP BY status');
$summary = [];
foreach (['valid', 'invalid', 'pending', 'error'] as $s) {
    $summary[] = html_writer::link(
        new moodle_url($baseurl, ['status' => $s]),
        get_string('refphoto_status_' . $s, 'local_examproctor') . ': ' . ($counts[$s] ?? 0)
    );
}
echo html_writer::tag('p', implode(' · ', $summary) . ' · ' . html_writer::link(
    new moodle_url($baseurl, ['status' => '']),
    get_string('all')
));
$form->display();

echo html_writer::start_tag('form', ['method' => 'get', 'class' => 'form-inline mb-2']);
echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'status', 'value' => $status]);
echo html_writer::empty_tag('input', ['type' => 'text', 'name' => 'search', 'value' => $search, 'class' => 'form-control mr-2',
    'placeholder' => get_string('refphoto_search', 'local_examproctor')]);
echo html_writer::empty_tag('input', ['type' => 'submit', 'value' => get_string('search'), 'class' => 'btn btn-secondary']);
echo html_writer::end_tag('form');

$where = '1 = 1';
$params = [];
if ($status !== '') {
    $where .= ' AND p.status = :status';
    $params['status'] = $status;
}
if ($search !== '') {
    $where .= ' AND (' . $DB->sql_like('u.idnumber', ':s1', false) . ' OR ' . $DB->sql_like('u.username', ':s2', false)
        . ' OR ' . $DB->sql_like($DB->sql_fullname('u.firstname', 'u.lastname'), ':s3', false) . ')';
    $params += ['s1' => "%{$search}%", 's2' => "%{$search}%", 's3' => "%{$search}%"];
}
$perpage = 50;
$total = $DB->count_records_sql("SELECT COUNT(1) FROM {local_examproctor_refphoto} p JOIN {user} u ON u.id = p.userid
    WHERE {$where}", $params);
$rows = $DB->get_records_sql("SELECT p.*, u.firstname, u.lastname, u.idnumber, u.username, u.firstnamephonetic,
        u.lastnamephonetic, u.middlename, u.alternatename
    FROM {local_examproctor_refphoto} p JOIN {user} u ON u.id = p.userid
    WHERE {$where} ORDER BY p.timemodified DESC", $params, $page * $perpage, $perpage);

$table = new html_table();
$table->head = [get_string('refphoto_photo', 'local_examproctor'), get_string('fullname'), get_string('idnumber'),
    get_string('status'), get_string('refphoto_source', 'local_examproctor'), get_string('lastmodified'), ''];
foreach ($rows as $row) {
    $img = moodle_url::make_pluginfile_url($context->id, 'local_examproctor', 'refphoto', $row->userid, '/', 'photo.jpg');
    $actions = [];
    foreach (['revalidate', 'delete'] as $a) {
        $url = new moodle_url($baseurl, ['action' => $a, 'userid' => $row->userid, 'sesskey' => sesskey()]);
        $attrs = $a === 'delete' ? ['data-confirm' => get_string('refphoto_confirmdelete', 'local_examproctor')] : [];
        $actions[] = html_writer::link($url, get_string('refphoto_' . $a, 'local_examproctor'), $attrs);
    }
    $table->data[] = [
        html_writer::empty_tag('img', ['src' => $img, 'alt' => '', 'style' => 'max-height:64px']),
        fullname($row),
        s($row->idnumber),
        get_string('refphoto_status_' . $row->status, 'local_examproctor') . ($row->reason ? ' — ' . s($row->reason) : ''),
        s($row->source),
        userdate($row->timemodified, get_string('strftimedatetimeshort')),
        implode(' | ', $actions),
    ];
}
echo html_writer::table($table);
echo $OUTPUT->paging_bar($total, $page, $perpage, $baseurl);
echo $OUTPUT->footer();

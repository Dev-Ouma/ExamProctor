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

namespace local_examproctor\privacy;

use core_privacy\local\metadata\collection;
use core_privacy\local\request\approved_contextlist;
use core_privacy\local\request\approved_userlist;
use core_privacy\local\request\contextlist;
use core_privacy\local\request\userlist;
use core_privacy\local\request\transform;
use core_privacy\local\request\writer;
use local_examproctor\local\privacy_service;
use local_examproctor\local\refphotos;

/**
 * Privacy provider for local_examproctor.
 *
 * Covers the Moodle-side tables, reference photos and, through signed calls, the evidence the
 * ExamProctor service holds (images, events, flags, scores, reviewer decisions).
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class provider implements
    \core_privacy\local\metadata\provider,
    \core_privacy\local\request\core_userlist_provider,
    \core_privacy\local\request\plugin\provider {
    /** @var string[] Tables keyed by user and quiz. */
    private const TABLES = ['local_examproctor_ready', 'local_examproctor_attempt'];

    /**
     * Describe stored and exported data.
     *
     * @param collection $collection
     * @return collection
     */
    public static function get_metadata(collection $collection): collection {
        $collection->add_database_table('local_examproctor_ready', [
            'userid' => 'privacy:metadata:ready:userid',
            'quizid' => 'privacy:metadata:ready:quizid',
            'sessionid' => 'privacy:metadata:ready:sessionid',
            'context' => 'privacy:metadata:ready:context',
            'timecreated' => 'privacy:metadata:ready:timecreated',
        ], 'privacy:metadata:ready');
        $collection->add_database_table('local_examproctor_attempt', [
            'userid' => 'privacy:metadata:attempt:userid',
            'attemptid' => 'privacy:metadata:attempt:attemptid',
            'sessionid' => 'privacy:metadata:attempt:sessionid',
            'integrityscore' => 'privacy:metadata:attempt:integrityscore',
            'band' => 'privacy:metadata:attempt:band',
        ], 'privacy:metadata:attempt');
        $collection->add_database_table('local_examproctor_refphoto', [
            'userid' => 'privacy:metadata:refphoto:userid',
            'status' => 'privacy:metadata:refphoto:status',
            'source' => 'privacy:metadata:refphoto:source',
            'timemodified' => 'privacy:metadata:refphoto:timemodified',
        ], 'privacy:metadata:refphoto');
        $collection->add_subsystem_link('core_files', [], 'privacy:metadata:refphoto:file');
        $collection->add_external_location_link('examproctor_service', [
            'userid' => 'privacy:metadata:service:userid',
            'quizid' => 'privacy:metadata:service:quizid',
            'photo' => 'privacy:metadata:service:photo',
            'images' => 'privacy:metadata:service:images',
            'events' => 'privacy:metadata:service:events',
            'flags' => 'privacy:metadata:service:flags',
            'decisions' => 'privacy:metadata:service:decisions',
        ], 'privacy:metadata:service');
        return $collection;
    }

    /**
     * SQL selecting quiz module contexts for a table.
     *
     * @param string $table
     * @return string
     */
    private static function context_sql(string $table): string {
        return "SELECT ctx.id
                  FROM {{$table}} t
                  JOIN {course_modules} cm ON cm.instance = t.quizid
                  JOIN {modules} m ON m.id = cm.module AND m.name = 'quiz'
                  JOIN {context} ctx ON ctx.instanceid = cm.id AND ctx.contextlevel = :level
                 WHERE t.userid = :userid";
    }

    /**
     * Contexts holding data for a user.
     *
     * @param int $userid
     * @return contextlist
     */
    public static function get_contexts_for_userid(int $userid): contextlist {
        $list = new contextlist();
        foreach (self::TABLES as $table) {
            $list->add_from_sql(self::context_sql($table), ['level' => CONTEXT_MODULE, 'userid' => $userid]);
        }
        if (refphotos::get($userid)) {
            $list->add_system_context();
        }
        $quizids = privacy_service::quizzes_for_user($userid);
        if ($quizids) {
            global $DB;
            [$insql, $params] = $DB->get_in_or_equal($quizids, SQL_PARAMS_NAMED);
            $list->add_from_sql(
                "SELECT ctx.id
                   FROM {course_modules} cm
                   JOIN {modules} m ON m.id = cm.module AND m.name = 'quiz'
                   JOIN {context} ctx ON ctx.instanceid = cm.id AND ctx.contextlevel = :level
                  WHERE cm.instance {$insql}",
                $params + ['level' => CONTEXT_MODULE]
            );
        }
        return $list;
    }

    /**
     * Users with data in a context.
     *
     * @param userlist $userlist
     * @return void
     */
    public static function get_users_in_context(userlist $userlist): void {
        $context = $userlist->get_context();
        if ($context instanceof \context_system) {
            $userlist->add_from_sql('userid', 'SELECT userid FROM {local_examproctor_refphoto}', []);
            return;
        }
        if (!$context instanceof \context_module) {
            return;
        }
        $quizid = self::quizid($context);
        foreach (self::TABLES as $table) {
            $userlist->add_from_sql('userid', "SELECT userid FROM {{$table}} WHERE quizid = :quizid", ['quizid' => $quizid]);
        }
        $userlist->add_users(privacy_service::users_in_quiz($quizid));
    }

    /**
     * Export a user's records.
     *
     * @param approved_contextlist $contextlist
     * @return void
     */
    public static function export_user_data(approved_contextlist $contextlist): void {
        global $DB;
        $userid = $contextlist->get_user()->id;
        foreach ($contextlist->get_contexts() as $context) {
            if ($context instanceof \context_system && ($photo = refphotos::get((int) $userid))) {
                $path = [get_string('refphotos', 'local_examproctor')];
                writer::with_context($context)
                    ->export_data($path, (object) ['status' => $photo->status, 'reason' => $photo->reason,
                        'source' => $photo->source, 'timemodified' => transform::datetime($photo->timemodified)])
                    ->export_area_files($path, 'local_examproctor', refphotos::FILEAREA, (int) $userid);
                continue;
            }
            if (!$context instanceof \context_module || !($quizid = self::quizid($context))) {
                continue;
            }
            $attempts = $DB->get_records(
                'local_examproctor_attempt',
                ['userid' => $userid, 'quizid' => $quizid],
                'timecreated',
                'attemptid, sessionid, status, integrityscore, band, flagcount, timecreated'
            );
            $ready = $DB->get_records(
                'local_examproctor_ready',
                ['userid' => $userid, 'quizid' => $quizid],
                'timecreated',
                'id, sessionid, context, timecreated, timeused'
            );
            writer::with_context($context)->export_data(
                [get_string('pluginname', 'local_examproctor')],
                (object) ['attempts' => array_values($attempts), 'prechecks' => array_values($ready)]
            );
            self::export_service_data($context, (int) $userid, $quizid);
        }
    }

    /**
     * Delete all users' data in a context.
     *
     * @param \context $context
     * @return void
     */
    public static function delete_data_for_all_users_in_context(\context $context): void {
        global $DB;
        if ($context instanceof \context_system) {
            foreach ($DB->get_fieldset_select('local_examproctor_refphoto', 'userid', '1 = 1') as $userid) {
                refphotos::delete((int) $userid);
            }
            return;
        }
        if ($context instanceof \context_module && ($quizid = self::quizid($context))) {
            foreach (privacy_service::users_in_quiz($quizid) as $userid) {
                privacy_service::erase($userid, $quizid);
            }
            foreach (self::TABLES as $table) {
                $DB->delete_records($table, ['quizid' => $quizid]);
            }
        }
    }

    /**
     * Delete one user's data in the approved contexts.
     *
     * @param approved_contextlist $contextlist
     * @return void
     */
    public static function delete_data_for_user(approved_contextlist $contextlist): void {
        global $DB;
        $userid = $contextlist->get_user()->id;
        foreach ($contextlist->get_contexts() as $context) {
            if ($context instanceof \context_system) {
                refphotos::delete((int) $userid);
            }
            if ($context instanceof \context_module && ($quizid = self::quizid($context))) {
                privacy_service::erase((int) $userid, $quizid);
                foreach (self::TABLES as $table) {
                    $DB->delete_records($table, ['quizid' => $quizid, 'userid' => $userid]);
                }
            }
        }
    }

    /**
     * Delete several users' data in one context.
     *
     * @param approved_userlist $userlist
     * @return void
     */
    public static function delete_data_for_users(approved_userlist $userlist): void {
        global $DB;
        $context = $userlist->get_context();
        if ($context instanceof \context_system) {
            foreach ($userlist->get_userids() as $userid) {
                refphotos::delete((int) $userid);
            }
            return;
        }
        if (!$context instanceof \context_module || !($quizid = self::quizid($context)) || !$userlist->get_userids()) {
            return;
        }
        foreach ($userlist->get_userids() as $userid) {
            privacy_service::erase((int) $userid, $quizid);
        }
        [$insql, $params] = $DB->get_in_or_equal($userlist->get_userids(), SQL_PARAMS_NAMED);
        $params['quizid'] = $quizid;
        foreach (self::TABLES as $table) {
            $DB->delete_records_select($table, "quizid = :quizid AND userid {$insql}", $params);
        }
    }

    /**
     * Export what the service holds for a user in one quiz: session data as JSON, images as files.
     *
     * @param \context_module $context
     * @param int $userid
     * @param int $quizid
     * @return void
     */
    private static function export_service_data(\context_module $context, int $userid, int $quizid): void {
        $base = [get_string('pluginname', 'local_examproctor'), get_string('privacy:export:service', 'local_examproctor')];
        foreach (privacy_service::export($userid, $quizid) as $session) {
            $path = array_merge($base, [clean_param($session['session_id'] ?? '', PARAM_ALPHANUMEXT)]);
            $uploads = $session['uploads'] ?? [];
            $session['uploads'] = [];
            foreach ($uploads as $upload) {
                $name = clean_filename(sprintf('%s-%06d.jpg', $upload['kind'] ?? 'image', (int) ($upload['seq'] ?? 0)));
                if (!empty($upload['jpeg_base64'])) {
                    writer::with_context($context)->export_custom_file($path, $name, base64_decode($upload['jpeg_base64']));
                }
                unset($upload['jpeg_base64']);
                $session['uploads'][] = $upload + ['file' => $name];
            }
            writer::with_context($context)->export_data($path, (object) $session);
        }
    }

    /**
     * Quiz id for a quiz module context, or 0.
     *
     * @param \context_module $context
     * @return int
     */
    private static function quizid(\context_module $context): int {
        $cm = get_coursemodule_from_id('quiz', $context->instanceid);
        return $cm ? (int) $cm->instance : 0;
    }
}

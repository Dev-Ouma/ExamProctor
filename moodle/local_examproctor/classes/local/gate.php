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

namespace local_examproctor\local;

/**
 * Ready records: written by the signed session.ready webhook, consumed when the attempt starts.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class gate {
    /**
     * Record that the service has passed this user's pre-checks for this quiz.
     *
     * @param int $userid Moodle user id.
     * @param int $quizid quiz id.
     * @param string $sessionid service session id.
     * @param array $policy policy the service checked.
     * @param array $context pre-check context (gaps).
     * @param int|null $now current time, for tests.
     * @return void
     */
    public static function record_ready(
        int $userid,
        int $quizid,
        string $sessionid,
        array $policy,
        array $context = [],
        ?int $now = null
    ): void {
        global $DB;
        $now = $now ?? time();
        if ($DB->record_exists('local_examproctor_ready', ['sessionid' => $sessionid])) {
            return; // Webhook retried after Moodle already stored it.
        }
        $DB->insert_record('local_examproctor_ready', (object) [
            'userid' => $userid,
            'quizid' => $quizid,
            'sessionid' => $sessionid,
            'policy' => json_encode($policy),
            'context' => json_encode($context),
            'timecreated' => $now,
            'timeexpires' => $now + config::READY_TTL,
        ]);
    }

    /**
     * Newest unused, unexpired ready record for a user and quiz.
     *
     * @param int $userid Moodle user id.
     * @param int $quizid quiz id.
     * @param int|null $now current time, for tests.
     * @return \stdClass|null
     */
    public static function find_ready(int $userid, int $quizid, ?int $now = null): ?\stdClass {
        global $DB;
        $records = $DB->get_records_select(
            'local_examproctor_ready',
            'userid = ? AND quizid = ? AND timeused IS NULL AND timeexpires >= ?',
            [$userid, $quizid, $now ?? time()],
            'timecreated DESC, id DESC',
            '*',
            0,
            1
        );
        return $records ? reset($records) : null;
    }

    /**
     * Use the ready record for a new attempt and freeze its policy onto the attempt.
     *
     * @param int $attemptid quiz attempt id.
     * @param int $userid attempt owner.
     * @param int $quizid quiz id.
     * @param int|null $now current time, for tests.
     * @return bool true if a ready record was consumed.
     */
    public static function link_attempt(int $attemptid, int $userid, int $quizid, ?int $now = null): bool {
        global $DB;
        $now = $now ?? time();
        $ready = self::find_ready($userid, $quizid, $now);
        if (!$ready || $DB->record_exists('local_examproctor_attempt', ['attemptid' => $attemptid])) {
            return false;
        }
        $DB->set_field('local_examproctor_ready', 'timeused', $now, ['id' => $ready->id]);
        $DB->insert_record('local_examproctor_attempt', (object) [
            'attemptid' => $attemptid,
            'quizid' => $quizid,
            'userid' => $userid,
            'sessionid' => $ready->sessionid,
            'policy' => $ready->policy,
            'status' => 'started',
            'timecreated' => $now,
            'timemodified' => $now,
        ]);
        return true;
    }
}

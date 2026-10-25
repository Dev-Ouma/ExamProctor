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
 * Privacy API requests for evidence the ExamProctor service holds (images, events, flags, scores,
 * reviewer decisions). Failures throw, so a data request is retried rather than reported done.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class privacy_service {
    /** @var service_client|null client, replaceable in tests. */
    public static ?service_client $client = null;

    /**
     * Send one signed call and return the decoded body.
     *
     * @param string $method HTTP method.
     * @param string $path path with query string.
     * @return array
     */
    private static function call(string $method, string $path): array {
        $client = self::$client ?? new service_client();
        [$status, $body] = $client->request($method, $path);
        if ($status !== 200) {
            throw new \moodle_exception('privacy_service_failed', 'local_examproctor', '', $status);
        }
        return $body;
    }

    /**
     * Is the service configured? Without it there is nothing held remotely to find.
     *
     * @return bool
     */
    public static function available(): bool {
        return config::service_url() !== '' && config::signing_key() !== '';
    }

    /**
     * Quiz ids for which the service holds data about a user.
     *
     * @param int $userid
     * @return int[]
     */
    public static function quizzes_for_user(int $userid): array {
        if (!self::available()) {
            return [];
        }
        return array_map('intval', self::call('GET', "/v1/admin/privacy/users/{$userid}/quizzes")['quiz_ids'] ?? []);
    }

    /**
     * User ids with data in one quiz.
     *
     * @param int $quizid
     * @return int[]
     */
    public static function users_in_quiz(int $quizid): array {
        if (!self::available()) {
            return [];
        }
        return array_map('intval', self::call('GET', "/v1/admin/privacy/quizzes/{$quizid}/users")['user_ids'] ?? []);
    }

    /**
     * Everything held about a user in one quiz.
     *
     * @param int $userid
     * @param int $quizid
     * @return array list of sessions.
     */
    public static function export(int $userid, int $quizid): array {
        if (!self::available()) {
            return [];
        }
        return self::call('GET', "/v1/admin/privacy/users/{$userid}?quiz_id={$quizid}")['sessions'] ?? [];
    }

    /**
     * Erase a user's data in one quiz. Sessions under legal hold are kept.
     *
     * @param int $userid
     * @param int $quizid
     * @return array{erased: string[], held: string[]}
     */
    public static function erase(int $userid, int $quizid): array {
        if (!self::available()) {
            return ['erased' => [], 'held' => []];
        }
        $body = self::call('DELETE', "/v1/admin/privacy/users/{$userid}?quiz_id={$quizid}");
        if (!empty($body['held'])) {
            debugging("ExamProctor: sessions on legal hold kept for user {$userid}: " . implode(', ', $body['held']), DEBUG_NORMAL);
        }
        return ['erased' => $body['erased'] ?? [], 'held' => $body['held'] ?? []];
    }
}

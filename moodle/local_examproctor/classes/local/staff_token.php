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

use Firebase\JWT\JWT;

/**
 * Mints the token a reviewer's browser uses to read one quiz's proctoring evidence.
 *
 * Moodle decides who may review; the token carries only the capabilities Moodle granted, for one
 * quiz, for one hour. The service never trusts a caller-supplied course or quiz id.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class staff_token {
    /**
     * Service capabilities for a user in a quiz context.
     *
     * Reviewers may view and record decisions; exporting evidence and live invigilation are
     * separate capabilities.
     *
     * @param \context_module $context quiz context.
     * @param int|null $userid user, default the current user.
     * @return string[] subset of review, decide, exportevidence, invigilate.
     */
    public static function caps(\context_module $context, ?int $userid = null): array {
        $caps = [];
        if (has_capability('local/examproctor:review', $context, $userid)) {
            $caps[] = 'review';
            $caps[] = 'decide';
        }
        if ($caps && has_capability('local/examproctor:exportevidence', $context, $userid)) {
            $caps[] = 'exportevidence';
        }
        if (has_capability('local/examproctor:invigilate', $context, $userid)) {
            $caps[] = 'invigilate';
        }
        return $caps;
    }

    /**
     * Build a signed staff token.
     *
     * @param \stdClass $user staff user (needs id and name fields).
     * @param \stdClass $quiz quiz record (needs id, course).
     * @param string[] $caps capabilities from {@see self::caps()}.
     * @param int|null $now current time, for tests.
     * @return string compact JWT.
     */
    public static function mint(\stdClass $user, \stdClass $quiz, array $caps, ?int $now = null): string {
        global $CFG;
        $now = $now ?? time();
        $claims = [
            'iss' => $CFG->wwwroot,
            'aud' => config::STAFF_AUDIENCE,
            'sub' => (string) $user->id,
            'name' => fullname($user),
            'course_id' => (int) $quiz->course,
            'quiz_id' => (int) $quiz->id,
            'caps' => array_values($caps),
            'iat' => $now,
            'exp' => $now + config::STAFF_TOKEN_TTL,
        ];
        return JWT::encode($claims, config::signing_key(), 'HS256');
    }
}

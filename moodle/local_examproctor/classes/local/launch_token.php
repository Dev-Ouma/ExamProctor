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
 * Mints the short-lived, single-use launch token the browser trades for a proctoring session.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class launch_token {
    /**
     * Build a signed launch token.
     *
     * @param int $userid Moodle user id.
     * @param \stdClass $quiz quiz record (needs id, course).
     * @param int $cmid course module id.
     * @param array $policy proctoring policy for this quiz.
     * @param int|null $now current time, for tests.
     * @return string compact JWT.
     */
    public static function mint(int $userid, \stdClass $quiz, int $cmid, array $policy, ?int $now = null): string {
        global $CFG;
        $now = $now ?? time();
        $claims = [
            'iss' => $CFG->wwwroot,
            'aud' => config::LAUNCH_AUDIENCE,
            'sub' => (string) $userid,
            'course_id' => (int) $quiz->course,
            'cmid' => $cmid,
            'quiz_id' => (int) $quiz->id,
            'attempt_id' => null,
            'policy' => $policy,
            'iat' => $now,
            'exp' => $now + config::LAUNCH_TOKEN_TTL,
            'jti' => random_string(32),
        ];
        return JWT::encode($claims, config::signing_key(), 'HS256');
    }
}

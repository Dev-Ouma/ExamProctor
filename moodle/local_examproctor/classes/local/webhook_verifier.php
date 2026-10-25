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
 * Verifies signed webhooks from the ExamProctor service: HMAC, timestamp window and one-time nonce.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class webhook_verifier {
    /**
     * Check a webhook. Records the nonce on success so a replay is rejected.
     *
     * @param string $timestamp X-ExamProctor-Timestamp header.
     * @param string $nonce X-ExamProctor-Nonce header.
     * @param string $signature X-ExamProctor-Signature header (hex HMAC-SHA256).
     * @param string $body raw request body.
     * @param int|null $now current time, for tests.
     * @return string|null null when valid, else a short reason code.
     */
    public static function verify(string $timestamp, string $nonce, string $signature, string $body,
            ?int $now = null): ?string {
        global $DB;
        $now = $now ?? time();
        $key = config::signing_key();
        if ($key === '') {
            return 'not_configured';
        }
        if (!ctype_digit($timestamp) || abs($now - (int) $timestamp) > config::WEBHOOK_MAX_SKEW) {
            return 'stale';
        }
        if (!preg_match('/^[a-f0-9]{16,64}$/', $nonce)) {
            return 'bad_nonce';
        }
        $expected = hash_hmac('sha256', "{$timestamp}.{$nonce}.{$body}", $key);
        if (!hash_equals($expected, strtolower($signature))) {
            return 'bad_signature';
        }
        $DB->delete_records_select('local_examproctor_nonce', 'timeexpires < ?', [$now]);
        try {
            $DB->insert_record('local_examproctor_nonce', (object) [
                'nonce' => $nonce,
                'timeexpires' => $now + 2 * config::WEBHOOK_MAX_SKEW,
            ]);
        } catch (\dml_write_exception $e) {
            return 'replay';
        }
        return null;
    }
}

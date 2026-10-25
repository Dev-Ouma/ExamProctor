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
 * Signed server-to-server calls from Moodle to the ExamProctor service.
 *
 * Signature: HMAC-SHA256 with the shared signing key over "<ts>.<nonce>.<METHOD> <path> <sha256(body)>".
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class service_client {
    /**
     * Send a signed request.
     *
     * @param string $method HTTP method.
     * @param string $path path starting with /v1/.
     * @param string $body raw body.
     * @param string $contenttype body content type.
     * @return array{0: int, 1: array} HTTP status and decoded JSON.
     */
    public function request(string $method, string $path, string $body = '', string $contenttype = 'application/json'): array {
        global $CFG;
        require_once($CFG->libdir . '/filelib.php');
        $ts = (string) time();
        $nonce = bin2hex(random_bytes(16));
        $canonical = $method . ' ' . $path . ' ' . hash('sha256', $body);
        $signature = hash_hmac('sha256', "{$ts}.{$nonce}.{$canonical}", config::signing_key());
        // The service URL is set by a site admin and is often a private address, so Moodle's
        // outbound-host block list must not apply to it.
        $curl = new \curl(['ignoresecurity' => true]);
        $curl->setHeader([
            'Content-Type: ' . $contenttype,
            'X-ExamProctor-Timestamp: ' . $ts,
            'X-ExamProctor-Nonce: ' . $nonce,
            'X-ExamProctor-Signature: ' . $signature,
        ]);
        $url = config::internal_url() . $path;
        $options = ['CURLOPT_TIMEOUT' => 30, 'CURLOPT_CUSTOMREQUEST' => $method];
        $raw = $method === 'GET' ? $curl->get($url, [], $options) : $curl->post($url, $body, $options);
        $status = (int) ($curl->get_info()['http_code'] ?? 0);
        return [$status, (array) json_decode((string) $raw, true)];
    }
}

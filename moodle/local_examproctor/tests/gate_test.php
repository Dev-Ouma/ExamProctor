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

namespace local_examproctor;

use Firebase\JWT\JWT;
use Firebase\JWT\Key;
use local_examproctor\local\config;
use local_examproctor\local\gate;
use local_examproctor\local\launch_token;
use local_examproctor\local\webhook_verifier;

/**
 * Launch token, webhook verification and ready-record tests.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 * @covers     \local_examproctor\local\launch_token
 * @covers     \local_examproctor\local\webhook_verifier
 * @covers     \local_examproctor\local\gate
 */
final class gate_test extends \advanced_testcase {
    /** @var string Fixed, obviously fake signing key for these tests. */
    private const KEY = 'kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk';

    protected function setUp(): void {
        parent::setUp();
        $this->resetAfterTest();
        set_config('signingkey', self::KEY, 'local_examproctor');
        set_config('serviceurl', 'https://proctor.example.invalid', 'local_examproctor');
    }

    /**
     * Build a signed webhook header set.
     *
     * @param string $body
     * @param int $timestamp
     * @param string $nonce
     * @return array
     */
    private function signed(string $body, int $timestamp, string $nonce): array {
        return [(string) $timestamp, $nonce, hash_hmac('sha256', "{$timestamp}.{$nonce}.{$body}", self::KEY), $body];
    }

    public function test_launch_token_claims(): void {
        global $CFG;
        $quiz = (object) ['id' => 5, 'course' => 3];
        $token = launch_token::mint(42, $quiz, 9, ['camera' => true], 1000);

        JWT::$timestamp = 1001;
        $claims = (array) JWT::decode($token, new Key(self::KEY, 'HS256'));
        JWT::$timestamp = null;

        $this->assertSame($CFG->wwwroot, $claims['iss']);
        $this->assertSame('examproctor-service', $claims['aud']);
        $this->assertSame('42', $claims['sub']);
        $this->assertSame(9, $claims['cmid']);
        $this->assertSame(5, $claims['quiz_id']);
        $this->assertSame(1120, $claims['exp']);
        $this->assertSame(32, strlen($claims['jti']));
    }

    public function test_valid_webhook_is_accepted_once(): void {
        $args = $this->signed('{"event":"x"}', 5000, str_repeat('a', 32));

        $this->assertNull(webhook_verifier::verify(...$args, ...[5010]));
        $this->assertSame('replay', webhook_verifier::verify(...$args, ...[5020]));
    }

    public function test_stale_or_tampered_webhooks_are_rejected(): void {
        [$ts, $nonce, $sig, $body] = $this->signed('{"event":"x"}', 5000, str_repeat('b', 32));

        $this->assertSame('stale', webhook_verifier::verify($ts, $nonce, $sig, $body, 5000 + config::WEBHOOK_MAX_SKEW + 1));
        $this->assertSame('bad_signature', webhook_verifier::verify($ts, $nonce, $sig, '{"event":"y"}', 5000));
        $this->assertSame('bad_nonce', webhook_verifier::verify($ts, 'not hex!', $sig, $body, 5000));
    }

    public function test_ready_record_expires_and_is_single_use(): void {
        $gen = $this->getDataGenerator();
        $user = $gen->create_user();
        $quiz = $gen->create_module('quiz', ['course' => $gen->create_course()->id]);
        gate::record_ready((int) $user->id, (int) $quiz->id, 'sess-1', ['camera' => true], [], 1000);
        gate::record_ready((int) $user->id, (int) $quiz->id, 'sess-1', ['camera' => true], [], 1001);

        $this->assertSame(1, $this->count_ready());
        $this->assertNull(gate::find_ready((int) $user->id, (int) $quiz->id, 1000 + config::READY_TTL + 1));
        $this->assertTrue(gate::link_attempt(77, (int) $user->id, (int) $quiz->id, 1100));
        $this->assertFalse(gate::link_attempt(78, (int) $user->id, (int) $quiz->id, 1101));
    }

    /**
     * Number of ready records.
     *
     * @return int
     */
    private function count_ready(): int {
        global $DB;
        return $DB->count_records('local_examproctor_ready');
    }

    public function test_is_active_needs_url_strong_key_and_no_kill_switch(): void {
        $this->assertTrue(config::is_active());
        set_config('killswitch', 1, 'local_examproctor');
        $this->assertFalse(config::is_active());
        set_config('killswitch', 0, 'local_examproctor');
        set_config('signingkey', 'short', 'local_examproctor');
        $this->assertFalse(config::is_active());
    }
}

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
 * Read access to ExamProctor site settings.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class config {
    /** @var int Seconds a launch token is valid. Spec: at most 120. */
    public const LAUNCH_TOKEN_TTL = 120;

    /** @var int Seconds a ready record may wait before the attempt starts. */
    public const READY_TTL = 600;

    /** @var int Accepted clock difference for webhook timestamps, in seconds. */
    public const WEBHOOK_MAX_SKEW = 300;

    /** @var string Audience the service expects in launch tokens. */
    public const LAUNCH_AUDIENCE = 'examproctor-service';

    /**
     * Is ExamProctor configured and not switched off for the whole site?
     *
     * @return bool
     */
    public static function is_active(): bool {
        return !self::kill_switch_on() && self::service_url() !== '' && strlen(self::signing_key()) >= 32;
    }

    /**
     * Is the site-wide kill switch on?
     *
     * @return bool
     */
    public static function kill_switch_on(): bool {
        return (bool) get_config('local_examproctor', 'killswitch');
    }

    /**
     * Service base URL for browsers, without a trailing slash.
     *
     * @return string
     */
    public static function service_url(): string {
        return rtrim((string) get_config('local_examproctor', 'serviceurl'), '/');
    }

    /**
     * Shared secret for launch tokens and webhooks.
     *
     * @return string
     */
    public static function signing_key(): string {
        return (string) get_config('local_examproctor', 'signingkey');
    }
}

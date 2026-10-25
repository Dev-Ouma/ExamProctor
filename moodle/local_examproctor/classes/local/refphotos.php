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
 * Institutional reference photos: create, read, update, delete.
 *
 * OUK collects student photos with consent at admission. Moodle keeps the copy of record in its
 * file storage; each photo is pushed to the ExamProctor service, which validates it (one face,
 * large enough, sharp, bright) and keeps a face embedding for identity matching.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class refphotos {
    /** @var int Largest accepted photo, bytes. */
    public const MAX_BYTES = 2000000;

    /** @var string File area. */
    public const FILEAREA = 'refphoto';

    /** @var string[] Accepted ways to identify a student. */
    public const IDENTIFIERS = ['id', 'username', 'idnumber', 'email'];

    /** @var service_client|null Injected client, for tests. */
    public static ?service_client $client = null;

    /**
     * Find a user by one identifier.
     *
     * @param string $field one of IDENTIFIERS.
     * @param string $value value to match.
     * @return \stdClass|null
     */
    public static function find_user(string $field, string $value): ?\stdClass {
        global $DB;
        if (!in_array($field, self::IDENTIFIERS, true) || trim($value) === '') {
            return null;
        }
        $users = $DB->get_records('user', [$field => trim($value), 'deleted' => 0], 'id', 'id, username, idnumber', 0, 2);
        return count($users) === 1 ? reset($users) : null; // Ambiguous matches are refused.
    }

    /**
     * Create or replace a user's photo. JPEG or PNG; PNG is converted to JPEG.
     *
     * @param int $userid
     * @param string $bytes image data.
     * @param string $source upload|zip|cli|api.
     * @param bool $syncnow push to the service now (single uploads) or queue it (bulk).
     * @return \stdClass the photo record.
     */
    public static function save(int $userid, string $bytes, string $source, bool $syncnow = true): \stdClass {
        global $DB, $USER;
        $jpeg = self::to_jpeg($bytes);
        $context = \context_system::instance();
        $fs = get_file_storage();
        $fs->delete_area_files($context->id, 'local_examproctor', self::FILEAREA, $userid);
        $file = $fs->create_file_from_string([
            'contextid' => $context->id,
            'component' => 'local_examproctor',
            'filearea' => self::FILEAREA,
            'itemid' => $userid,
            'filepath' => '/',
            'filename' => 'photo.jpg',
            'userid' => $USER->id ?? null,
        ], $jpeg);
        $now = time();
        $record = $DB->get_record('local_examproctor_refphoto', ['userid' => $userid]) ?: (object) [
            'userid' => $userid,
            'timecreated' => $now,
        ];
        $record->contenthash = $file->get_contenthash();
        $record->source = $source;
        $record->status = 'pending';
        $record->reason = null;
        $record->facepx = null;
        $record->timemodified = $now;
        $record->timesynced = null;
        if (empty($record->id)) {
            $record->id = $DB->insert_record('local_examproctor_refphoto', $record);
        } else {
            $DB->update_record('local_examproctor_refphoto', $record);
        }
        if ($syncnow) {
            return self::push($userid);
        }
        $task = new \local_examproctor\task\push_refphoto();
        $task->set_custom_data(['userid' => $userid]);
        \core\task\manager::queue_adhoc_task($task, true);
        return $record;
    }

    /**
     * Validate and normalise image bytes to JPEG.
     *
     * @param string $bytes
     * @return string JPEG bytes.
     * @throws \invalid_parameter_exception
     */
    public static function to_jpeg(string $bytes): string {
        if ($bytes === '' || strlen($bytes) > self::MAX_BYTES) {
            throw new \invalid_parameter_exception('Photo must be between 1 byte and ' . self::MAX_BYTES . ' bytes');
        }
        $info = @getimagesizefromstring($bytes);
        if (!$info || !in_array($info[2], [IMAGETYPE_JPEG, IMAGETYPE_PNG], true)) {
            throw new \invalid_parameter_exception('Photo must be a JPEG or PNG image');
        }
        if ($info[2] === IMAGETYPE_JPEG) {
            return $bytes;
        }
        $image = imagecreatefromstring($bytes);
        ob_start();
        imagejpeg($image, null, 90);
        return (string) ob_get_clean();
    }

    /**
     * Send the stored photo to the service and record its verdict.
     *
     * @param int $userid
     * @return \stdClass the updated record.
     */
    public static function push(int $userid): \stdClass {
        global $DB;
        $record = $DB->get_record('local_examproctor_refphoto', ['userid' => $userid], '*', MUST_EXIST);
        $file = self::file($userid);
        $client = self::$client ?? new service_client();
        [$status, $body] = $file
            ? $client->request('PUT', "/v1/admin/reference-photos/{$userid}", $file->get_content(), 'image/jpeg')
            : [0, []];
        if ($status === 200 && in_array($body['status'] ?? '', ['valid', 'invalid'], true)) {
            $record->status = $body['status'];
            $record->reason = $body['reason'] ?? null;
            $record->facepx = isset($body['face_px']) ? (int) $body['face_px'] : null;
            $record->timesynced = time();
        } else {
            $record->status = 'error';
            $record->reason = $file ? 'service_http_' . $status : 'file_missing';
        }
        $record->timemodified = time();
        $DB->update_record('local_examproctor_refphoto', $record);
        return $record;
    }

    /**
     * The stored file for a user, if any.
     *
     * @param int $userid
     * @return \stored_file|null
     */
    public static function file(int $userid): ?\stored_file {
        $files = get_file_storage()->get_area_files(
            \context_system::instance()->id,
            'local_examproctor',
            self::FILEAREA,
            $userid,
            'id',
            false
        );
        return $files ? reset($files) : null;
    }

    /**
     * Read one record.
     *
     * @param int $userid
     * @return \stdClass|null
     */
    public static function get(int $userid): ?\stdClass {
        global $DB;
        return $DB->get_record('local_examproctor_refphoto', ['userid' => $userid]) ?: null;
    }

    /**
     * Delete a user's photo everywhere: Moodle file, record and the service copy.
     *
     * @param int $userid
     * @return bool true if a photo existed.
     */
    public static function delete(int $userid): bool {
        global $DB;
        $existed = $DB->record_exists('local_examproctor_refphoto', ['userid' => $userid]);
        get_file_storage()->delete_area_files(\context_system::instance()->id, 'local_examproctor', self::FILEAREA, $userid);
        $DB->delete_records('local_examproctor_refphoto', ['userid' => $userid]);
        if ($existed && config::internal_url() !== '') {
            (self::$client ?? new service_client())->request('DELETE', "/v1/admin/reference-photos/{$userid}");
        }
        return $existed;
    }

    /**
     * Import photos from a ZIP whose file names are student identifiers, e.g. "OUK-2026-0001.jpg".
     *
     * @param string $zippath path to the ZIP file.
     * @param string $field identifier the file names hold.
     * @param string $source source label.
     * @return array{saved: string[], skipped: array<string, string>}
     */
    public static function import_zip(string $zippath, string $field, string $source = 'zip'): array {
        $zip = new \ZipArchive();
        if ($zip->open($zippath) !== true) {
            throw new \invalid_parameter_exception('Not a readable ZIP file');
        }
        $saved = [];
        $skipped = [];
        for ($i = 0; $i < $zip->numFiles; $i++) {
            $name = $zip->getNameIndex($i);
            if (str_ends_with($name, '/') || str_starts_with(basename($name), '.')) {
                continue;
            }
            [$ok, $reason] = self::import_one(pathinfo($name, PATHINFO_FILENAME), (string) $zip->getFromIndex($i), $field, $source);
            if ($ok) {
                $saved[] = $name;
            } else {
                $skipped[$name] = $reason;
            }
        }
        $zip->close();
        return ['saved' => $saved, 'skipped' => $skipped];
    }

    /**
     * Import one photo keyed by an identifier; queued for validation.
     *
     * @param string $identifier identifier value from the file name.
     * @param string $bytes image data.
     * @param string $field identifier type.
     * @param string $source source label.
     * @return array{0: bool, 1: string} success and a reason when skipped.
     */
    public static function import_one(string $identifier, string $bytes, string $field, string $source): array {
        $user = self::find_user($field, $identifier);
        if (!$user) {
            return [false, 'no_unique_user'];
        }
        try {
            self::save((int) $user->id, $bytes, $source, false);
        } catch (\invalid_parameter_exception $e) {
            return [false, 'bad_image'];
        }
        return [true, ''];
    }
}

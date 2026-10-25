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

use local_examproctor\external\refphoto_delete;
use local_examproctor\external\refphoto_list;
use local_examproctor\external\refphoto_save;
use local_examproctor\local\refphotos;
use local_examproctor\local\service_client;

/**
 * Reference photo CRUD tests, with the service replaced by a recording fake.
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 * @covers     \local_examproctor\local\refphotos
 * @covers     \local_examproctor\external\refphoto_save
 * @covers     \local_examproctor\external\refphoto_delete
 * @covers     \local_examproctor\external\refphoto_list
 * @covers     \local_examproctor\task\push_refphoto
 */
final class refphotos_test extends \advanced_testcase {
    /** @var array Calls the fake service received. */
    private array $calls = [];

    /** @var array Next response from the fake service. */
    private array $reply = [200, ['status' => 'valid', 'reason' => null, 'face_px' => 180]];

    protected function setUp(): void {
        parent::setUp();
        $this->resetAfterTest();
        set_config('serviceurl', 'https://proctor.example.invalid', 'local_examproctor');
        set_config('signingkey', str_repeat('k', 40), 'local_examproctor');
        $test = $this;
        refphotos::$client = new class ($test) extends service_client {
            /** @var refphotos_test */
            private $test;

            /**
             * Constructor.
             *
             * @param refphotos_test $test
             */
            public function __construct($test) {
                $this->test = $test;
            }

            /**
             * Record the call and return the scripted reply.
             *
             * @param string $method
             * @param string $path
             * @param string $body
             * @param string $contenttype
             * @return array
             */
            public function request(
                string $method,
                string $path,
                string $body = '',
                string $contenttype = 'application/json'
            ): array {
                return $this->test->record_call($method, $path, $body);
            }
        };
    }

    protected function tearDown(): void {
        refphotos::$client = null;
        parent::tearDown();
    }

    /**
     * Fake service entry point.
     *
     * @param string $method
     * @param string $path
     * @param string $body
     * @return array
     */
    public function record_call(string $method, string $path, string $body): array {
        $this->calls[] = [$method, $path, strlen($body)];
        return $this->reply;
    }

    /**
     * A small real JPEG or PNG.
     *
     * @param string $type jpeg or png
     * @return string
     */
    private function image(string $type = 'jpeg'): string {
        $img = imagecreatetruecolor(32, 32);
        ob_start();
        $type === 'png' ? imagepng($img) : imagejpeg($img);
        return (string) ob_get_clean();
    }

    public function test_save_stores_file_and_records_service_verdict(): void {
        $user = $this->getDataGenerator()->create_user(['idnumber' => 'OUK-2026-0001']);

        $record = refphotos::save((int) $user->id, $this->image(), 'upload');

        $this->assertSame('valid', $record->status);
        $this->assertSame(180, $record->facepx);
        $this->assertNotNull(refphotos::file((int) $user->id));
        $this->assertSame('PUT', $this->calls[0][0]);
        $this->assertSame("/v1/admin/reference-photos/{$user->id}", $this->calls[0][1]);
    }

    public function test_invalid_verdict_and_service_errors_are_recorded(): void {
        $user = $this->getDataGenerator()->create_user();
        $this->reply = [200, ['status' => 'invalid', 'reason' => 'multiple_faces', 'face_px' => 150]];
        $this->assertSame('multiple_faces', refphotos::save((int) $user->id, $this->image(), 'upload')->reason);

        $this->reply = [0, []];
        $record = refphotos::save((int) $user->id, $this->image(), 'upload');
        $this->assertSame(['error', 'service_http_0'], [$record->status, $record->reason]);
    }

    public function test_png_is_converted_and_non_images_are_refused(): void {
        $this->assertSame(IMAGETYPE_JPEG, getimagesizefromstring(refphotos::to_jpeg($this->image('png')))[2]);
        $this->expectException(\invalid_parameter_exception::class);
        refphotos::to_jpeg('%PDF-1.7 not an image');
    }

    public function test_ambiguous_identifiers_match_nobody(): void {
        $this->getDataGenerator()->create_user(['idnumber' => 'DUP']);
        $this->getDataGenerator()->create_user(['idnumber' => 'DUP']);
        $this->assertNull(refphotos::find_user('idnumber', 'DUP'));
        $this->assertNull(refphotos::find_user('firstname', 'x'));
    }

    public function test_zip_import_queues_photos_then_cron_validates_them(): void {
        $a = $this->getDataGenerator()->create_user(['idnumber' => 'OUK-1']);
        $this->getDataGenerator()->create_user(['idnumber' => 'OUK-2']);
        $zippath = make_request_directory() . '/photos.zip';
        $zip = new \ZipArchive();
        $zip->open($zippath, \ZipArchive::CREATE);
        $zip->addFromString('OUK-1.jpg', $this->image());
        $zip->addFromString('OUK-2.png', $this->image('png'));
        $zip->addFromString('NOBODY.jpg', $this->image());
        $zip->addFromString('OUK-1-notes.txt', 'x');
        $zip->close();

        $result = refphotos::import_zip($zippath, 'idnumber');

        $this->assertEqualsCanonicalizing(['OUK-1.jpg', 'OUK-2.png'], $result['saved']);
        $this->assertSame(['NOBODY.jpg' => 'no_unique_user', 'OUK-1-notes.txt' => 'no_unique_user'], $result['skipped']);
        $this->assertSame('pending', refphotos::get((int) $a->id)->status);
        $this->assertSame([], $this->calls);

        $this->runAdhocTasks(task\push_refphoto::class);

        $this->assertCount(2, $this->calls);
        $this->assertSame('valid', refphotos::get((int) $a->id)->status);
    }

    public function test_delete_removes_everything_and_tells_the_service(): void {
        $user = $this->getDataGenerator()->create_user();
        refphotos::save((int) $user->id, $this->image(), 'upload');

        $this->assertTrue(refphotos::delete((int) $user->id));

        $this->assertNull(refphotos::get((int) $user->id));
        $this->assertNull(refphotos::file((int) $user->id));
        $this->assertSame('DELETE', end($this->calls)[0]);
        $this->assertFalse(refphotos::delete((int) $user->id));
    }

    public function test_deleting_the_moodle_user_deletes_the_photo(): void {
        $user = $this->getDataGenerator()->create_user();
        refphotos::save((int) $user->id, $this->image(), 'upload');

        delete_user($user);

        $this->assertNull(refphotos::get((int) $user->id));
    }

    public function test_web_services_need_the_capability_and_round_trip(): void {
        $student = $this->getDataGenerator()->create_user(['idnumber' => 'OUK-9']);
        $this->setUser($this->getDataGenerator()->create_user());
        try {
            refphoto_save::execute('idnumber', 'OUK-9', base64_encode($this->image()));
            $this->fail('capability not enforced');
        } catch (\required_capability_exception $e) {
            $this->assertSame('nopermissions', $e->errorcode);
        }

        $this->setAdminUser();
        $saved = refphoto_save::execute('idnumber', 'OUK-9', base64_encode($this->image()));
        $listed = refphoto_list::execute('valid');
        $deleted = refphoto_delete::execute('idnumber', 'OUK-9');

        $this->assertSame([(int) $student->id, 'valid'], [$saved['userid'], $saved['status']]);
        $this->assertSame([(int) $student->id], array_column($listed['photos'], 'userid'));
        $this->assertTrue($deleted['deleted']);
    }
}

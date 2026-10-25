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

/**
 * Bulk import of admission photos from a folder. File names are student identifiers.
 *
 * Example: php local/examproctor/cli/import_refphotos.php --dir=/srv/admissions/photos --match=idnumber
 *
 * @package    local_examproctor
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

define('CLI_SCRIPT', true);

require(__DIR__ . '/../../../config.php');
require_once($CFG->libdir . '/clilib.php');

use local_examproctor\local\refphotos;

[$options, $unrecognised] = cli_get_params(
    ['dir' => '', 'match' => 'idnumber', 'dry-run' => false, 'limit' => 0, 'help' => false],
    ['h' => 'help', 'n' => 'dry-run']
);

if ($options['help'] || $options['dir'] === '' || !in_array($options['match'], refphotos::IDENTIFIERS, true)) {
    cli_writeln("Import student reference photos.

Options:
  --dir=PATH        Folder of .jpg/.jpeg/.png files named by student identifier
  --match=FIELD     Identifier in file names: idnumber (default), username, email or id
  --limit=N         Stop after N files (0 = all)
  -n, --dry-run     Report matches without saving
  -h, --help        This help

Photos are queued; cron validates them with the ExamProctor service.");
    exit($options['help'] ? 0 : 2);
}

$files = glob(rtrim($options['dir'], '/') . '/*.{jpg,jpeg,png,JPG,JPEG,PNG}', GLOB_BRACE) ?: [];
$saved = $skipped = 0;
foreach ($files as $i => $path) {
    if ($options['limit'] && $i >= (int) $options['limit']) {
        break;
    }
    $identifier = pathinfo($path, PATHINFO_FILENAME);
    if ($options['dry-run']) {
        $ok = refphotos::find_user($options['match'], $identifier) !== null;
        $reason = $ok ? '' : 'no_unique_user';
    } else {
        [$ok, $reason] = refphotos::import_one($identifier, (string) file_get_contents($path), $options['match'], 'cli');
    }
    $ok ? $saved++ : $skipped++;
    if (!$ok) {
        cli_writeln("skip {$identifier}: {$reason}");
    }
}
cli_writeln(($options['dry-run'] ? 'Would import' : 'Imported') . " {$saved}, skipped {$skipped}, of " . count($files) . ' files.');

<?php  // Staging config: every value comes from the container environment.
unset($CFG);
global $CFG;
$CFG = new stdClass();

$CFG->dbtype    = 'pgsql';
$CFG->dblibrary = 'native';
$CFG->dbhost    = getenv('MOODLE_DB_HOST');
$CFG->dbname    = getenv('MOODLE_DB_NAME');
$CFG->dbuser    = getenv('MOODLE_DB_USER');
$CFG->dbpass    = getenv('MOODLE_DB_PASSWORD');
$CFG->prefix    = 'mdl_';
$CFG->dboptions = ['dbport' => 5432];

$CFG->wwwroot   = getenv('MOODLE_WWWROOT');
$CFG->dataroot  = '/var/moodledata';
$CFG->admin     = 'admin';
$CFG->directorypermissions = 02777;

// PHPUnit (run inside this container by `make test-moodle`).
$CFG->phpunit_prefix   = 'phpu_';
$CFG->phpunit_dataroot = '/var/moodledata/phpunit';

// Staging only: no outbound mail, verbose errors.
$CFG->noemailever = true;
$CFG->debug = E_ALL;
$CFG->debugdisplay = 1;

require_once(__DIR__ . '/lib/setup.php');

<?php
// Seed synthetic staging data: one course, one quiz with questions, students and staff roles.
// Idempotent: re-running leaves existing records in place. Synthetic names only.
// Run: make seed (php /opt/seed/seed.php as www-data inside the moodle container).

define('CLI_SCRIPT', true);
require('/var/www/html/config.php');
require_once($CFG->libdir . '/testing/generator/lib.php');
require_once($CFG->dirroot . '/user/lib.php');
require_once($CFG->dirroot . '/mod/quiz/locallib.php');

$gen = new testing_data_generator();
\core\session\manager::set_user(get_admin());

const COURSE_SHORTNAME = 'EP-STAGING-101';
const STUDENTS = 20;

$course = $DB->get_record('course', ['shortname' => COURSE_SHORTNAME]);
if (!$course) {
    $course = $gen->create_course([
        'fullname' => 'ExamProctor Staging 101',
        'shortname' => COURSE_SHORTNAME,
        'summary' => 'Synthetic course for ExamProctor testing. No real student data.',
    ]);
    mtrace('Created course ' . COURSE_SHORTNAME);
}

$people = [['epteacher', 'editingteacher', 'Teacher'], ['epinvigilator', 'teacher', 'Invigilator'],
    ['epreviewer', 'teacher', 'Reviewer']];
for ($i = 1; $i <= STUDENTS; $i++) {
    $people[] = [sprintf('epstudent%02d', $i), 'student', sprintf('Student %02d', $i)];
}
$password = getenv('SEED_USER_PASSWORD') ?: 'Staging#2026';
foreach ($people as [$username, $role, $lastname]) {
    $user = $DB->get_record('user', ['username' => $username, 'deleted' => 0]);
    if (!$user) {
        $user = $gen->create_user([
            'username' => $username, 'password' => $password,
            'firstname' => 'Synthetic', 'lastname' => $lastname,
            'email' => "{$username}@example.invalid",
        ]);
    }
    if (!is_enrolled(context_course::instance($course->id), $user)) {
        $gen->enrol_user($user->id, $course->id, $role);
    }
}
mtrace('Users enrolled: ' . count($people));

$quiz = $DB->get_record('quiz', ['course' => $course->id, 'name' => 'Proctored practice quiz']);
if (!$quiz) {
    $quiz = $gen->create_module('quiz', [
        'course' => $course->id, 'name' => 'Proctored practice quiz',
        'timelimit' => 15 * MINSECS, 'attempts' => 0, 'questionsperpage' => 1,
    ]);
    mtrace('Created quiz');
}
$quiz = $DB->get_record('quiz', ['id' => $quiz->id]);
$quiz->cmid = get_coursemodule_from_instance('quiz', $quiz->id)->id;
if (!$DB->record_exists('quiz_slots', ['quizid' => $quiz->id])) {
    // Question generator needs the PHPUnit framework; save through the question type API instead.
    $context = context_module::instance($quiz->cmid);
    // Fresh quiz: its question bank category may not exist yet.
    $category = question_get_default_category($context->id, true) ?: question_make_default_categories([$context]);
    if (empty($category->id)) {
        throw new moodle_exception('Could not create a question category for the seeded quiz');
    }
    mtrace("Question category {$category->id} in context {$context->id}");
    $qtype = question_bank::get_qtype('truefalse');
    for ($i = 1; $i <= 5; $i++) {
        $question = new stdClass();
        $question->category = $category->id;
        $question->qtype = 'truefalse';
        $question->createdby = $question->modifiedby = get_admin()->id;
        $form = (object) [
            'category' => "{$category->id},{$context->id}",
            'name' => "Synthetic statement {$i}",
            'questiontext' => ['text' => "Synthetic statement {$i} is true.", 'format' => FORMAT_HTML],
            'generalfeedback' => ['text' => '', 'format' => FORMAT_HTML],
            'defaultmark' => 1, 'penalty' => 1, 'correctanswer' => $i % 2,
            'feedbacktrue' => ['text' => '', 'format' => FORMAT_HTML],
            'feedbackfalse' => ['text' => '', 'format' => FORMAT_HTML],
            'status' => \core_question\local\bank\question_version_status::QUESTION_STATUS_READY,
        ];
        $saved = $qtype->save_question($question, $form);
        quiz_add_quiz_question($saved->id, $quiz, $i);
    }
    \mod_quiz\quiz_settings::create($quiz->id)->get_grade_calculator()->recompute_quiz_sumgrades();
    mtrace('Added 5 questions to quiz');
}
// Proctoring on: camera and screen, lenient so phones can still sit the practice quiz.
// Creating the quiz already stored a default (disabled) policy row, so update rather than insert.
$policy = ['quizid' => $quiz->id, 'enabled' => 1, 'camera' => 1, 'screen' => 1, 'identity' => 1, 'strict' => 0];
if ($existing = $DB->get_record('quizaccess_examproctor', ['quizid' => $quiz->id])) {
    $DB->update_record('quizaccess_examproctor', (object) (['id' => $existing->id] + $policy));
} else {
    $DB->insert_record('quizaccess_examproctor', (object) $policy);
}
mtrace('ExamProctor enabled on the quiz');
mtrace('Seed done. Login users: epteacher, epinvigilator, epreviewer, epstudent01..' . sprintf('%02d', STUDENTS));

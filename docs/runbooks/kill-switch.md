# Kill switch

Turns ExamProctor off for the whole site. Quizzes keep their settings; the access rule stops
applying, so students start attempts with no proctoring checks. Answers are never affected.

Rehearsed on agiledev 2026-10-25 (`staging/browser/tests/killswitch.spec.ts`): with the switch on
the quiz opened with no ExamProctor panel; with it off the pre-check returned.

## Turn on

Site administration > Plugins > Local plugins > ExamProctor > Kill switch, or:

    cd <moodle> && sudo -u www-data php admin/cli/cfg.php --component=local_examproctor --name=killswitch --set=1
    sudo -u www-data php admin/cli/purge_caches.php

Students already inside a proctored attempt keep their exam shell until they finish or reload; new
starts are unproctored. Tell invigilators and the exams office which sittings ran without
proctoring (time on, time off).

## Turn off

Same command with `--set=0`, purge caches, then smoke test one proctored quiz start.

## When to use

- The service is down and the exam must go ahead ([service-down.md](service-down.md)).
- A fault produces wrong flags or blocks students who meet the requirements.
- A policy or legal instruction to stop processing.

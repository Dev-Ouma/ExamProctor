# Deploy and roll back

Rehearsed on agiledev 2026-10-25: deploy 3 min 26 s (image build), rollback 20 s, roll forward 20 s,
health green throughout.

## Deploy

1. Outside exam windows only. Check the quiz calendar.
2. `git status` clean, tests green (`make test`, `cd service && uv run --frozen pytest ../security`).
3. `deploy/deploy.sh deploy user@host`. It copies the code, builds `examproctor-service:<commit>`,
   records the old tag as `previous_tag`, restarts `service` and `worker`, installs the plugins,
   runs Moodle's upgrade and purges caches, then waits for health.
4. Smoke: open a proctored quiz as a test student up to "All checks passed"; open the proctoring
   report as a teacher.

## Roll back the service

`deploy/deploy.sh rollback user@host` switches `service` and `worker` back to the previous image tag.
No rebuild, no data change. Schema changes are additive only, so an older service runs on the
newer database. Running it twice rolls forward again.

## Moodle plugins

Moodle cannot downgrade a plugin version. If a plugin release misbehaves, turn on the kill switch
([kill-switch.md](kill-switch.md)), then deploy a fixed commit forward. Never edit
`config_plugins.version` by hand.

## After any deploy or rollback

Note the tags from `deploy/deploy.sh status` in the change log with the reason.

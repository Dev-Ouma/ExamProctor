# ExamProctor developer commands. Staging stack lives in staging/compose.yml.
COMPOSE := docker compose -f staging/compose.yml --env-file staging/.env --env-file staging/examproctor.secrets
MOODLE_EXEC := $(COMPOSE) exec -T -u www-data moodle

.PHONY: models up down reset seed e2e-gate test-browser sdk-moodle logs ps test test-service test-js test-moodle

staging/.env:
	@cp staging/.env.example staging/.env
	@for k in MOODLE_DB_PASSWORD MOODLE_ADMIN_PASSWORD SERVICE_DB_PASSWORD; do \
		v=$$(openssl rand -hex 16); sed -i.bak "s/^$$k=.*/$$k=$$v/" staging/.env; done; rm -f staging/.env.bak
	@echo "Generated staging/.env with random passwords (admin password: MOODLE_ADMIN_PASSWORD)."

staging/examproctor.secrets: FORCE  ## Generated secrets; missing keys are added, existing ones kept.
	@umask 077; touch staging/examproctor.secrets; \
	for k in EXAMPROCTOR_SHARED_SECRET EXAMPROCTOR_SESSION_KEY EXAMPROCTOR_S3_ACCESS_KEY EXAMPROCTOR_S3_SECRET_KEY; do \
		grep -q "^$$k=" staging/examproctor.secrets || echo "$$k=$$(openssl rand -hex 24)" >> staging/examproctor.secrets; done

FORCE:

up: staging/.env staging/examproctor.secrets  ## Build and start the whole stack, wait until healthy, then seed.
	$(COMPOSE) up -d --build --wait --wait-timeout 900
	$(MAKE) seed
	@echo "Moodle: http://localhost:$$(grep MOODLE_PORT staging/.env | cut -d= -f2)  Service: http://localhost:8000/v1/health"

down:
	$(COMPOSE) down

reset:  ## Destroy all staging data volumes.
	$(COMPOSE) down -v

seed:
	$(MOODLE_EXEC) php /opt/seed/seed.php
	$(MOODLE_EXEC) sh -c 'php admin/cli/cfg.php --component=local_examproctor --name=serviceurl --set="$$EXAMPROCTOR_PUBLIC_URL" && php admin/cli/cfg.php --component=local_examproctor --name=signingkey --set="$$EXAMPROCTOR_SHARED_SECRET" && php admin/cli/cfg.php --component=local_examproctor --name=camerainterval --set=10 && php admin/cli/cfg.php --component=local_examproctor --name=screeninterval --set=15 && php admin/cli/cfg.php --component=local_examproctor --name=serviceinternalurl --set="$$EXAMPROCTOR_INTERNAL_URL" && php admin/cli/purge_caches.php'

test-browser:  ## Real Chromium with fake camera/screen against the staging stack.
	cd staging/browser && npm ci --silent && npx playwright install chromium >/dev/null && STUDENT=epstudent$$(shuf -i 5-20 -n 1 2>/dev/null || jot -r 1 5 20) npx playwright test --workers=1

sdk-moodle:  ## Rebuild the SDK into quizaccess_examproctor/amd.
	cd client-sdk && npm run -s build:moodle

e2e-gate:  ## M2 end-to-end: launch token -> service -> signed webhook -> Moodle gate.
	$(MOODLE_EXEC) php /opt/seed/e2e_gate.php

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

test: test-service test-js

models:  ## Download the pinned face models for local tests.
	cd service && ./fetch_models.sh models

test-service:
	cd service && uv run ruff check . && uv run ruff format --check . && uv run pytest -q

test-js:
	cd client-sdk && npm run -s lint && npm test -s
	cd dashboards && npm run -s lint && npm test -s

test-moodle:  ## PHPUnit for both plugins inside the running moodle container.
	$(COMPOSE) exec -T moodle sh -c 'cd /var/www/html && [ -x vendor/bin/phpunit ] || (curl -sS https://getcomposer.org/installer | php -- --quiet && php composer.phar install --quiet --no-interaction)'
	$(COMPOSE) exec -T moodle sh -c 'cd /var/www/html && mkdir -p /var/moodledata/phpunit && php admin/tool/phpunit/cli/init.php >/dev/null'
	$(COMPOSE) exec -T moodle sh -c 'cd /var/www/html && vendor/bin/phpunit --testsuite quizaccess_examproctor_testsuite && vendor/bin/phpunit --testsuite local_examproctor_testsuite'

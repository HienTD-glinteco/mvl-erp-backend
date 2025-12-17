ENVIRONMENT := local

# app commands
check:
	python manage.py check

migrations:
	python manage.py makemigrations

migrate:
	python manage.py migrate

compilemessages:
	python manage.py compilemessages -l vi

# generate translation messages (ignore environment, coverage, tests and non-Python dirs)
messages:
	python manage.py makemessages -l vi --no-obsolete \
		--ignore=venv --ignore=.venv --ignore=htmlcov --ignore=tests \
		--ignore=logs --ignore=.git --ignore=.mypy_cache \
		--ignore=.pytest_cache --ignore=.ruff_cache

start:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py runserver

shell:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py shell_plus

celery_worker:
	ENVIRONMENT=$(ENVIRONMENT) celery -A celery_tasks worker -l info -Q default

run_audit_logs_consumer:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py consume_audit_logs $(ARGS)

run_realtime_attendance_listener:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py run_realtime_attendance_listener $(ARGS)

test:
	ENVIRONMENT=test pytest $(ARGS)

test_parallel:
	ENVIRONMENT=test pytest -n auto $(ARGS)

ENVIRONMENT := local
args =

# app commands
check:
	python manage.py check $(args)

migrations:
	python manage.py makemigrations $(args)

migrate:
	python manage.py migrate $(args)

compilemessages:
	python manage.py compilemessages -l vi $(args)

# generate translation messages (ignore environment, coverage, tests and non-Python dirs)
messages:
	python manage.py makemessages -l vi --no-obsolete \
		--ignore=venv --ignore=.venv --ignore=htmlcov --ignore=tests \
		--ignore=logs --ignore=.git --ignore=.mypy_cache \
		--ignore=.pytest_cache --ignore=.ruff_cache

start:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py runserver $(args)

shell:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py shell_plus $(args)

celery_worker:
	ENVIRONMENT=$(ENVIRONMENT) celery -A celery_tasks worker -l info -Q default $(args)

run_audit_logs_consumer:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py consume_audit_logs $(args)

run_realtime_attendance_listener:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py run_realtime_attendance_listener $(args)

test:
	ENVIRONMENT=test pytest $(args)

test_parallel:
	ENVIRONMENT=test pytest -n auto $(args)

ENVIRONMENT := local

# app commands
check:
	python manage.py check

migrations:
	python manage.py makemigrations

migrate:
	python manage.py migrate

messages:
	python manage.py makemessages -l vi -i venv

server:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py runserver

shell:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py shell_plus

celery_worker:
	ENVIRONMENT=$(ENVIRONMENT) celery -A celery_tasks worker -l info -Q default

run_audit_logs_consumer:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py consume_audit_logs $(ARGS)

test:
	ENVIRONMENT=testing pytest $(ARGS)

test_parallel:
	ENVIRONMENT=testing pytest -n auto $(ARGS)

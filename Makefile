ENVIRONMENT := local

# app commands
check:
	python manage.py check

migrations:
	python manage.py makemigrations

migrate:
	python manage.py migrate

server:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py runserver

shell:
	ENVIRONMENT=$(ENVIRONMENT) python manage.py shell_plus

celery_worker:
	ENVIRONMENT=$(ENVIRONMENT) celery -A celery_tasks worker -l info -Q default

celery_audit_worker:
	ENVIRONMENT=$(ENVIRONMENT) celery -A celery_tasks worker -l info -Q audit_logs_queue

test:
	ENVIRONMENT=testing pytest -s

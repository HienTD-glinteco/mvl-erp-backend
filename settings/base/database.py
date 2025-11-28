import dj_database_url

from .base import config

# Parse database connection url strings like psql://user:pass@127.0.0.1:8458/db
DATABASES = {"default": dj_database_url.parse(config("DATABASE_URL"))}

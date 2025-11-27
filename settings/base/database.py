import dj_database_url

from .base import config

# Parse database connection url strings like psql://user:pass@127.0.0.1:8458/db
DATABASES = {"default": dj_database_url.parse(config("DATABASE_URL"))}

# Ensure PostGIS backend is used so GeoDjango features work correctly.
# dj_database_url.parse may set a default postgresql backend; override
# explicitly to the PostGIS engine.
DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"

# The backend Project

This project powers the MaiVietLand backend.

## Prepare environment

### Create a virtual environment

```bash
pyenv virtualenv backend
pyenv shell backend

# or

python -m venv venv
source venv/bin/activate
```

### Install poetry

- poetry is used for easily managing dependency packages

```bash
pip install poetry
```

### Install dependency packages

```bash
poetry install

# for development
poetry install --dev
```

### Create Database

If using sqlite, you can pass this step.
This guide intends to help create PostgreSQL db

```sql
DROP DATABASE IF EXISTS backend;

CREATE DATABASE backend;

CREATE ROLE backend WITH LOGIN PASSWORD 'password';
ALTER DATABASE backend OWNER TO backend;
```

### Create environment file

``` bash
cp .env.tpl .env

# Update the environment varables as needed
```

### Run migrate to init database for the app

```bash
python manage.py migrate
```

## Create superuser

```bash
python manage.py createsuperuser
```

### Install pre-commit

```bash
# cd <TO REPO's root directory>
pre-commit install
```

### Run mypy for checking type annotations

```bash
mypy --ignore-missing-imports
```

### Install redis if needed

```bash
# For Ubuntu
## Install redis
sudo apt-get install redis-server
## Start service
sudo service redis-server

# For Mac
## Install redis
brew install redis
## Start service
brew services start redis
```


## Run celery

```bash
ENVIRONMENT=local celery -A celery_tasks worker -l info -Q default
ENVIRONMENT=local celery -A celery_tasks beat -l info
```

## Run flower to easily manage celery in browsers

```bash
# Run flower to manage celery
ENVIRONMENT=local celery -A celery_tasks flower
```

Then navigate to http://localhost:5555/

## CI/CD Pipeline

This project includes an **optimized CI/CD pipeline** using GitHub Actions with parallel job execution and intelligent caching.

### Environments
- **Test**: Automatically deployed when code is merged to `master`
- **Staging**: Deployed when PR from `master` to `staging` is merged
- **Production**: Deployed when PR from `master` to `release` is merged

### CI Performance
- ⚡ **Fast feedback**: ~3-4 minutes (with cache)
- 🔄 **Parallel execution**: Linting, Django checks, and tests run simultaneously
- 💾 **Smart caching**: Dependencies cached for faster subsequent runs
- ✅ **Reliable**: Fixed cache issues for consistent performance

### Quick Start for CI/CD

1. **Set up GitHub Secrets**: Configure environment secrets in repository settings
2. **Create branches**: Ensure `staging` and `release` branches exist
3. **Test the pipeline**: Create a PR to `master` to trigger CI

### Documentation

- 📖 [CICD.md](docs/CICD.md) - Complete CI/CD documentation
- 🚀 [CI Quick Reference](docs/CI_QUICK_REFERENCE.md) - Quick troubleshooting guide
- 📊 [CI Optimization Summary](docs/CI_OPTIMIZATION_SUMMARY.md) - Performance improvements
- 📈 [Workflow Comparison](docs/CI_WORKFLOW_COMPARISON.md) - Before/after visualization

### Workflow

1. Create feature branch from `master`
2. Make changes and create PR to `master` (triggers CI - runs in ~3-4 min)
3. Merge PR to deploy to test environment
4. Create PR from `master` to `staging` for staging deployment
5. Create PR from `master` to `release` for production deployment

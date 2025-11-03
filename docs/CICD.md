# CI/CD Pipeline Documentation

This document describes the CI/CD pipeline setup for the MaiVietLand backend project.

## Overview

The CI/CD pipeline is implemented using GitHub Actions and supports the following workflow:

1. **Feature Development**: Developers create feature branches from `master`
2. **Pull Request CI**: When PRs are created to `master`, CI runs code quality checks and tests
3. **Test Deployment**: When PRs are merged to `master` **AND CI tests pass**, automatic deployment to test environment
4. **Staging Deployment**: PRs from `master` to `staging` trigger deployment to staging environment
5. **Production Deployment**: PRs from `master` to `release` trigger deployment to production environment (workflow not yet implemented)

## Environments

### Test Environment
- **Trigger**: Automatic deployment when code is merged to `master` branch **AND CI tests pass**
- **Purpose**: Continuous testing of new features
- **Branch**: `master`
- **Infrastructure**: EC2 server with nginx + supervisor + gunicorn setup
- **Details**: See [EC2_DEPLOYMENT.md](EC2_DEPLOYMENT.md) for complete setup guide

### Staging Environment
- **Trigger**: Manual deployment via PR from `master` to `staging` branch
- **Purpose**: Pre-production testing and client review
- **Branch**: `staging`

### Production Environment
- **Trigger**: Manual deployment via PR from `master` to `release` branch
- **Purpose**: Live production environment
- **Branch**: `release`

## Workflows

### 1. CI/CD Pipeline (`ci-cd.yml`)
**Trigger**: Pull requests to `master` branch, Push to `master` branch

**Workflow Structure** (optimized to avoid redundant dependency installation):

```
prepare
   ├── django-checks (system checks + linting)
   └── test (run tests with coverage, only on PRs)
        └── deploy-develop (only on push to master)
```

#### Prepare Job - Setup Poetry & Install Dependencies
**Purpose**: Centralizes dependency installation and caching for all subsequent jobs

**Steps**:
- Code checkout
- Python setup
- Cache Poetry installation
- Install Poetry
- Cache virtual environment (.venv)
- Install dependencies (only on cache miss)

**Benefits**:
- Dependencies installed only once per workflow run
- All subsequent jobs restore from cache (fail-on-cache-miss: true)
- Eliminates redundant dependency installation
- Faster CI/CD runs (especially on cache hits)

#### Django Checks Job - Django System Validation
**Depends on**: `prepare` job
**Steps**:
- Code checkout
- Python setup
- Restore Poetry from cache (read-only)
- Restore virtual environment from cache (read-only)
- Environment configuration (SQLite for faster execution)
- Django system checks
- Pre-commit hooks (linting, formatting, type checking)

**Note**: This job does NOT install dependencies - it only restores them from cache.

#### Test Job - Unit Tests with Coverage
**Trigger**: Only runs on pull requests
**Depends on**: `prepare` job (runs in parallel with django-checks)

**Steps**:
- Code checkout
- Python setup
- Database services (PostgreSQL, Redis)
- Restore Poetry from cache (read-only)
- Restore virtual environment from cache (read-only)
- Environment configuration
- Unit tests with coverage
- Coverage reporting to Codecov

**Note**: This job does NOT install dependencies - it only restores them from cache. It runs independently from django-checks.

#### Deploy-Develop Job - Deploy to Test Environment
**Trigger**: Only runs on push to `master` branch (not on pull requests)
**Depends on**: `django-checks` job must complete successfully

**Steps**:
- Deploy to EC2 test server via SSH
- Auto-update API documentation version with ISO timestamp
- Install production dependencies on server
- Database migrations
- Application restart (supervisor)
- Web server reload (nginx)
- Health checks
- Slack notifications

**Performance Optimizations**:
- Centralized dependency setup reduces CI time by ~40-50%
- Poetry installation caching speeds up subsequent runs
- Smart cache restoration with fail-on-cache-miss ensures consistency
- Parallel execution of django-checks and test jobs
- Test job no longer waits for django-checks to complete

### 2. Staging Environment Deployment (`deploy-staging.yml`)
**Trigger**: PR from `master` to `staging` branch (when merged)

**Steps**:
- Code checkout from `staging` branch
- Environment setup
- Auto-update API documentation version with ISO timestamp
- Application build
- Database migrations
- Deployment (configurable)
- Health checks
- Notifications

### 3. Production Environment Deployment (`deploy-production.yml`)
**Note**: This workflow file is not currently implemented. Create it based on the staging workflow template when needed.

**Planned Trigger**: PR from `master` to `release` branch (when merged)

## API Documentation Versioning

The API documentation version is automatically updated with an ISO timestamp during every deployment. This ensures that the API documentation always reflects the latest deployment time.

### How It Works

1. **Environment Variable**: The API documentation version is read from the `API_DOC_VERSION` environment variable
2. **Automatic Update**: During deployment, the CI/CD pipeline:
   - Generates an ISO timestamp (format: `YYYY-MM-DDTHH:MM:SSZ`)
   - Updates or adds `API_DOC_VERSION` in the server's `.env` file
   - Restarts the application to load the new version
3. **Default Value**: If `API_DOC_VERSION` is not set, it defaults to `1.0.0`

### Configuration

**Settings File** (`settings/base/drf.py`):
```python
SPECTACULAR_SETTINGS = {
    "VERSION": config("API_DOC_VERSION", default="1.0.0"),
    # ... other settings
}
```

**CI/CD Deployment Script** (in `ci-cd.yml` and `deploy-staging.yml`):
```bash
# Update API documentation version in .env file
API_DOC_VERSION=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
if grep -q "^API_DOC_VERSION=" .env 2>/dev/null; then
  sed -i "s/^API_DOC_VERSION=.*/API_DOC_VERSION=$API_DOC_VERSION/" .env
else
  echo "API_DOC_VERSION=$API_DOC_VERSION" >> .env
fi
```

### Accessing the Version

The version can be viewed in:
- **Swagger UI**: Available at `/docs/` (in develop/local environments)
- **API Schema**: Available at `/schema/` (in develop/local environments)

Example version: `2024-12-20T10:30:00Z`

## Required GitHub Secrets

### Test Environment
- `TEST_CELERY_BROKER_URL`: Celery broker URL
- `TEST_SENTRY_DSN`: Sentry DSN for error tracking

### Staging Environment
- `STAGING_SECRET_KEY`: Django secret key for staging environment
- `STAGING_DATABASE_URL`: Database connection string
- `STAGING_ALLOWED_HOSTS`: Allowed hosts configuration
- `STAGING_CACHE_URL`: Redis cache URL
- `STAGING_CELERY_BROKER_URL`: Celery broker URL
- `STAGING_SENTRY_DSN`: Sentry DSN for error tracking

### Production Environment
- `PRODUCTION_SECRET_KEY`: Django secret key for production environment
- `PRODUCTION_DATABASE_URL`: Database connection string
- `PRODUCTION_ALLOWED_HOSTS`: Allowed hosts configuration
- `PRODUCTION_CACHE_URL`: Redis cache URL
- `PRODUCTION_CELERY_BROKER_URL`: Celery broker URL
- `PRODUCTION_SENTRY_DSN`: Sentry DSN for error tracking

### Deployment Secrets
- `TEST_HOST`, `STAGING_HOST`, `PRODUCTION_HOST`: Server hostnames for SSH deployment
- `TEST_USERNAME`, `STAGING_USERNAME`, `PRODUCTION_USERNAME`: SSH usernames
- `TEST_SSH_KEY`, `STAGING_SSH_KEY`, `PRODUCTION_SSH_KEY`: SSH private keys

## Deployment Methods

The workflows support multiple deployment methods (currently disabled by default):

1. **SSH Deployment**: Direct deployment to servers via SSH
2. **Docker Deployment**: Build and deploy Docker containers
3. **Cloud Deployment**: Deploy to cloud platforms (AWS, GCP, Azure)

To enable a specific deployment method, set the `if` condition to `true` in the respective workflow file.

## Branch Strategy

```
master (main development branch)
├── feature/feature-name (feature branches)
├── staging (staging environment branch)
└── release (production environment branch)
```

### Workflow Process

1. **Feature Development**:
   ```bash
   git checkout master
   git pull origin master
   git checkout -b feature/your-feature-name
   # ... make changes ...
   git push origin feature/your-feature-name
   # Create PR to master
   ```

2. **Deploy to Staging**:
   ```bash
   git checkout staging
   git pull origin staging
   # Create PR from master to staging
   # Merge PR to trigger staging deployment
   ```

3. **Deploy to Production**:
   ```bash
   git checkout release
   git pull origin release
   # Create PR from master to release
   # Merge PR to trigger production deployment
   ```

## Testing

The CI pipeline includes:
- Unit tests using pytest
- Django system checks
- Code quality checks with MyPy
- Test coverage reporting
- Database migration validation

## Monitoring and Notifications

- **Sentry Integration**: Error tracking for all environments
- **Slack Notifications**: Deployment status notifications
- **Health Checks**: Automated health checks after deployments
- **Release Tagging**: Automatic tagging of production releases

## Getting Started

1. **Set up GitHub Secrets**: Configure all required secrets in GitHub repository settings
2. **Create Branches**: Ensure `staging` and `release` branches exist
3. **Configure Deployment**: Enable and configure your preferred deployment method
4. **Test the Pipeline**: Create a test PR to verify CI/CD functionality

## Maintenance

- **Update Dependencies**: Regularly update Python and package dependencies
- **Monitor Workflows**: Review workflow runs for failures or performance issues
- **Security Updates**: Keep secrets and deployment credentials updated
- **Environment Synchronization**: Ensure environment configurations stay in sync

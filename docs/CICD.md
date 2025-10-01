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

**Jobs** (run in parallel for faster feedback):

#### Lint Job - Code Quality Checks
**Steps**:
- Code checkout
- Python and Poetry setup with caching
- Dependency installation (cached)
- MyPy type checking (project files only: apps/, libs/, settings/)

#### Django Checks Job - Django System Validation
**Steps**:
- Code checkout
- Python and Poetry setup with caching
- Dependency installation (cached)
- Environment configuration (SQLite for faster execution)
- Django system checks

#### Test Job - Unit Tests with Coverage
**Steps**:
- Code checkout
- Python and Poetry setup with caching
- Dependency installation (cached)
- Database services (PostgreSQL, Redis)
- Environment configuration
- Database migrations
- Unit tests with coverage
- Coverage reporting

#### Test Deployment Job - Deploy to Test Environment
**Trigger**: Only runs on push to `master` branch (not on pull requests) **AND** only after all CI jobs pass successfully
**Depends on**: lint, django-checks, and test jobs must complete successfully

**Steps**:
- Deploy to EC2 test server via SSH
- Database migrations
- Application restart (supervisor)
- Web server reload (nginx)
- Health checks
- Notifications

**Performance Optimizations**:
- Parallel job execution reduces CI time by ~40-50%
- Poetry installation caching speeds up subsequent runs
- Fixed cache key bug ensures reliable dependency caching
- Focused MyPy scope reduces linting time
- Combined shell commands reduce overhead

### 2. Staging Environment Deployment (`deploy-staging.yml`)
**Trigger**: PR from `master` to `staging` branch (when merged)

**Steps**:
- Code checkout from `staging` branch
- Environment setup
- Application build
- Database migrations
- Deployment (configurable)
- Health checks
- Notifications

### 3. Production Environment Deployment (`deploy-production.yml`)
**Note**: This workflow file is not currently implemented. Create it based on the staging workflow template when needed.

**Planned Trigger**: PR from `master` to `release` branch (when merged)

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
# GitHub Environments Setup

This document provides step-by-step instructions for setting up GitHub environments and secrets for the CI/CD pipeline.

## 1. Create GitHub Environments

1. Navigate to your repository on GitHub
2. Go to **Settings** → **Environments**
3. Create three environments:
   - `test`
   - `staging` 
   - `production`

## 2. Configure Environment Protection Rules

### Test Environment
- No protection rules needed (auto-deployment)

### Staging Environment
- Enable **Required reviewers** (optional)
- Add reviewers who can approve staging deployments

### Production Environment
- Enable **Required reviewers** (recommended)
- Add reviewers who can approve production deployments
- Consider enabling **Deployment branches** to restrict to `release` branch only

## 3. Configure Environment Secrets

### Test Environment Secrets

**Note**: Environment variables are now managed directly on the server, not through GitHub secrets. Only SSH access secrets are needed in GitHub:

```
TEST_HOST=your-ec2-ip-or-domain
TEST_USERNAME=ubuntu
TEST_SSH_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
...your private key...
-----END OPENSSH PRIVATE KEY-----
TEST_APP_URL=http://test.yourdomain.com
```

### Staging Environment Secrets

**Note**: Environment variables are now managed directly on the server, not through GitHub secrets. Only SSH access secrets are needed in GitHub:

```
STAGING_HOST=your-ec2-ip-or-domain
STAGING_USERNAME=ubuntu
STAGING_SSH_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
...your private key...
-----END OPENSSH PRIVATE KEY-----
STAGING_APP_URL=http://staging.yourdomain.com
```
```

### Production Environment Secrets

**Note**: Production environment will be implemented later. Environment variables will be managed directly on the server, not through GitHub secrets.

## 4. Environment Configuration on Server

Environment variables are now managed directly on each server using `.env` files. Use the provided templates:

- **Test Environment**: Copy `config/env/test.env.example` to `.env` and configure
- **Staging Environment**: Copy `config/env/staging.env.example` to `.env` and configure  
- **Production Environment**: Will be provided when production deployment is implemented

## 5. Optional Deployment Secrets (Legacy - No Longer Used)

The following secrets are no longer used as environment configuration is now managed on servers:
TEST_SSH_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
...your private key...
-----END OPENSSH PRIVATE KEY-----

STAGING_HOST=staging-server.com
STAGING_USERNAME=deploy
STAGING_SSH_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
...your private key...
-----END OPENSSH PRIVATE KEY-----

PRODUCTION_HOST=prod-server.com
PRODUCTION_USERNAME=deploy
PRODUCTION_SSH_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
...your private key...
-----END OPENSSH PRIVATE KEY-----
```

### Docker Deployment (if using Docker)
```
DOCKER_REGISTRY=your-registry.com
DOCKER_USERNAME=your-username
DOCKER_PASSWORD=your-password
```

### Notification Secrets
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
```

## 5. Create Required Branches

Create the required branches for the deployment workflow:

```bash
# Create staging branch
git checkout master
git checkout -b staging
git push origin staging

# Create release branch
git checkout master
git checkout -b release
git push origin release
```

## 6. Test the Setup

1. Create a test feature branch
2. Make a small change
3. Create a PR to `master`
4. Verify that the CI pipeline runs
5. Merge the PR to verify test deployment

## 7. Enable Deployment Methods

Edit the workflow files to enable your preferred deployment method:

1. Open `.github/workflows/deploy-test.yml`
2. Change `if: false` to `if: true` for your deployment method
3. Configure the deployment steps for your infrastructure
4. Repeat for `deploy-staging.yml` and `deploy-production.yml`

## Example: Enable SSH Deployment

```yaml
- name: Deploy to Server (SSH Example)
  if: true  # Changed from false to true
  uses: appleboy/ssh-action@v0.1.5
  with:
    host: ${{ secrets.TEST_HOST }}
    username: ${{ secrets.TEST_USERNAME }}
    key: ${{ secrets.TEST_SSH_KEY }}
    script: |
      cd /path/to/your/app
      git pull origin master
      # ... rest of deployment commands
```

## Security Best Practices

1. **Use strong secret keys**: Generate secure random keys for each environment
2. **Rotate secrets regularly**: Update secrets periodically
3. **Limit access**: Only give necessary team members access to production secrets
4. **Use environment-specific databases**: Never use production data in test/staging
5. **Monitor access**: Regularly review who has access to environments and secrets
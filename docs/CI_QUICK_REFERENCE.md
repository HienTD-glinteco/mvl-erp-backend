# CI/CD Quick Reference Guide

## What Runs When

### On Pull Request to `master`
All three CI jobs run in parallel:

| Job | What It Checks | Typical Time (cached) | Fails If |
|-----|----------------|----------------------|----------|
| **lint** | MyPy type checking on `apps/`, `libs/`, `settings/` | ~1-2 min | Type errors found |
| **django-checks** | Django system checks (models, migrations, etc.) | ~1 min | System check errors |
| **test** | Unit tests + coverage | ~3-4 min | Test failures, coverage issues |

All jobs must pass for PR to be merged.

### On Push to `master`
Same as PR, **plus** automatic deployment to test environment if all jobs pass.

## Viewing Results

### GitHub Actions Tab
1. Go to repository → Actions tab
2. Click on your workflow run
3. See all jobs at once (parallel execution)
4. Click any job to see detailed logs

### Check Status in PR
- ✅ Green checkmark = All jobs passed
- ❌ Red X = At least one job failed
- 🟡 Yellow circle = Jobs running
- Click "Details" to see which job failed

## Common Failures and Fixes

### MyPy Type Errors (lint job)
```bash
# Run locally before pushing
source .venv/bin/activate
python -m mypy apps/ libs/ settings/ --ignore-missing-imports
```

### Django System Check Errors (django-checks job)
```bash
# Run locally
ENVIRONMENT=test python manage.py check
```

### Test Failures (test job)
```bash
# Run all tests locally
ENVIRONMENT=test pytest apps/ -v

# Run specific test file
ENVIRONMENT=test pytest apps/hrm/tests/test_models.py -v

# Run with coverage
ENVIRONMENT=test pytest apps/ --cov=apps --cov-report=html
```

## Cache Behavior

### When Cache Hits
- Dependencies install in ~20 seconds
- Poetry installation in ~10 seconds
- Total setup time: ~30-40 seconds per job

### When Cache Misses
- Happens when `poetry.lock` changes
- Dependencies install in ~2-3 minutes
- Subsequent runs will be cached

### Force Cache Refresh
If you need to force a cache refresh:
1. Update `poetry.lock` (e.g., run `poetry update`)
2. Or, modify the cache key in `.github/workflows/ci-cd.yml`

## Performance Tips

### ✅ DO:
- Push small, focused changes
- Run tests locally before pushing
- Keep dependencies up to date
- Use `git commit --amend` for small fixes (before pushing)

### ❌ DON'T:
- Push broken code just to "see if CI catches it"
- Add unnecessary dependencies
- Skip local testing
- Create massive PRs (harder to debug when CI fails)

## Debugging Failed CI

### Step 1: Identify Which Job Failed
Look at the workflow summary - failed jobs are marked with ❌

### Step 2: Check the Job Logs
Click the failed job → Expand the failed step → Read the error

### Step 3: Reproduce Locally
```bash
# For lint failures
python -m mypy apps/ libs/ settings/ --ignore-missing-imports

# For django-checks failures
ENVIRONMENT=test python manage.py check

# For test failures
ENVIRONMENT=test pytest apps/ -v --tb=short
```

### Step 4: Fix and Push
```bash
# Make your fixes
git add .
git commit -m "fix: resolve CI failure"
git push
```

CI will automatically run again on the new push.

## Comparing with Old Workflow

| Aspect | Old Workflow | New Workflow |
|--------|-------------|--------------|
| Execution | Sequential (one after another) | Parallel (all at once) |
| Feedback Time | ~8-10 minutes | ~3-4 minutes |
| Cache | Broken (always reinstalls) | Working (caches properly) |
| MyPy Scope | Entire directory | Project code only |
| Django Checks DB | PostgreSQL | SQLite (faster) |
| Visibility | Single job (hard to see what failed) | Multiple jobs (easy to see) |

## Advanced: Running CI Locally

### Using Act (GitHub Actions locally)
```bash
# Install act
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run the lint job
act -j lint

# Run all jobs
act pull_request
```

### Using Docker Compose
```bash
# Coming soon - local CI environment
```

## Need Help?

### CI/CD Issues
1. Check this guide
2. Check the main [CICD.md](CICD.md) documentation
3. Check the [CI_OPTIMIZATION_SUMMARY.md](CI_OPTIMIZATION_SUMMARY.md)
4. Ask in team Slack channel

### Workflow Modifications
- Requires approval from team lead
- Test changes in a feature branch first
- Document any changes made

## Monitoring CI Performance

### Key Metrics to Watch
- Average run time (target: <5 minutes)
- Cache hit rate (target: >80%)
- Failure rate (target: <20%)
- Time to feedback (target: <4 minutes)

### Where to Check
- GitHub Actions → Workflow runs
- Repository Insights → Actions tab
- Weekly CI/CD performance reports

## Related Documentation

- [CICD.md](CICD.md) - Complete CI/CD documentation
- [CI_OPTIMIZATION_SUMMARY.md](CI_OPTIMIZATION_SUMMARY.md) - Optimization details
- [CI_WORKFLOW_COMPARISON.md](CI_WORKFLOW_COMPARISON.md) - Before/after comparison
- [EC2_DEPLOYMENT.md](EC2_DEPLOYMENT.md) - Deployment details

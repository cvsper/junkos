# CI/CD Pipeline Quick Start

Get your Umuve CI/CD pipeline running in 5 minutes! 🚀

## Step 1: Add Required Secrets (5 min)

Go to: `Settings > Secrets and variables > Actions > New repository secret`

### Minimum Required Secrets

```bash
# For GitHub Container Registry (auto-provided, no action needed)
GITHUB_TOKEN ✅ (automatic)

# Choose ONE deployment platform:

# Option A: Railway (Easiest)
RAILWAY_TOKEN=<your-railway-token>

# Option B: AWS ECS (More control)
AWS_ACCESS_KEY_ID=<your-aws-key>
AWS_SECRET_ACCESS_KEY=<your-aws-secret>
AWS_REGION=us-east-1

# Database (Production)
PRODUCTION_DATABASE_URL=postgresql://user:pass@host:5432/umuve_prod
```

### Optional (but recommended):

```bash
# Notifications
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
SLACK_WEBHOOK=https://hooks.slack.com/services/...

# Environment URLs
STAGING_URL=https://staging.goumuve.com
PRODUCTION_URL=https://goumuve.com
```

## Step 2: Set Up GitHub Environment

1. Go to `Settings > Environments > New environment`
2. Name: `production`
3. Add protection rules:
   - ✅ Required reviewers: Add yourself + 1 other
   - ✅ Wait timer: 5 minutes (optional)
4. Click `Save protection rules`

## Step 3: Test It Out!

### Test CI Pipeline

```bash
# Create a test PR
git checkout develop
git checkout -b test/ci-pipeline
echo "# Test" >> TEST.md
git add TEST.md
git commit -m "test: verify CI pipeline"
git push origin test/ci-pipeline

# Create PR on GitHub
# Watch CI run in Actions tab! 🎉
```

Expected result: All checks pass in ~10-15 minutes

### Test Staging Deployment

```bash
# Merge your test PR to develop
# Or push directly:
git checkout develop
git merge test/ci-pipeline
git push origin develop

# Watch staging deployment in Actions tab
# Check your staging URL after ~8-12 minutes
```

### Test Production Deployment (When Ready)

```bash
# Merge develop to main
git checkout main
git merge develop
git push origin main

# In Actions tab:
# 1. Workflow starts
# 2. Pre-checks run
# 3. **APPROVAL REQUIRED** - Click "Review deployments"
# 4. Approve deployment
# 5. Blue-green deployment begins
# 6. Traffic switches
# 7. Done! 🎉
```

## Step 4: Set Up Weekly Security Scans

The security workflow is already configured to run every Monday at 2 AM UTC.

To test it now:
1. Go to `Actions` tab
2. Click `Security Audit` workflow
3. Click `Run workflow` dropdown
4. Click green `Run workflow` button

## Common Issues & Fixes

### ❌ "Secret not found: RAILWAY_TOKEN"

**Fix:** Add the secret in Settings > Secrets > Actions

### ❌ Docker build fails

**Fix:** Test locally first:
```bash
cd backend
docker build -t test .
```

### ❌ Tests fail on CI but pass locally

**Fix:** Check PostgreSQL service is running in CI (it is)
```bash
# Run tests with same config as CI
cd backend
DATABASE_URL=postgresql://test:test@localhost:5432/umuve_test pytest
```

### ❌ Staging deployment succeeds but can't access site

**Fix:** Check firewall/security groups allow HTTP/HTTPS

### ❌ Production approval not showing

**Fix:** 
1. Check Environment is named exactly "production"
2. Verify you're added as required reviewer
3. Check GitHub notifications

## Verification Checklist

Use this to verify everything is working:

```
✅ CI Pipeline:
  [ ] Tests run on PRs
  [ ] Coverage reports posted
  [ ] Linting checks pass
  [ ] Docker images build

✅ Staging Deployment:
  [ ] Deploys on merge to develop
  [ ] Smoke tests run
  [ ] Health checks pass
  [ ] Notifications sent

✅ Production Deployment:
  [ ] Pre-deployment checks run
  [ ] Manual approval required
  [ ] Blue-green deployment works
  [ ] Monitoring enabled
  [ ] Rollback capability tested

✅ Security:
  [ ] Weekly scans scheduled
  [ ] Reports generated
  [ ] Issues created for critical findings
```

## Next Steps

1. **Customize notifications**: Add your team's Discord/Slack webhooks
2. **Set up monitoring**: Integrate with Sentry, Datadog, or similar
3. **Add more tests**: Improve coverage to >80%
4. **Test rollback**: Intentionally fail a deployment to verify rollback works
5. **Document runbooks**: Add team-specific deployment procedures

## Getting Help

- 📖 Full docs: [README.md](./README.md)
- 🐛 Issues: Check workflow logs in Actions tab
- 💬 Team: Ask in #engineering channel

---

**You're all set! Happy deploying! 🚀**

# JunkOS CI/CD Pipeline Documentation

This directory contains the complete CI/CD pipeline for JunkOS, including automated testing, security scanning, and deployment workflows.

## 📋 Table of Contents

- [Workflows Overview](#workflows-overview)
- [Setup Requirements](#setup-requirements)
- [Workflow Details](#workflow-details)
- [Environment Variables & Secrets](#environment-variables--secrets)
- [Deployment Strategy](#deployment-strategy)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

---

## 🔄 Workflows Overview

| Workflow | Trigger | Purpose | Duration |
|----------|---------|---------|----------|
| **ci.yml** | PRs, Push to main/develop | Run tests, linting, security scans | ~10-15 min |
| **deploy-staging.yml** | Push to develop | Deploy to staging environment | ~8-12 min |
| **deploy-production.yml** | Push to main | Deploy to production (blue-green) | ~15-25 min |
| **security-scan.yml** | Weekly + manual | Comprehensive security audit | ~15-20 min |

---

## 🛠️ Setup Requirements

### Required GitHub Secrets

Add these secrets in your repository settings (`Settings > Secrets and variables > Actions`):

#### Container Registry
- `GITHUB_TOKEN` - Auto-provided by GitHub Actions

#### Deployment Platforms (choose one or both)

**Railway:**
- `RAILWAY_TOKEN` - Railway API token ([Get it here](https://railway.app/account/tokens))

**AWS ECS:**
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `AWS_REGION` - AWS region (e.g., `us-east-1`)

#### Notification Channels (optional)
- `DISCORD_WEBHOOK` - Discord webhook URL
- `SLACK_WEBHOOK` - Slack incoming webhook URL

#### Environment URLs
- `STAGING_URL` - Staging environment URL (e.g., `https://staging.junkos.app`)
- `BLUE_INTERNAL_URL` - Blue environment URL for blue-green deployments
- `PRODUCTION_URL` - Production URL (e.g., `https://junkos.app`)
- `PRODUCTION_DATABASE_URL` - Production database connection string

#### Load Balancer (for blue-green deployment)
- `PRODUCTION_LISTENER_ARN` - AWS ALB listener ARN
- `BLUE_TARGET_GROUP_ARN` - Blue target group ARN
- `GREEN_TARGET_GROUP_ARN` - Green target group ARN

### GitHub Environments

Create these environments in repository settings:

1. **production** - Add protection rules:
   - ✅ Required reviewers (1-2 people)
   - ✅ Wait timer: 5 minutes
   - ✅ Branch restrictions: `main` only

---

## 📝 Workflow Details

### 1. CI Workflow (`ci.yml`)

**Triggers:**
- Pull requests to `main` or `develop`
- Direct pushes to `main` or `develop`

**What it does:**

#### Backend Testing
```yaml
✓ PostgreSQL service container
✓ Python 3.11 setup
✓ Pytest with coverage (>80% recommended)
✓ Coverage reports to Codecov
✓ HTML coverage artifacts
```

#### Backend Linting
```yaml
✓ Black (code formatting)
✓ isort (import sorting)
✓ flake8 (style guide)
✓ pylint (code quality)
```

#### Backend Security
```yaml
✓ Bandit security scanner
✓ Vulnerability detection
✓ JSON reports for review
```

#### Frontend & Dashboard Testing
```yaml
✓ Jest unit tests with coverage
✓ ESLint for code quality
✓ Prettier formatting check
✓ Coverage reporting
```

#### Docker Build Verification
```yaml
✓ Build all service images
✓ Verify images can start
✓ Build caching for faster builds
```

#### PR Coverage Comments
- Automatically posts coverage percentages on PRs
- Shows backend and frontend coverage side-by-side
- Links to detailed reports

**Best Practices:**
- All PRs must pass CI before merging
- Aim for >80% test coverage
- Fix linting issues before requesting review
- Review security findings immediately

---

### 2. Staging Deployment (`deploy-staging.yml`)

**Triggers:**
- Automatic on merge to `develop`
- Manual dispatch via Actions tab

**Deployment Flow:**

```mermaid
graph LR
    A[Build Images] --> B[Push to Registry]
    B --> C{Deploy Target}
    C -->|Railway| D[Railway Deploy]
    C -->|AWS| E[ECS Deploy]
    D --> F[Smoke Tests]
    E --> F
    F --> G[Health Checks]
    G --> H[Notify Team]
```

**Features:**
- Multi-service Docker builds (backend, frontend, dashboard)
- Parallel image building for speed
- Railway or AWS ECS deployment
- Automated smoke tests with Playwright
- Health endpoint verification
- Discord/Slack notifications

**Smoke Tests:**
```bash
cd e2e
npx playwright test smoke --project=chromium
```

**Health Checks:**
- Backend API: `/api/health`
- Frontend: Root URL
- Dashboard: `/dashboard`

**Rollback:**
If smoke tests fail, manually trigger previous stable version deployment.

---

### 3. Production Deployment (`deploy-production.yml`)

**Triggers:**
- Automatic on merge to `main`
- Manual dispatch with options

**Safety Features:**

#### 1. Pre-Deployment Checks ✅
```yaml
✓ Staging health verification
✓ Database migration safety analysis
✓ Dangerous operation detection (DROP, ALTER DROP)
```

#### 2. Manual Approval 🚦
- **Required** for production deploys
- Configured via GitHub Environments
- Can be skipped in emergencies (not recommended)

#### 3. Blue-Green Deployment Strategy 🔵🟢

**What is Blue-Green?**
- Two identical production environments (Blue & Green)
- Deploy new version to idle environment
- Test thoroughly before switching traffic
- Instant rollback capability

**Deployment Flow:**

```
1. Current: Green (live) ← Users
            Blue (idle)

2. Deploy:  Green (live) ← Users
            Blue (deploying new version...)

3. Test:    Green (live) ← Users
            Blue (testing...)

4. Switch:  Green (idle)
            Blue (live) ← Users

5. Sync:    Green (updated to match)
            Blue (live) ← Users
```

**Benefits:**
- Zero-downtime deployments
- Easy rollback (just switch back)
- Lower risk than in-place updates

#### 4. Database Migrations 🗄️

**Safety Checks:**
```python
# Automatic detection of:
- New migration files
- DROP operations
- ALTER TABLE DROP COLUMN
- Other destructive changes
```

**Process:**
1. Backup before migration
2. Run migrations
3. Verify success
4. Store rollback version
5. Auto-rollback on failure

#### 5. Automated Rollback 🔴

**Triggers automatic rollback if:**
- Blue environment health checks fail
- Smoke tests fail on Blue
- Error rate >10% after traffic switch
- Production verification fails

**Rollback Process:**
1. Switch traffic back to Green
2. Rollback database (if needed)
3. Verify Green is healthy
4. Alert team

#### 6. Monitoring & Verification 📊

**Production Monitoring:**
- 5 minutes of continuous monitoring
- Health checks every 10 seconds
- Error rate calculation
- Automatic rollback if >10% errors

---

### 4. Security Scan (`security-scan.yml`)

**Triggers:**
- Weekly (Mondays at 2 AM UTC)
- Manual dispatch
- Changes to dependencies or Dockerfiles

**Comprehensive Security Audit:**

#### Python Security
```yaml
✓ safety - Known vulnerability database
✓ pip-audit - PyPI advisory database
✓ bandit - SAST for Python code
```

#### JavaScript Security
```yaml
✓ npm audit - NPM advisory database
✓ ESLint security plugins
✓ Outdated package detection
```

#### Container Security
```yaml
✓ Trivy - Image vulnerability scanning
✓ OS package vulnerabilities
✓ Application dependency issues
✓ SARIF reports for GitHub Security
```

#### Secret Detection
```yaml
✓ Gitleaks - Git history scanning
✓ TruffleHog - Secret pattern detection
✓ API keys, tokens, passwords
```

#### License Compliance
```yaml
✓ pip-licenses - Python package licenses
✓ license-checker - NPM package licenses
✓ JSON & Markdown reports
```

#### SAST (Static Analysis)
```yaml
✓ Semgrep - Multi-language scanning
✓ OWASP Top 10 checks
✓ Security best practices
```

**Report Artifacts:**
- All scan results saved for 90 days
- JSON reports for automation
- Human-readable summaries
- SARIF format for GitHub Security tab

**Auto-Issue Creation:**
- Critical findings automatically create GitHub issues
- Weekly summary notifications
- Priority labels applied

---

## 🔐 Environment Variables & Secrets

### Local Development

Create `.env` files in each service directory:

**backend/.env:**
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/junkos
SECRET_KEY=your-secret-key
STRIPE_SECRET_KEY=sk_test_...
```

**frontend/.env:**
```bash
VITE_API_URL=http://localhost:5000
VITE_STRIPE_PUBLIC_KEY=pk_test_...
```

**dashboard/.env:**
```bash
VITE_API_URL=http://localhost:5000
VITE_MAPBOX_TOKEN=pk.ey...
```

### CI/CD Environment

**Never commit secrets to Git!** Use GitHub Secrets instead.

**To add a secret:**
1. Go to `Settings > Secrets and variables > Actions`
2. Click `New repository secret`
3. Name it exactly as shown in docs (case-sensitive)
4. Paste the value
5. Click `Add secret`

---

## 🚀 Deployment Strategy

### Branch Strategy

```
main (production)
  ↑
  └─ develop (staging)
       ↑
       └─ feature/* (PRs)
```

**Workflow:**

1. **Feature Development**
   ```bash
   git checkout develop
   git checkout -b feature/new-feature
   # ... make changes ...
   git push origin feature/new-feature
   # Create PR to develop
   ```

2. **CI Runs Automatically**
   - Tests run on PR
   - Coverage reported
   - Linting checked
   - Security scanned

3. **Merge to Develop → Staging**
   ```bash
   # After PR approval
   git checkout develop
   git merge feature/new-feature
   git push origin develop
   # Triggers deploy-staging.yml
   ```

4. **Test on Staging**
   - Smoke tests run automatically
   - Manual QA testing
   - Client review (if applicable)

5. **Merge to Main → Production**
   ```bash
   git checkout main
   git merge develop
   git push origin main
   # Triggers deploy-production.yml
   # Requires manual approval!
   ```

### Hotfix Strategy

For urgent production fixes:

```bash
git checkout main
git checkout -b hotfix/urgent-fix
# ... fix the issue ...
git push origin hotfix/urgent-fix
# Create PR to main
# Merge and deploy

# Backport to develop
git checkout develop
git merge main
git push origin develop
```

---

## 🛡️ Security Best Practices

### 1. Dependency Management

**Update regularly:**
```bash
# Backend
cd backend
pip list --outdated
pip install --upgrade package-name

# Frontend/Dashboard
cd frontend
npm outdated
npm update
```

**Review security advisories:**
- GitHub Dependabot alerts
- Weekly security scan reports
- npm audit / safety reports

### 2. Secret Management

**Never commit:**
- API keys
- Database passwords
- Access tokens
- Private keys

**Use environment variables:**
```python
# ❌ Bad
API_KEY = "sk_live_123..."

# ✅ Good
import os
API_KEY = os.environ.get('API_KEY')
```

### 3. Database Migrations

**Safe migrations:**
```sql
-- ✅ Safe (additive)
ALTER TABLE users ADD COLUMN phone VARCHAR(20);
CREATE INDEX idx_users_email ON users(email);

-- ⚠️ Requires review
ALTER TABLE users ALTER COLUMN email TYPE TEXT;

-- ❌ Dangerous (use with extreme caution)
ALTER TABLE users DROP COLUMN old_field;
DROP TABLE deprecated_table;
```

**Always:**
- Test migrations on staging first
- Backup before running
- Plan rollback strategy
- Avoid DROP operations in production

### 4. Docker Security

**Use specific base images:**
```dockerfile
# ❌ Bad (mutable)
FROM python:3

# ✅ Good (pinned)
FROM python:3.11.7-slim
```

**Run as non-root:**
```dockerfile
RUN adduser --disabled-password --gecos '' appuser
USER appuser
```

**Scan images:**
```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image junkos-backend:latest
```

---

## 🐛 Troubleshooting

### CI Failures

#### Tests Failing
```bash
# Run tests locally first
cd backend
pytest -v

cd frontend
npm test
```

#### Linting Issues
```bash
# Auto-fix formatting
cd backend
black app/ tests/
isort app/ tests/

cd frontend
npx prettier --write "src/**/*.{js,jsx}"
npx eslint --fix .
```

#### Docker Build Failures
```bash
# Build locally to debug
docker build -t test-build ./backend
docker run --rm test-build
```

### Staging Deployment Issues

#### Railway Deployment Fails
```bash
# Check Railway logs
railway logs --service backend

# Verify environment variables
railway variables
```

#### AWS ECS Deployment Fails
```bash
# Check ECS service events
aws ecs describe-services \
  --cluster junkos-staging \
  --services backend

# View CloudWatch logs
aws logs tail /ecs/junkos-backend --follow
```

#### Smoke Tests Fail
```bash
# Run smoke tests locally
cd e2e
BASE_URL=https://staging.junkos.app npx playwright test smoke

# Debug with UI
npx playwright test --ui
```

### Production Deployment Issues

#### Manual Approval Timeout
- Check GitHub notifications
- Verify reviewers are notified
- Can approve in Actions tab

#### Blue Environment Unhealthy
- Check AWS ECS task logs
- Verify environment variables
- Check database connectivity
- Review application logs

#### Rollback Initiated
1. Check workflow logs for root cause
2. Fix issue in develop branch
3. Test thoroughly on staging
4. Retry production deployment

#### Database Migration Failed
```bash
# Check migration status
flask db current

# Manual rollback if needed
flask db downgrade <previous_version>
```

### Security Scan Issues

#### High Severity Vulnerabilities Found
1. Review the specific vulnerability
2. Check if patch available: `npm audit fix` or `pip install --upgrade`
3. If no patch: evaluate risk vs. functionality
4. Document decision (suppress with justification)

#### False Positives
```yaml
# Suppress in bandit
# bandit: skip

# Suppress in ESLint
/* eslint-disable-next-line security/detect-object-injection */
```

---

## 📚 Additional Resources

### GitHub Actions Documentation
- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- [Contexts](https://docs.github.com/en/actions/learn-github-actions/contexts)

### Deployment Platforms
- [Railway Docs](https://docs.railway.app/)
- [AWS ECS Docs](https://docs.aws.amazon.com/ecs/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

### Security Tools
- [Bandit](https://bandit.readthedocs.io/)
- [Trivy](https://aquasecurity.github.io/trivy/)
- [Semgrep](https://semgrep.dev/docs/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

### Testing
- [Pytest](https://docs.pytest.org/)
- [Jest](https://jestjs.io/)
- [Playwright](https://playwright.dev/)

---

## 🤝 Contributing

### Adding New Tests
```bash
# Backend
cd backend/tests
# Add test_feature.py

# Frontend
cd frontend/tests
# Add Feature.test.jsx
```

### Updating Workflows

1. Make changes to workflow files
2. Test with `act` (local GitHub Actions runner)
3. Create PR to develop
4. CI will validate YAML syntax
5. Test on staging before merging to main

### Improving Security

- Add more Semgrep rules
- Configure custom bandit rules
- Set up SAST baselines
- Add security unit tests

---

## 📞 Support

**Issues with CI/CD?**
1. Check workflow logs in Actions tab
2. Review this documentation
3. Search existing GitHub issues
4. Create new issue with:
   - Workflow name
   - Run ID
   - Error messages
   - Steps to reproduce

**Emergency Deployment Issues?**
1. Check #engineering Discord/Slack
2. Review production monitoring
3. Use manual workflow dispatch if needed
4. Document incident for post-mortem

---

## 📈 Metrics & Monitoring

### Key Performance Indicators

**CI Performance:**
- ✅ Test pass rate: >95%
- ✅ Build time: <15 minutes
- ✅ Coverage: >80%

**Deployment Success:**
- ✅ Staging: >98% success rate
- ✅ Production: >99% success rate
- ✅ Rollback time: <5 minutes

**Security:**
- ✅ Critical vulnerabilities: 0
- ✅ High vulnerabilities: <5
- ✅ Scan frequency: Weekly

### Workflow Run History

View in Actions tab:
- Filter by workflow
- Check success rates
- Identify patterns
- Optimize slow steps

---

## 🎯 Roadmap

### Planned Improvements

- [ ] E2E test coverage for all critical paths
- [ ] Canary deployments (gradual rollout)
- [ ] Automated performance testing
- [ ] Cost optimization for CI/CD
- [ ] Multi-region deployment
- [ ] Feature flags integration
- [ ] Automated changelog generation
- [ ] Slack/Discord bot for deployment commands

---

**Last Updated:** 2024-02-06  
**Maintained By:** JunkOS DevOps Team  
**Version:** 1.0.0

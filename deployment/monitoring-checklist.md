# JunkOS Backend - Production Monitoring Checklist

Complete checklist for setting up monitoring, logging, and alerting for your production backend.

---

## 📊 Overview

**Goal:** Detect issues before users do, respond quickly to incidents, and maintain system reliability.

**Key Metrics to Track:**
- **Availability:** Is the service up?
- **Performance:** How fast is it responding?
- **Errors:** What's breaking?
- **Traffic:** How many requests?
- **Resources:** CPU, memory, database

---

## ✅ Pre-Launch Checklist

### Error Tracking

- [ ] **Sentry configured** with DSN in environment variables
- [ ] **Source maps uploaded** for better stack traces
- [ ] **Error alerts enabled** (email, Slack, PagerDuty)
- [ ] **Release tracking enabled** to correlate errors with deploys
- [ ] **Minimum log level set** (info in production, debug in staging)
- [ ] **PII filtering enabled** (don't log passwords, tokens, personal data)
- [ ] **Test error reporting** (trigger test error, verify in Sentry)

### Uptime Monitoring

- [ ] **Service selected** (UptimeRobot, Pingdom, StatusCake)
- [ ] **Health endpoint created** (`/health` returns 200 OK)
- [ ] **Monitor configured** for main API endpoint
- [ ] **Check interval set** (5 minutes recommended)
- [ ] **Alert contacts added** (email, SMS, Slack)
- [ ] **Status page created** (optional, for customer communication)

### Database Monitoring

- [ ] **Automatic backups enabled** (minimum daily)
- [ ] **Backup retention set** (7-30 days recommended)
- [ ] **Backup restoration tested** (simulate disaster recovery)
- [ ] **Connection pooling configured** (prevent connection exhaustion)
- [ ] **Query performance monitored** (slow query log enabled)
- [ ] **Storage alerts set** (warn at 80% capacity)
- [ ] **Connection limits monitored** (alert at 80% of max connections)

### Application Logging

- [ ] **Structured logging implemented** (JSON format)
- [ ] **Log levels configured** (error, warn, info, debug)
- [ ] **Log aggregation setup** (CloudWatch, LogDNA, Papertrail)
- [ ] **Log retention policy set** (30-90 days typical)
- [ ] **Sensitive data masked** (passwords, API keys, tokens)
- [ ] **Request ID tracking** (correlate logs across services)
- [ ] **Search and filter tested** (can find specific errors quickly)

---

## 🔧 Sentry Setup (Error Tracking)

### 1. Create Sentry Account

1. Sign up at [sentry.io](https://sentry.io)
2. Create new project → **Node.js**
3. Copy DSN (looks like `https://xxxxx@sentry.io/xxxxx`)

**Free tier:** 5,000 errors/month

### 2. Install Sentry SDK

```bash
npm install @sentry/node @sentry/tracing
```

### 3. Configure in Application

**`server.js`:**
```javascript
const Sentry = require('@sentry/node');
const Tracing = require('@sentry/tracing');

// Initialize BEFORE any other code
Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  release: `junkos-backend@${process.env.APP_VERSION || 'unknown'}`,
  
  // Performance monitoring (10% of transactions)
  tracesSampleRate: 0.1,
  
  // Integrations
  integrations: [
    new Sentry.Integrations.Http({ tracing: true }),
    new Tracing.Integrations.Express({ app }),
    new Tracing.Integrations.Postgres(),
  ],
  
  // Filter sensitive data
  beforeSend(event) {
    // Remove passwords from breadcrumbs/context
    if (event.request?.data?.password) {
      delete event.request.data.password;
    }
    return event;
  },
});

// Request handler (must be first middleware)
app.use(Sentry.Handlers.requestHandler());
app.use(Sentry.Handlers.tracingHandler());

// ... your routes ...

// Error handler (must be AFTER routes, BEFORE other error handlers)
app.use(Sentry.Handlers.errorHandler());

// Optional fallback error handler
app.use((err, req, res, next) => {
  res.status(500).json({ error: 'Internal server error' });
});
```

### 4. Configure Alerts

**Sentry Dashboard → Alerts:**

1. **High error rate:**
   - Trigger: > 10 errors in 1 minute
   - Action: Email + Slack notification

2. **New error type:**
   - Trigger: First occurrence of new error
   - Action: Immediate notification

3. **Regression:**
   - Trigger: Error reappears after being marked resolved
   - Action: Email team lead

### 5. Set Up Releases

Track which version caused errors:

```bash
# In CI/CD pipeline
export SENTRY_ORG=your-org
export SENTRY_PROJECT=junkos-backend
export VERSION=$(git rev-parse --short HEAD)

# Create release
sentry-cli releases new "$VERSION"
sentry-cli releases set-commits "$VERSION" --auto
sentry-cli releases finalize "$VERSION"

# Deploy
sentry-cli releases deploys "$VERSION" new -e production
```

---

## 🔔 Uptime Monitoring Setup

### Option 1: UptimeRobot (Recommended - Free)

**Setup (5 minutes):**

1. Sign up at [uptimerobot.com](https://uptimerobot.com)
2. **Add New Monitor:**
   - Monitor Type: HTTP(s)
   - Friendly Name: JunkOS Backend API
   - URL: `https://api.junkos.com/health`
   - Monitoring Interval: 5 minutes
   - Monitor Timeout: 30 seconds
3. **Add Alert Contacts:**
   - Email (free)
   - SMS ($0.15/alert)
   - Slack webhook
   - PagerDuty
4. **Configure Alert Settings:**
   - Send alerts when: Down
   - Alert after: 2 failed checks (avoid false positives)
   - Re-alert if still down: Every 30 minutes

**Free tier:** 50 monitors, 5-minute checks

### Option 2: Pingdom

1. Sign up at [pingdom.com](https://www.pingdom.com)
2. Create uptime check (similar to UptimeRobot)
3. More detailed analytics, but paid ($15/month)

### Option 3: StatusCake

1. Sign up at [statuscake.com](https://www.statuscake.com)
2. Free tier includes basic monitoring
3. Good for multiple regions

### Create Health Endpoint

**`routes/health.js`:**
```javascript
router.get('/health', async (req, res) => {
  try {
    // Check database connection
    await pool.query('SELECT 1');
    
    // Check critical dependencies
    const checks = {
      database: true,
      stripe: !!process.env.STRIPE_SECRET_KEY,
      memory: process.memoryUsage().heapUsed / process.memoryUsage().heapTotal < 0.9,
    };
    
    const healthy = Object.values(checks).every(v => v);
    
    res.status(healthy ? 200 : 503).json({
      status: healthy ? 'healthy' : 'degraded',
      timestamp: new Date().toISOString(),
      checks,
    });
  } catch (error) {
    res.status(503).json({
      status: 'unhealthy',
      error: 'Database connection failed',
    });
  }
});
```

---

## 💾 Database Backup Strategy

### Automated Daily Backups

#### Railway
1. PostgreSQL plugin → **Settings**
2. Enable **Automatic Backups**
3. Set schedule: Daily at 2 AM UTC
4. Retention: 7 days (upgrade for more)

#### AWS RDS
Automatic backups enabled by default:
```bash
aws rds modify-db-instance \
  --db-instance-identifier junkos-prod-db \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00"
```

### Manual Backup Script

**`scripts/backup-db.sh`:**
```bash
#!/bin/bash
set -e

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
BACKUP_FILE="$BACKUP_DIR/junkos_backup_$DATE.sql.gz"
S3_BUCKET="s3://junkos-backups/database/"

echo "Starting backup at $(date)"

# Create backup directory
mkdir -p $BACKUP_DIR

# Dump database
pg_dump $DATABASE_URL | gzip > $BACKUP_FILE

# Upload to S3 (optional)
if command -v aws &> /dev/null; then
  aws s3 cp $BACKUP_FILE $S3_BUCKET
  echo "Uploaded to S3: $S3_BUCKET$BACKUP_FILE"
fi

# Keep only last 30 days locally
find $BACKUP_DIR -name "junkos_backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE"
echo "Size: $(du -h $BACKUP_FILE | cut -f1)"
```

**Schedule with cron:**
```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /path/to/backup-db.sh >> /var/log/junkos-backup.log 2>&1
```

### Backup Testing

**Monthly restoration drill:**

```bash
# Restore to test database
createdb junkos_test
gunzip -c backup_20260206_020000.sql.gz | psql junkos_test

# Verify data integrity
psql junkos_test -c "SELECT COUNT(*) FROM users;"
psql junkos_test -c "SELECT COUNT(*) FROM orders;"

# Cleanup
dropdb junkos_test
```

**Document in runbook:**
- RTO (Recovery Time Objective): 1 hour
- RPO (Recovery Point Objective): 24 hours (daily backups)

---

## 📈 Application Performance Monitoring (APM)

### Recommended Tools

| Tool | Best For | Cost |
|------|----------|------|
| **Sentry** | Error tracking + basic performance | Free (5k errors/month) |
| **New Relic** | Full APM, deep insights | $99/month |
| **Datadog** | APM + infrastructure | $15/host/month |
| **AWS CloudWatch** | AWS-native monitoring | $0.30/metric/month |

### Basic Performance Tracking

**Add middleware to track response times:**

```javascript
const prometheus = require('prom-client');

// Create metrics
const httpRequestDuration = new prometheus.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.1, 0.5, 1, 2, 5],
});

// Middleware
app.use((req, res, next) => {
  const start = Date.now();
  
  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    httpRequestDuration
      .labels(req.method, req.route?.path || req.path, res.statusCode)
      .observe(duration);
  });
  
  next();
});

// Expose metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', prometheus.register.contentType);
  res.end(await prometheus.register.metrics());
});
```

### Key Metrics to Monitor

**Golden Signals:**

1. **Latency** (response time)
   - p50, p95, p99 percentiles
   - Alert if p95 > 1000ms

2. **Traffic** (requests per second)
   - Track trends over time
   - Alert on sudden drops (outage) or spikes (attack)

3. **Errors** (error rate)
   - 4xx vs 5xx errors
   - Alert if error rate > 5%

4. **Saturation** (resource usage)
   - CPU > 80%
   - Memory > 90%
   - Database connections > 80%

---

## 🔥 Alert Configuration

### Alert Levels

| Level | Response Time | Examples |
|-------|--------------|----------|
| **Critical** | Immediate (5 min) | Service down, database unreachable |
| **High** | 30 minutes | Error rate > 10%, high latency |
| **Medium** | 4 hours | Elevated error rate, disk space low |
| **Low** | Next business day | SSL cert expiring in 30 days |

### Alert Channels

**Primary:**
- Email (always on)
- Slack (team channel)

**Critical only:**
- PagerDuty (on-call engineer)
- SMS (team lead)

### Example Alert Rules

#### Sentry Alert Rules

1. **Service Down:**
   - Condition: > 50 errors in 1 minute
   - Severity: Critical
   - Notify: Email + SMS + PagerDuty

2. **High Error Rate:**
   - Condition: Error rate > 5% for 5 minutes
   - Severity: High
   - Notify: Email + Slack

3. **New Error Type:**
   - Condition: First seen error
   - Severity: Medium
   - Notify: Slack only

#### UptimeRobot Alerts

1. **API Down:**
   - Trigger: 2 consecutive failed checks
   - Notify: Email + SMS
   - Re-alert: Every 30 minutes

2. **Slow Response:**
   - Trigger: Response time > 3 seconds
   - Notify: Email
   - Re-alert: Every 2 hours

#### Database Alerts (AWS CloudWatch)

```bash
# High CPU
aws cloudwatch put-metric-alarm \
  --alarm-name junkos-db-high-cpu \
  --alarm-description "Database CPU > 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# Low storage
aws cloudwatch put-metric-alarm \
  --alarm-name junkos-db-low-storage \
  --metric-name FreeStorageSpace \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 2000000000 \  # 2GB
  --comparison-operator LessThanThreshold \
  --evaluation-periods 1
```

---

## 📱 Incident Response

### Incident Workflow

1. **Detect** - Alert fires
2. **Acknowledge** - Engineer accepts alert
3. **Investigate** - Check logs, metrics, recent deploys
4. **Mitigate** - Rollback, restart, scale up, etc.
5. **Resolve** - Service restored
6. **Post-mortem** - Document what happened and how to prevent

### Runbook Template

**Service Down:**
1. Check uptime monitor (is it really down?)
2. Check recent deploys (rollback if needed)
3. Check logs for errors (Sentry, CloudWatch)
4. Check infrastructure (ECS, RDS, ALB)
5. Escalate if not resolved in 15 minutes

**High Error Rate:**
1. Check Sentry for error details
2. Identify affected endpoints
3. Check recent changes (last deploy)
4. Consider rollback if caused by deploy
5. Fix and deploy patch

**Database Issues:**
1. Check connection pool (exhausted?)
2. Check slow queries (performance issue?)
3. Check storage (disk full?)
4. Restart connections if needed
5. Scale database if under-resourced

### On-Call Schedule

Use PagerDuty, Opsgenie, or similar:
- Weekly rotations
- Primary + backup engineer
- Clear escalation path
- Documented runbooks

---

## 📊 Dashboard Setup

### Grafana Dashboard (Advanced)

If using Prometheus + Grafana:

**Key Panels:**
1. Request rate (requests/sec)
2. Response time (p50, p95, p99)
3. Error rate (% of requests)
4. Active database connections
5. Memory usage
6. CPU usage

### Simple Dashboard (Sentry)

Sentry provides built-in dashboards:
- Error frequency
- Affected users
- Release health
- Performance metrics

### CloudWatch Dashboard (AWS)

```bash
aws cloudwatch put-dashboard \
  --dashboard-name junkos-prod \
  --dashboard-body file://dashboard.json
```

---

## 🔐 Security Monitoring

### Log Security Events

```javascript
const winston = require('winston');

// Security event logger
const securityLogger = winston.createLogger({
  level: 'warn',
  format: winston.format.json(),
  transports: [
    new winston.transports.File({ filename: 'security.log' })
  ]
});

// Log authentication failures
app.post('/login', (req, res) => {
  if (!isValidLogin(req.body)) {
    securityLogger.warn('Failed login attempt', {
      ip: req.ip,
      username: req.body.username,
      timestamp: new Date().toISOString(),
    });
  }
});

// Log suspicious activity
app.use((req, res, next) => {
  if (isSuspicious(req)) {
    securityLogger.warn('Suspicious request', {
      ip: req.ip,
      path: req.path,
      userAgent: req.get('user-agent'),
    });
  }
  next();
});
```

### Enable AWS GuardDuty (AWS only)

```bash
aws guardduty create-detector --enable
```

Monitors for:
- Compromised instances
- Reconnaissance attempts
- Unusual API calls
- Cryptocurrency mining

---

## ✅ Post-Launch Checklist

### Week 1

- [ ] Monitor error rate daily (should be < 1%)
- [ ] Check uptime monitoring (should be 99.9%+)
- [ ] Review slow query logs
- [ ] Verify backups are running
- [ ] Test alert delivery (trigger test alert)
- [ ] Review Sentry errors, fix top 5

### Month 1

- [ ] Test backup restoration (disaster recovery drill)
- [ ] Review and optimize slow queries
- [ ] Analyze traffic patterns (peak times, endpoints)
- [ ] Check resource utilization (need to scale?)
- [ ] Review alert thresholds (too noisy? too quiet?)
- [ ] Update runbooks based on incidents

### Quarterly

- [ ] Security audit (dependency updates)
- [ ] Cost review (optimize resources)
- [ ] Load testing (can handle 2x traffic?)
- [ ] Disaster recovery drill (full restore)
- [ ] Review and update monitoring strategy

---

## 📚 Tools Summary

### Essential (Free Tier Available)

- **Sentry** - Error tracking (5k errors/month free)
- **UptimeRobot** - Uptime monitoring (50 monitors free)
- **CloudWatch** - AWS native monitoring (AWS only)

### Recommended (Paid)

- **PagerDuty** - On-call management ($19/user/month)
- **New Relic** - Full APM ($99/month)
- **Datadog** - Infrastructure + APM ($15/host/month)

### Cost-Effective Stack

**For startups ($0-20/month):**
- Sentry (free tier)
- UptimeRobot (free tier)
- CloudWatch Logs (AWS, ~$5/month)
- Manual database backups

**For growing companies ($50-100/month):**
- Sentry Pro ($26/month)
- PagerDuty ($19/user/month)
- New Relic or Datadog ($50+/month)
- Automated backups

---

## 🆘 Support Resources

**Sentry:**
- [Docs](https://docs.sentry.io)
- [Community Forum](https://forum.sentry.io)

**AWS CloudWatch:**
- [Docs](https://docs.aws.amazon.com/cloudwatch)
- [AWS Support](https://console.aws.amazon.com/support)

**UptimeRobot:**
- [Help Center](https://uptimerobot.com/help)

---

## Summary

**Monitoring is not optional.** You need:

✅ **Error tracking** (know when things break)  
✅ **Uptime monitoring** (know when service is down)  
✅ **Database backups** (recover from disasters)  
✅ **Alert rules** (get notified of problems)  
✅ **Incident runbooks** (respond quickly)

**Total setup time:** 2-3 hours  
**Total cost:** $0-50/month (depending on scale)  
**Peace of mind:** Priceless 😊

---

**Last Updated:** 2026-02-06  
**Version:** 1.0.0

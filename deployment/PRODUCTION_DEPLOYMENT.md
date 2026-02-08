# JunkOS Backend - Production Deployment Guide

Complete guide for deploying JunkOS backend to production with security best practices.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Setup](#database-setup)
4. [Deployment Options](#deployment-options)
5. [Environment Variables](#environment-variables)
6. [Stripe Configuration](#stripe-configuration)
7. [Domain & SSL Setup](#domain--ssl-setup)
8. [Database Migrations](#database-migrations)
9. [Monitoring & Logging](#monitoring--logging)
10. [Backup Strategy](#backup-strategy)
11. [Scaling Considerations](#scaling-considerations)
12. [Security Checklist](#security-checklist)

---

## Prerequisites

- [ ] PostgreSQL 14+ database (managed service recommended)
- [ ] Stripe account with production API keys
- [ ] Domain name configured
- [ ] SSL certificate (auto-provisioned by most platforms)
- [ ] Node.js 18+ runtime environment
- [ ] Git repository access
- [ ] Monitoring tools configured (Sentry, uptime monitoring)

---

## Environment Setup

### Production vs Staging

Always maintain separate environments:

| Environment | Purpose | Database | Stripe Keys | Domain |
|-------------|---------|----------|-------------|--------|
| **Production** | Live user traffic | Production DB | Live keys | app.junkos.com |
| **Staging** | Pre-release testing | Staging DB | Test keys | staging.junkos.com |
| **Development** | Local development | Local DB | Test keys | localhost:3000 |

**Best Practice:** Never use production credentials in staging/development environments.

---

## Database Setup

### Option 1: AWS RDS (Recommended for Enterprise)

**Advantages:**
- Automatic backups
- Multi-AZ deployment for high availability
- Read replicas for scaling
- Point-in-time recovery
- Enhanced monitoring

**Setup:**

1. **Create RDS Instance**
   ```bash
   # Via AWS Console or CLI
   aws rds create-db-instance \
     --db-instance-identifier junkos-prod \
     --db-instance-class db.t3.micro \
     --engine postgres \
     --engine-version 15.4 \
     --master-username junkosadmin \
     --master-user-password <STRONG_PASSWORD> \
     --allocated-storage 20 \
     --storage-type gp3 \
     --backup-retention-period 7 \
     --multi-az \
     --publicly-accessible false \
     --vpc-security-group-ids sg-xxxxxxxxx
   ```

2. **Security Group Configuration**
   - Only allow connections from your application's security group
   - No public access unless absolutely necessary
   - Use VPC peering or private subnets

3. **Connection String**
   ```
   postgresql://junkosadmin:<PASSWORD>@junkos-prod.xxxxx.us-east-1.rds.amazonaws.com:5432/junkos
   ```

### Option 2: Railway PostgreSQL (Recommended for Startups)

**Advantages:**
- Simple setup
- Automatic backups
- Built-in monitoring
- Cost-effective for small/medium scale

**Setup:**

1. Create Railway project
2. Add PostgreSQL plugin
3. Railway auto-generates `DATABASE_URL`
4. Enable daily backups in plugin settings

### Database Security Checklist

- [ ] Use strong, randomly generated passwords (32+ characters)
- [ ] Enable SSL/TLS for connections (enforce `sslmode=require`)
- [ ] Restrict access by IP/VPC security groups
- [ ] Regular automated backups (minimum daily)
- [ ] Test backup restoration process monthly
- [ ] Enable query logging for audit trails
- [ ] Use connection pooling (pg-pool or PgBouncer)

---

## Deployment Options

### 🚀 Option 1: Railway (Recommended - Easy)

**Best for:** Startups, MVPs, quick deployment

**Pros:**
- Fastest setup (< 15 minutes)
- Automatic SSL
- Built-in CI/CD from GitHub
- Integrated PostgreSQL
- Simple pricing

**See:** [RAILWAY_QUICKSTART.md](./RAILWAY_QUICKSTART.md)

**Cost:** $5-20/month

---

### 🏢 Option 2: AWS ECS/Fargate (Recommended - Enterprise)

**Best for:** Enterprise, high-scale, full control

**Pros:**
- Full AWS ecosystem integration
- Auto-scaling
- Load balancing
- High availability
- Advanced monitoring

**See:** [AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md)

**Cost:** $30-100+/month

---

### 🌊 Option 3: DigitalOcean App Platform

**Best for:** Mid-sized apps, simpler than AWS

**Setup Steps:**

1. **Connect Repository**
   - Log in to DigitalOcean
   - Create new App Platform app
   - Connect GitHub repository

2. **Configure Build**
   ```yaml
   # .do/app.yaml
   name: junkos-backend
   services:
     - name: api
       github:
         repo: your-username/junkos-backend
         branch: main
       build_command: npm install && npm run build
       run_command: npm start
       environment_slug: node-js
       instance_count: 1
       instance_size_slug: basic-xs
       envs:
         - key: NODE_ENV
           value: production
         - key: DATABASE_URL
           type: SECRET
         - key: STRIPE_SECRET_KEY
           type: SECRET
       health_check:
         http_path: /health
   ```

3. **Add Database**
   - Add managed PostgreSQL database
   - Automatically connects via `DATABASE_URL`

4. **Configure Domain**
   - Add custom domain in App settings
   - Configure DNS records
   - SSL auto-provisioned

**Cost:** $12-50/month

---

### ☁️ Option 4: Heroku

**Best for:** Quick prototypes, familiar platform

**Setup Steps:**

1. **Create Heroku App**
   ```bash
   heroku create junkos-backend
   heroku addons:create heroku-postgresql:mini
   ```

2. **Configure Buildpacks**
   ```bash
   heroku buildpacks:set heroku/nodejs
   ```

3. **Deploy**
   ```bash
   git push heroku main
   ```

4. **Set Environment Variables**
   ```bash
   heroku config:set NODE_ENV=production
   heroku config:set STRIPE_SECRET_KEY=sk_live_xxxxx
   ```

**Cost:** $7-25/month (Heroku pricing increased significantly in 2022)

---

## Environment Variables

### Required Variables

Create a `.env.production` template (DO NOT commit actual values):

```bash
# Application
NODE_ENV=production
PORT=8080
API_BASE_URL=https://api.junkos.com

# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname
DB_SSL=true
DB_POOL_MIN=2
DB_POOL_MAX=10

# Authentication & Security
JWT_SECRET=<GENERATE_256_BIT_KEY>
JWT_EXPIRATION=7d
SESSION_SECRET=<GENERATE_256_BIT_KEY>
CORS_ORIGIN=https://junkos.com,https://www.junkos.com

# Stripe
STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxxxxxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxxxxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxx

# Email (if using)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=<SENDGRID_API_KEY>
FROM_EMAIL=noreply@junkos.com

# Monitoring
SENTRY_DSN=https://xxxxx@sentry.io/xxxxx
LOG_LEVEL=info

# Rate Limiting
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100
```

### Generating Secure Secrets

```bash
# Generate JWT_SECRET (256-bit)
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# Generate SESSION_SECRET (256-bit)
openssl rand -hex 32

# Or use 1Password, LastPass, or similar password manager
```

### Environment Variable Management

**Best Practices:**

1. **Never commit secrets to Git**
   - Add `.env*` to `.gitignore`
   - Use `.env.example` for documentation

2. **Use platform secret management**
   - Railway: Environment variables UI
   - AWS: Secrets Manager or Parameter Store
   - DigitalOcean: App Platform encrypted environment variables

3. **Rotate secrets regularly**
   - JWT secrets: Every 6 months
   - Database passwords: Annually or on personnel changes
   - API keys: When compromised or per provider recommendations

4. **Principle of least privilege**
   - Only grant necessary permissions
   - Use separate API keys per environment

---

## Stripe Configuration

### Production Setup

1. **Activate Production Mode**
   - Complete Stripe account activation
   - Submit business information
   - Add bank account for payouts

2. **Get Production API Keys**
   - Dashboard → Developers → API keys
   - Copy `Secret key` (sk_live_xxx)
   - Copy `Publishable key` (pk_live_xxx)

3. **Configure Webhooks**

   **Webhook Endpoint:** `https://api.junkos.com/webhooks/stripe`

   **Events to Subscribe:**
   - `checkout.session.completed`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`

   **Security:**
   - Copy webhook signing secret (`whsec_xxx`)
   - Verify webhook signatures in your code:

   ```javascript
   const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
   
   app.post('/webhooks/stripe', 
     express.raw({ type: 'application/json' }),
     (req, res) => {
       const sig = req.headers['stripe-signature'];
       let event;
       
       try {
         event = stripe.webhooks.constructEvent(
           req.body,
           sig,
           process.env.STRIPE_WEBHOOK_SECRET
         );
       } catch (err) {
         return res.status(400).send(`Webhook Error: ${err.message}`);
       }
       
       // Handle event
       res.json({ received: true });
     }
   );
   ```

4. **Test Webhook Delivery**
   - Send test webhook from Stripe dashboard
   - Verify your endpoint receives and processes correctly
   - Check webhook logs in Stripe dashboard

### Security Best Practices

- [ ] **Never log full API keys** (only last 4 characters)
- [ ] **Always verify webhook signatures**
- [ ] **Use idempotency keys** for payment operations
- [ ] **Implement retry logic** with exponential backoff
- [ ] **Monitor failed webhook deliveries**
- [ ] **Set up Stripe Radar** for fraud prevention
- [ ] **Enable 3D Secure (SCA)** for European customers

---

## Domain & SSL Setup

### DNS Configuration

Point your domain to your deployment:

**For Railway/Heroku:**
```
CNAME  api.junkos.com  →  your-app.railway.app
```

**For AWS (with Load Balancer):**
```
A      api.junkos.com  →  52.1.2.3 (ELB IP)
CNAME  api.junkos.com  →  junkos-alb-123456.us-east-1.elb.amazonaws.com
```

**For DigitalOcean:**
```
CNAME  api.junkos.com  →  your-app.ondigitalocean.app
```

### SSL/TLS Certificate

**Most platforms auto-provision SSL:**
- Railway: Automatic Let's Encrypt
- AWS: Use ACM (AWS Certificate Manager)
- DigitalOcean: Automatic Let's Encrypt
- Heroku: Automatic Let's Encrypt (paid plans)

**Manual SSL Setup (if needed):**

1. **Generate Certificate with Certbot**
   ```bash
   certbot certonly --standalone -d api.junkos.com
   ```

2. **Configure in your platform**
   - Upload certificate
   - Configure automatic renewal

**Security Headers:**

Add these to your Express app:

```javascript
const helmet = require('helmet');

app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
    },
  },
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true,
    preload: true
  },
}));

// Force HTTPS
app.use((req, res, next) => {
  if (req.header('x-forwarded-proto') !== 'https') {
    res.redirect(`https://${req.header('host')}${req.url}`);
  } else {
    next();
  }
});
```

---

## Database Migrations

### Migration Strategy

**Golden Rule:** Never run migrations manually on production.

### Setup Migration System

Using **Knex.js** (example):

```javascript
// knexfile.js
module.exports = {
  production: {
    client: 'postgresql',
    connection: process.env.DATABASE_URL,
    pool: { min: 2, max: 10 },
    migrations: {
      directory: './db/migrations',
      tableName: 'knex_migrations'
    },
    ssl: { rejectUnauthorized: false }
  }
};
```

### Migration Best Practices

1. **Always test migrations on staging first**
2. **Write reversible migrations (up/down)**
3. **Avoid data loss** (rename/transform, don't drop)
4. **Use transactions** where possible
5. **Create backups before running migrations**

### Running Migrations on Production

**Option 1: As part of deployment (Railway/Heroku)**

Add to `package.json`:
```json
{
  "scripts": {
    "start": "node server.js",
    "deploy": "npm run migrate && npm start",
    "migrate": "knex migrate:latest"
  }
}
```

**Option 2: Separate migration job (AWS ECS)**

Create a one-off task:
```bash
aws ecs run-task \
  --cluster junkos-prod \
  --task-definition junkos-migrate \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"
```

**Option 3: Manual with safety**

```bash
# 1. Create backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Run migration in transaction (if supported)
psql $DATABASE_URL -c "BEGIN; \i migration.sql; COMMIT;"

# 3. Verify migration
psql $DATABASE_URL -c "SELECT * FROM knex_migrations ORDER BY id DESC LIMIT 5;"
```

### Rollback Plan

Always have a rollback strategy:

```bash
# Rollback last migration
npm run migrate:rollback

# Or restore from backup
psql $DATABASE_URL < backup_20260206_153000.sql
```

---

## Monitoring & Logging

### Sentry (Error Tracking)

1. **Install Sentry**
   ```bash
   npm install @sentry/node @sentry/tracing
   ```

2. **Configure**
   ```javascript
   const Sentry = require('@sentry/node');
   const Tracing = require('@sentry/tracing');
   
   Sentry.init({
     dsn: process.env.SENTRY_DSN,
     environment: process.env.NODE_ENV,
     tracesSampleRate: 0.1, // 10% of transactions
     integrations: [
       new Sentry.Integrations.Http({ tracing: true }),
       new Tracing.Integrations.Express({ app }),
     ],
   });
   
   // Request handler must be first
   app.use(Sentry.Handlers.requestHandler());
   app.use(Sentry.Handlers.tracingHandler());
   
   // Error handler must be last
   app.use(Sentry.Handlers.errorHandler());
   ```

### CloudWatch Logs (AWS)

**For ECS/Fargate:**
```json
{
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/junkos-backend",
      "awslogs-region": "us-east-1",
      "awslogs-stream-prefix": "ecs"
    }
  }
}
```

**Query logs:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/junkos-backend \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
```

### Application Logging

Use structured logging:

```javascript
const winston = require('winston');

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.json(),
  defaultMeta: { service: 'junkos-backend' },
  transports: [
    new winston.transports.Console({
      format: winston.format.simple()
    })
  ]
});

// Log with context
logger.info('Payment processed', {
  userId: user.id,
  amount: 1000,
  currency: 'usd',
  stripeId: 'ch_xxx'
});
```

### Key Metrics to Monitor

- **Response time** (p50, p95, p99)
- **Error rate** (5xx responses)
- **Request rate** (requests/second)
- **Database connection pool** utilization
- **Memory usage**
- **CPU usage**
- **Disk I/O** (if applicable)

### Alerting Rules

Set up alerts for:

- Error rate > 5% for 5 minutes
- Response time p95 > 1000ms for 5 minutes
- Database connections > 80% pool for 10 minutes
- Memory usage > 90% for 5 minutes
- No requests received for 5 minutes (downtime)

**See:** [monitoring-checklist.md](./monitoring-checklist.md) for detailed setup.

---

## Backup Strategy

### Database Backups

**Automated Daily Backups:**

**AWS RDS:**
- Automatic backups enabled (retention: 7-35 days)
- Manual snapshots before major changes
- Enable point-in-time recovery

**Railway:**
- Enable daily backups in plugin settings
- Download backups weekly to S3/local storage

**Manual Backup Script:**

```bash
#!/bin/bash
# backup-db.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="junkos_backup_$DATE.sql.gz"
S3_BUCKET="s3://junkos-backups/database/"

# Create backup
pg_dump $DATABASE_URL | gzip > $BACKUP_FILE

# Upload to S3
aws s3 cp $BACKUP_FILE $S3_BUCKET

# Keep only last 30 days locally
find . -name "junkos_backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE"
```

**Schedule with cron:**
```bash
0 2 * * * /path/to/backup-db.sh >> /var/log/backup.log 2>&1
```

### Backup Testing

- [ ] Test restore process monthly
- [ ] Document restore procedures
- [ ] Measure recovery time (RTO)
- [ ] Verify data integrity post-restore

### Application Code Backups

- [ ] Git repository with off-site backup (GitHub)
- [ ] Tag releases (v1.0.0, v1.1.0)
- [ ] Store compiled artifacts for quick rollback
- [ ] Document deployment procedures

---

## Scaling Considerations

### Horizontal Scaling

**Application Servers:**
- Add more instances behind load balancer
- Ensure stateless application (use Redis for sessions)
- Use sticky sessions if state is unavoidable

**Database Scaling:**
- Read replicas for read-heavy workloads
- Connection pooling (PgBouncer)
- Query optimization and indexing
- Consider sharding for very large datasets

### Vertical Scaling

**When to scale up:**
- CPU consistently > 70%
- Memory consistently > 80%
- Database IOPS maxed out

**Typical progression:**
1. Start: 1 CPU, 512MB RAM (Railway basic)
2. Growth: 2 CPU, 2GB RAM
3. Scale: 4 CPU, 8GB RAM
4. Enterprise: Multiple instances + load balancer

### Performance Optimization

```javascript
// 1. Database connection pooling
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// 2. Response caching
const redis = require('redis');
const client = redis.createClient(process.env.REDIS_URL);

app.get('/api/items', async (req, res) => {
  const cacheKey = 'items:all';
  const cached = await client.get(cacheKey);
  
  if (cached) {
    return res.json(JSON.parse(cached));
  }
  
  const items = await db.query('SELECT * FROM items');
  await client.setEx(cacheKey, 300, JSON.stringify(items)); // 5 min cache
  
  res.json(items);
});

// 3. Compression
const compression = require('compression');
app.use(compression());

// 4. Rate limiting
const rateLimit = require('express-rate-limit');
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
});
app.use('/api/', limiter);
```

### Caching Strategy

- **CDN:** Static assets (images, CSS, JS)
- **Redis:** Session data, frequently accessed data
- **Database:** Query result caching
- **HTTP:** Cache-Control headers for API responses

---

## Security Checklist

### Pre-Deployment

- [ ] Environment variables secured (not in code)
- [ ] Database uses SSL/TLS connections
- [ ] Strong passwords (32+ characters, random)
- [ ] CORS configured (whitelist domains only)
- [ ] Rate limiting enabled
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (sanitize user input)
- [ ] CSRF protection (if using cookies)
- [ ] Security headers configured (helmet.js)
- [ ] HTTPS enforced (no HTTP)
- [ ] Dependencies updated (no critical vulnerabilities)
- [ ] API authentication required (JWT/OAuth)
- [ ] Webhook signatures verified (Stripe)

### Post-Deployment

- [ ] Error monitoring active (Sentry)
- [ ] Uptime monitoring configured
- [ ] Log aggregation working
- [ ] Backups automated and tested
- [ ] SSL certificate auto-renewal enabled
- [ ] Security scanning scheduled (npm audit, Snyk)
- [ ] Incident response plan documented
- [ ] Access controls reviewed (least privilege)
- [ ] Audit logging enabled

### Regular Maintenance

- **Weekly:**
  - Review error logs
  - Check uptime reports
  - Monitor performance metrics

- **Monthly:**
  - Update dependencies (`npm audit fix`)
  - Review access controls
  - Test backup restoration
  - Review and rotate logs

- **Quarterly:**
  - Security audit
  - Load testing
  - Disaster recovery drill
  - Review and update documentation

---

## Deployment Checklist

### Pre-Launch

- [ ] All tests passing
- [ ] Staging environment matches production
- [ ] Database migrations tested on staging
- [ ] Environment variables configured
- [ ] SSL certificate active
- [ ] Monitoring tools configured
- [ ] Backup strategy implemented
- [ ] Load testing completed
- [ ] Security scan passed
- [ ] Documentation updated

### Launch Day

- [ ] Create database backup
- [ ] Deploy to production
- [ ] Run database migrations
- [ ] Verify health check endpoint
- [ ] Test critical user flows
- [ ] Monitor error rates
- [ ] Check logs for issues
- [ ] Verify webhook deliveries (Stripe)

### Post-Launch

- [ ] Monitor for 2-4 hours
- [ ] Review performance metrics
- [ ] Check error tracking (Sentry)
- [ ] Verify backups created
- [ ] Document any issues
- [ ] Update runbook with lessons learned

---

## Rollback Plan

If deployment fails:

1. **Stop new traffic** (disable load balancer targets)
2. **Assess issue** (check logs, error tracking)
3. **Decide:** Fix forward vs. rollback
4. **If rollback:**
   - Deploy previous version
   - Rollback database migrations (if needed)
   - Restore from backup (if data corruption)
5. **Verify:** Test critical flows
6. **Post-mortem:** Document issue and prevention

---

## Support & Resources

- **Railway Docs:** https://docs.railway.app
- **AWS ECS Docs:** https://docs.aws.amazon.com/ecs
- **Stripe Docs:** https://stripe.com/docs
- **Sentry Docs:** https://docs.sentry.io
- **PostgreSQL Docs:** https://www.postgresql.org/docs

---

## Next Steps

1. Choose your deployment platform
2. Follow platform-specific guide:
   - [Railway Quickstart](./RAILWAY_QUICKSTART.md) for quick setup
   - [AWS Deployment](./AWS_DEPLOYMENT.md) for enterprise setup
3. Configure monitoring: [Monitoring Checklist](./monitoring-checklist.md)
4. Schedule regular maintenance tasks
5. Document your specific deployment procedures

---

**Last Updated:** 2026-02-06  
**Version:** 1.0.0

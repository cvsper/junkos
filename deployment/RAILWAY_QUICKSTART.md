# Deploy Umuve Backend to Railway in 15 Minutes 🚀

Get your Umuve backend live in production with Railway - the fastest path from code to deployed.

## Why Railway?

- ✅ **Zero DevOps** - No server management, no Docker wrestling
- ✅ **Integrated Database** - PostgreSQL included, auto-connected
- ✅ **Automatic SSL** - HTTPS enabled by default
- ✅ **Git Deploy** - Push to deploy, automatic builds
- ✅ **Cost Effective** - $5-20/month for most apps
- ✅ **Great DX** - Clean UI, simple workflows

**Perfect for:** MVPs, startups, solo developers, side projects

---

## Prerequisites

- [ ] GitHub account with Umuve backend repo
- [ ] Stripe account (test mode is fine to start)
- [ ] Domain name (optional, Railway provides subdomain)
- [ ] 15 minutes ⏱️

---

## Step 1: Create Railway Account (2 min)

1. Go to [railway.app](https://railway.app)
2. Click **"Start a New Project"**
3. Sign in with GitHub
4. **Trial:** $5 free credit, no card required
5. **Hobby Plan:** $5/month + usage (~$15-20 typical)

---

## Step 2: Deploy from GitHub (3 min)

### Option A: One-Click Deploy Template

If your repo has a `railway.json` or `railway.toml`:

1. Click **"Deploy from GitHub"**
2. Select repository: `your-username/umuve-backend`
3. Railway automatically:
   - Detects Node.js
   - Installs dependencies
   - Builds your app
   - Deploys it

### Option B: Manual Setup

1. **New Project** → **Deploy from GitHub repo**
2. Authorize Railway to access your GitHub
3. Select repository: `umuve-backend`
4. Select branch: `main`
5. Railway auto-detects `package.json`
6. Click **"Deploy Now"**

**Build Settings (auto-detected):**
```json
{
  "build": "npm install",
  "start": "npm start"
}
```

---

## Step 3: Add PostgreSQL Database (1 min)

1. In your project, click **"New"** → **"Database"** → **"Add PostgreSQL"**
2. Railway automatically:
   - Provisions database
   - Creates `DATABASE_URL` environment variable
   - Links it to your service

**Connection string auto-injected:**
```
DATABASE_URL=postgresql://postgres:xxxxx@containers.railway.app:6543/railway
```

**Verify database connection:**
- Click PostgreSQL plugin
- See **"Data"** tab (query interface)
- Check **"Connect"** tab for connection details

---

## Step 4: Configure Environment Variables (5 min)

Click your service → **"Variables"** tab

### Required Variables

```bash
# Application
NODE_ENV=production
PORT=8080

# Database (auto-created by Railway)
# DATABASE_URL=postgresql://... (already set)

# JWT & Security
JWT_SECRET=your-256-bit-secret-here
SESSION_SECRET=your-256-bit-secret-here
CORS_ORIGIN=https://goumuve.com

# Stripe (use test keys first)
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxxxxx
STRIPE_PUBLISHABLE_KEY=pk_test_xxxxxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxx
```

### Generate Secrets

```bash
# In your terminal:
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# Copy output to JWT_SECRET and SESSION_SECRET
```

### Add Variables in Railway

1. Click **"New Variable"**
2. Enter name (e.g., `JWT_SECRET`)
3. Paste value
4. Repeat for all variables

**Pro Tip:** Use **"Raw Editor"** to paste all at once:
```
NODE_ENV=production
PORT=8080
JWT_SECRET=abc123...
STRIPE_SECRET_KEY=sk_test_...
```

---

## Step 5: Set Up Stripe Webhooks (2 min)

1. Get your Railway URL:
   - Go to your service → **"Settings"** → **"Domains"**
   - Copy generated URL (e.g., `umuve-backend-production.up.railway.app`)

2. Configure Stripe webhook:
   - [Stripe Dashboard](https://dashboard.stripe.com/webhooks)
   - Click **"Add endpoint"**
   - URL: `https://your-app.up.railway.app/webhooks/stripe`
   - Events: Select all `checkout.*`, `customer.subscription.*`, `payment_intent.*`
   - Click **"Add endpoint"**
   - Copy **"Signing secret"** (whsec_xxx)

3. Add webhook secret to Railway:
   - Back to Railway → Variables
   - Add `STRIPE_WEBHOOK_SECRET=whsec_xxxxx`

---

## Step 6: Custom Domain (Optional, 2 min)

### Add Your Domain

1. **Railway:** Your service → **"Settings"** → **"Domains"**
2. Click **"Custom Domain"**
3. Enter: `api.goumuve.com`
4. Railway shows DNS records to add

### Configure DNS

In your domain registrar (Namecheap, Cloudflare, etc.):

```
Type   Name   Value
CNAME  api    your-app.up.railway.app
```

**SSL:** Railway auto-provisions Let's Encrypt certificate (1-5 minutes)

**Verify:**
```bash
curl https://api.goumuve.com/health
```

---

## Step 7: Run Database Migrations (1 min)

### Option 1: Add to Start Script

Update `package.json`:
```json
{
  "scripts": {
    "start": "npm run migrate && node server.js",
    "migrate": "knex migrate:latest"
  }
}
```

Railway runs this on every deploy.

### Option 2: One-Time Migration

1. Railway service → **"Settings"** → **"One-off Command"**
2. Enter: `npm run migrate`
3. Click **"Run"**
4. Monitor logs for success

---

## Step 8: Monitor & Verify (1 min)

### Check Deployment

1. **Logs:** Service → **"Deployments"** → Latest deploy → **"View Logs"**
2. **Health:** Visit `https://your-app.up.railway.app/health`
3. **Metrics:** Service → **"Metrics"** (CPU, memory, requests)

### Test API

```bash
# Health check
curl https://your-app.up.railway.app/health

# Test endpoint
curl https://your-app.up.railway.app/api/items
```

---

## Cost Breakdown 💰

Railway pricing is usage-based:

| Resource | Usage | Cost |
|----------|-------|------|
| **Subscription** | Hobby Plan | $5/month |
| **Compute** | ~$0.000231/min (~$10/month for 24/7) | ~$10/month |
| **Database** | 1GB storage | $0.25/GB (~$0.25) |
| **Egress** | 100GB included | Free (then $0.10/GB) |
| **Total** | Typical usage | **$15-20/month** |

**Free tier:** $5 credit/month (enough for hobby projects)

**Scaling costs:**
- Add 1 CPU: +$5/month
- Add 1GB RAM: +$2/month
- Add read replica: +$5/month

---

## Post-Deployment Checklist

### Immediate

- [ ] Health endpoint responding
- [ ] Database connected (check logs)
- [ ] Environment variables set
- [ ] Stripe webhooks receiving events
- [ ] SSL certificate active

### Next 24 Hours

- [ ] Set up monitoring (see [monitoring-checklist.md](./monitoring-checklist.md))
- [ ] Enable automatic backups (PostgreSQL plugin → Settings)
- [ ] Add uptime monitoring (UptimeRobot, free)
- [ ] Test critical user flows
- [ ] Document any deployment-specific notes

### Weekly

- [ ] Review Railway logs for errors
- [ ] Check metrics (CPU, memory)
- [ ] Monitor costs in Railway dashboard
- [ ] Download database backup manually

---

## Common Issues & Fixes

### Build Fails

**Issue:** `npm install` errors

**Fix:**
1. Check Node.js version in Railway matches your local
2. Set in `package.json`:
   ```json
   {
     "engines": {
       "node": "18.x"
     }
   }
   ```

### Database Connection Fails

**Issue:** `ECONNREFUSED` or timeout errors

**Fix:**
1. Verify `DATABASE_URL` variable is set
2. Check PostgreSQL plugin is running (green status)
3. Restart your service

### Port Issues

**Issue:** App not responding, but logs show success

**Fix:**
Railway expects your app to listen on `process.env.PORT`:
```javascript
const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
});
```

### Webhook Signature Fails

**Issue:** Stripe webhook signature verification errors

**Fix:**
1. Verify `STRIPE_WEBHOOK_SECRET` matches Stripe dashboard
2. Check webhook is sent to correct URL
3. Ensure `express.raw()` middleware for webhook route:
   ```javascript
   app.post('/webhooks/stripe', 
     express.raw({ type: 'application/json' }),
     handleWebhook
   );
   ```

---

## Deployment Workflow

### Regular Deploys

Railway auto-deploys on git push:

```bash
git add .
git commit -m "Add new feature"
git push origin main
```

Railway automatically:
1. Detects push
2. Builds new image
3. Runs tests (if configured)
4. Deploys with zero downtime
5. Keeps previous version for rollback

### Rollback

If something breaks:

1. Service → **"Deployments"**
2. Find last working deploy
3. Click **⋯** → **"Redeploy"**
4. Instant rollback to previous version

---

## Scaling Your Railway App

### Vertical Scaling (More Resources)

When CPU/memory consistently high:

1. Service → **"Settings"** → **"Resources"**
2. Increase vCPU or RAM
3. Railway adjusts pricing automatically

**Recommendations:**
- **Startup:** 0.5 vCPU, 512MB RAM
- **Growth:** 1 vCPU, 1GB RAM
- **Scale:** 2 vCPU, 2GB RAM

### Horizontal Scaling (Multiple Instances)

For high traffic:

1. **Settings** → **"Replicas"**
2. Set replica count (2-10)
3. Railway auto-balances traffic

**Note:** Requires stateless app (use Redis for sessions)

### Database Scaling

When database is bottleneck:

1. **Add Read Replica:**
   - PostgreSQL plugin → Settings → Add replica
   - Use for read-heavy queries

2. **Increase Storage:**
   - Plugin → Settings → Increase volume size

3. **Connection Pooling:**
   ```javascript
   const { Pool } = require('pg');
   const pool = new Pool({
     connectionString: process.env.DATABASE_URL,
     max: 20, // connection pool size
   });
   ```

---

## Security Best Practices

- [ ] **Never commit `.env` files** to Git
- [ ] **Use Railway's secret variables** (not regular variables) for sensitive data
- [ ] **Enable 2FA** on Railway account
- [ ] **Restrict CORS origins** (don't use `*`)
- [ ] **Rate limit API endpoints**
- [ ] **Validate all user inputs**
- [ ] **Keep dependencies updated** (`npm audit fix`)
- [ ] **Monitor error logs** daily

---

## Backup Strategy

### Automatic Backups

1. PostgreSQL plugin → **"Settings"**
2. Enable **"Automatic Backups"** (daily at 2 AM UTC)
3. Set retention period (7-30 days)

### Manual Backup

```bash
# Export database
railway run pg_dump $DATABASE_URL > backup.sql

# Or via Railway CLI
railway connect postgres
pg_dump railway > backup_$(date +%Y%m%d).sql
```

### Restore from Backup

```bash
railway run psql $DATABASE_URL < backup.sql
```

**Test restores monthly!**

---

## Monitoring Setup (5 min)

### 1. Add Sentry (Error Tracking)

```bash
npm install @sentry/node
```

```javascript
const Sentry = require('@sentry/node');
Sentry.init({ dsn: process.env.SENTRY_DSN });
```

Add `SENTRY_DSN` to Railway variables.

### 2. UptimeRobot (Free Uptime Monitoring)

1. [UptimeRobot](https://uptimerobot.com) → Free account
2. Add monitor: `https://your-app.up.railway.app/health`
3. Set check interval: 5 minutes
4. Add email alerts

### 3. Railway Metrics

Built-in metrics show:
- CPU usage
- Memory usage
- Request count
- Response times

Access: Service → **"Metrics"** tab

---

## Railway CLI (Optional Power Users)

Install Railway CLI for advanced workflows:

```bash
# Install
npm i -g @railway/cli

# Login
railway login

# Link project
railway link

# View logs
railway logs

# Run commands with production env
railway run npm run migrate

# Shell into production
railway run bash
```

---

## Next Steps

### Production Checklist

- [ ] Switch Stripe to production keys
- [ ] Add custom domain
- [ ] Enable automatic database backups
- [ ] Set up error monitoring (Sentry)
- [ ] Add uptime monitoring (UptimeRobot)
- [ ] Configure log retention
- [ ] Document deployment process
- [ ] Test backup restoration

### Learn More

- [Railway Docs](https://docs.railway.app)
- [Railway Templates](https://railway.app/templates)
- [Railway Discord](https://discord.gg/railway)

### Other Deployment Options

Need more control or different features?

- **AWS Deployment:** See [AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md)
- **Full Comparison:** See [PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)

---

## Support

**Railway Issues:**
- [Railway Discord](https://discord.gg/railway)
- [Railway Feedback](https://feedback.railway.app)
- [Status Page](https://status.railway.app)

**Umuve Backend Issues:**
- Check application logs in Railway
- Review [PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)
- Monitor Sentry for errors

---

## Summary

You've deployed Umuve backend to production! 🎉

**What you've accomplished:**
- ✅ Backend deployed with automatic HTTPS
- ✅ PostgreSQL database provisioned
- ✅ Environment variables configured
- ✅ Stripe webhooks connected
- ✅ Custom domain (optional)
- ✅ Automatic deploys on git push

**Total time:** ~15 minutes  
**Total cost:** $15-20/month  
**Maintenance:** Minimal (automatic updates, backups)

**Railway handles:**
- Server management
- SSL certificates
- Automatic scaling
- Zero-downtime deploys
- Database backups
- Monitoring

**You focus on:**
- Building features
- Fixing bugs
- Growing your product

---

**Last Updated:** 2026-02-06  
**Version:** 1.0.0

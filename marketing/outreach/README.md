# Umuve Cold Email Outreach Campaign

Complete cold email automation system for customer acquisition targeting junk removal and hauling companies.

---

## 📁 Campaign Files

- **`prospect-list-template.csv`** — Template for prospect data
- **`sequence-a-pain-point.md`** — Pain-point focused emails (3 emails)
- **`sequence-b-benefit.md`** — Benefit-focused emails (3 emails)  
- **`sequence-c-social-proof.md`** — Social-proof focused emails (3 emails)
- **`outreach-script.py`** — Python automation script
- **`README.md`** — This file

---

## 🎯 Campaign Strategy

### Target Audience
Small to mid-sized junk removal and hauling companies with 2-10 trucks struggling with:
- Manual quoting processes
- Dispatch chaos
- No-shows and cancellations
- Administrative overhead

### Messaging Approach
1. **Sequence A (Pain-Point)** — Emphasize current struggles (slow quotes, no-shows, dispatch)
2. **Sequence B (Benefit)** — Show growth outcomes (3→10 trucks, time savings)
3. **Sequence C (Social Proof)** — Leverage peer success (500+ companies, local case studies)

### A/B Testing
Test all three sequences with equal prospect splits to identify highest-converting approach.

**Success Metrics:**
- Open rate: Target 40%+
- Reply rate: Target 8-12%
- Demo booking rate: Target 3-5%

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install mailgun  # or: pip install sendgrid
```

### 2. Set Up Environment Variables

```bash
# For Mailgun
export MAILGUN_API_KEY="your-mailgun-api-key"
export MAILGUN_DOMAIN="mg.yourdomain.com"

# OR for SendGrid
export SENDGRID_API_KEY="your-sendgrid-api-key"
```

### 3. Add Your Prospects

Edit `prospect-list-template.csv`:
```csv
name,company,email,city,truck_count
John Smith,Smith Hauling LLC,john@smithhauling.com,Austin,3
```

### 4. Test in Dry-Run Mode

```bash
python outreach-script.py --csv prospect-list-template.csv --sequence A
```

Review output to ensure personalization is working correctly.

### 5. Send Real Emails

```bash
python outreach-script.py --csv prospect-list-template.csv --sequence B --live
```

---

## 📧 Email Sequences

### Sequence A: Pain-Point Focused
**Best for:** Prospects with obvious operational pain points  
**Tone:** Direct, problem-focused, conversational  
**CTA:** Low-commitment ("10-minute look", "show me")

- **Email 1:** Slow quoting → losing jobs
- **Email 2:** No-shows case study
- **Email 3:** "What's your dispatch process?"

### Sequence B: Benefit-Focused
**Best for:** Growth-minded operators  
**Tone:** Aspirational, results-driven  
**CTA:** Progressive (demo → trial → setup call)

- **Email 1:** Growth story (3→10 trucks)
- **Email 2:** 2-minute demo video
- **Email 3:** Free trial offer

### Sequence C: Social-Proof Focused
**Best for:** Skeptical prospects, late adopters  
**Tone:** Evidence-based, peer-validated  
**CTA:** Social proof → screen share

- **Email 1:** 500+ companies switched
- **Email 2:** Local competitor success (+23% revenue)
- **Email 3:** Simple screen share offer

---

## ⚙️ Script Configuration

Edit `CONFIG` in `outreach-script.py`:

```python
CONFIG = {
    'service': 'mailgun',  # or 'sendgrid'
    'from_email': 'sales@goumuve.com',
    'from_name': 'Alex from Umuve',
    'email_delays': [0, 2, 5],  # Days between emails
    'track_opens': True,
    'track_clicks': True,
    'dry_run': True,  # Set False to send
}
```

---

## 📊 Tracking & Analytics

### Built-in Tracking
- Open tracking (pixel-based)
- Click tracking (link wrapping)
- Campaign logs (JSON output)

### View Analytics

```bash
python outreach-script.py --track
```

Or check your email service dashboard:
- **Mailgun:** https://app.mailgun.com/analytics
- **SendGrid:** https://app.sendgrid.com/statistics

### Campaign Logs
Each campaign run generates a JSON log:
```
campaign-log-A-20260206-150830.json
```

Contains:
- Prospects contacted
- Email send status
- Scheduled send dates
- Personalization data

---

## ✅ Best Practices

### 1. Prospect Research
- Verify email addresses (use Hunter.io, Clearbit, etc.)
- Check company websites for current pain points
- Confirm truck count and city data
- Look for recent reviews mentioning operational issues

### 2. Personalization
- Use real company names (never "{{company}}")
- Reference local competitors when possible
- Adjust truck count references (don't mention if unknown)
- Vary subject lines within each sequence

### 3. Sending Strategy
- **Volume:** Start with 20-50 prospects per week
- **Timing:** Send Tuesday-Thursday, 9-11 AM local time
- **Spacing:** Wait 2-3 days between follow-ups
- **Testing:** Run A/B tests for 100+ prospects before scaling

### 4. Response Handling
- Reply within 1 hour during business hours
- Offer specific times for demos (don't make them suggest)
- Send calendar invite immediately after booking
- Follow up if they miss the demo (they're busy!)

### 5. List Hygiene
- Remove hard bounces immediately
- Unsubscribe anyone who replies "not interested"
- Mark "out of business" prospects
- Update CSV with response status

---

## ⚖️ Legal Compliance (CAN-SPAM Act)

### Required Elements
All emails MUST include:

1. ✅ **Accurate "From" header** — Use real name and company
2. ✅ **Honest subject lines** — No deceptive subjects
3. ✅ **Physical address** — Add to email footer:
   ```
   Umuve Inc.
   123 Main Street, Suite 100
   Austin, TX 78701
   ```
4. ✅ **Unsubscribe mechanism** — Add to footer:
   ```
   Don't want to hear from us? Reply with "unsubscribe"
   ```
5. ✅ **Honor opt-outs within 10 days**

### Penalties
- Up to $50,120 per violation
- Criminal charges for egregious cases

### Safe Practices
- **Do** send B2B emails to company addresses (generally permissible)
- **Don't** use purchased/scraped lists
- **Don't** hide your identity
- **Don't** keep emailing after opt-out
- **Do** keep records of opt-outs for 3+ years

### GDPR Considerations (if targeting EU)
- Requires "legitimate interest" or consent
- Must provide privacy policy link
- More strict than CAN-SPAM

**Recommendation:** Consult legal counsel before sending to EU prospects.

---

## 🔧 Advanced Features

### Scheduling with Cron

Add to crontab for automated daily sends:
```bash
# Send 20 prospects per day at 9 AM
0 9 * * * cd ~/Documents/programs/webapps/umuve/marketing/outreach && python outreach-script.py --csv daily-prospects.csv --sequence A --live
```

### Integration with CRM

Connect to HubSpot, Pipedrive, or Salesforce:
```python
# Example: Update HubSpot after email sent
import requests

def update_crm(email, status):
    requests.post(
        'https://api.hubapi.com/contacts/v1/contact/email/{email}/profile',
        headers={'Authorization': f'Bearer {HUBSPOT_KEY}'},
        json={'properties': [{'property': 'last_outreach', 'value': status}]}
    )
```

### Reply Detection

Use email service webhooks to detect replies:
```python
# Flask webhook endpoint example
from flask import Flask, request

@app.route('/mailgun/webhook', methods=['POST'])
def handle_reply():
    data = request.json
    if data.get('event') == 'replied':
        # Mark prospect as "replied" in database
        # Send notification to sales team
        pass
```

---

## 📈 Campaign Optimization

### Week 1-2: Testing Phase
- Send 100 prospects split evenly (33/33/34) across A/B/C
- Track open rates, reply rates, demo bookings
- Identify winning sequence

### Week 3-4: Scaling Phase
- Double down on winning sequence
- A/B test subject line variations
- Refine personalization based on replies

### Month 2+: Optimization
- Test different CTAs
- Adjust email timing (day/hour)
- Segment by truck count (2-3 trucks vs. 5-10 trucks)
- Create custom sequences for high-value prospects

### Key Metrics to Track
| Metric | Target | Action if Below |
|--------|--------|-----------------|
| Open Rate | 40%+ | Improve subject lines |
| Reply Rate | 10%+ | Strengthen personalization |
| Positive Reply | 5%+ | Refine value proposition |
| Demo Booking | 3%+ | Simplify CTA, reduce friction |

---

## 🆘 Troubleshooting

### Emails Going to Spam
- Warm up your sending domain (start with 20/day, increase slowly)
- Use SPF/DKIM/DMARC authentication
- Avoid spam trigger words ("free", "guarantee", "$$$")
- Keep HTML minimal (plain text preferred)

### Low Open Rates
- Test different subject lines
- Send at different times (9-11 AM is usually best)
- Check sender reputation (use mail-tester.com)

### No Replies
- Emails might be too long (aim for 60-80 words)
- CTA unclear or too demanding
- Not enough personalization
- Wrong target audience (they don't have the problem you're solving)

### Script Errors
```bash
# Test without sending
python outreach-script.py --csv test.csv --sequence A

# Check API credentials
echo $MAILGUN_API_KEY  # Should output your key

# Verify CSV format
cat prospect-list-template.csv
```

---

## 📚 Resources

- [CAN-SPAM Act Compliance](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business)
- [Mailgun API Docs](https://documentation.mailgun.com)
- [SendGrid API Docs](https://docs.sendgrid.com)
- [Cold Email Best Practices](https://www.coldoutreach.com/cold-email-guide)

---

## 🚨 Final Checklist

Before sending your first campaign:

- [ ] Prospects verified (real emails, correct data)
- [ ] Email service configured (API keys set)
- [ ] Sender domain authenticated (SPF/DKIM)
- [ ] Footer includes physical address
- [ ] Unsubscribe mechanism in place
- [ ] Tested in dry-run mode
- [ ] Reviewed for typos/personalization errors
- [ ] Scheduled reply monitoring
- [ ] CRM/tracking system ready

---

**Questions?** Contact the Umuve team or review the [Sales Playbook](https://goumuve.com/sales-playbook).

Happy hunting! 🎯

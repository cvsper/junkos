#!/usr/bin/env python3
"""
Umuve Cold Email Outreach Automation Script
Supports Mailgun and SendGrid with personalization, scheduling, and tracking
"""

import csv
import time
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

# Uncomment your preferred email service
# from mailgun import MailgunClient  # pip install mailgun
# from sendgrid import SendGridAPIClient  # pip install sendgrid
# from sendgrid.helpers.mail import Mail

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # Email Service (choose one: 'mailgun' or 'sendgrid')
    'service': 'mailgun',
    
    # API Keys (set as environment variables for security)
    'mailgun_api_key': os.getenv('MAILGUN_API_KEY', 'your-mailgun-api-key'),
    'mailgun_domain': os.getenv('MAILGUN_DOMAIN', 'mg.yourdomain.com'),
    'sendgrid_api_key': os.getenv('SENDGRID_API_KEY', 'your-sendgrid-api-key'),
    
    # Sender Info
    'from_email': 'sales@goumuve.com',
    'from_name': 'Alex from Umuve',
    'reply_to': 'alex@goumuve.com',
    
    # Timing (days between emails)
    'email_delays': [0, 2, 5],  # Email 1: immediate, Email 2: +2 days, Email 3: +5 days after #2
    
    # Tracking
    'track_opens': True,
    'track_clicks': True,
    
    # Safety
    'dry_run': True,  # Set to False to actually send emails
}

# ============================================================================
# EMAIL TEMPLATES
# ============================================================================

SEQUENCES = {
    'A': [
        {
            'subject': 'Losing jobs because of slow quotes?',
            'body': '''Hi {{name}},

Quick question for {{company}} — how often do you lose jobs because someone else got their quote in faster?

Most haulers in {{city}} tell us they're typing the same info into spreadsheets 10+ times per day. The winner isn't always the best operator — just the fastest quote.

Umuve generates quotes in 30 seconds. Live pricing, instant PDF, done.

Worth a 10-minute look?

Best,
{{sender_name}}'''
        },
        {
            'subject': 'How {{city}} Haulers cut no-shows by 40%',
            'body': '''{{name}},

Saw you didn't get a chance to respond — no worries.

I wanted to share something relevant: A hauler in {{city}} was losing $3K/month to no-shows and last-minute cancellations.

They started using Umuve's automated reminders (SMS + email). No-shows dropped 40% in the first 60 days. Now their {{truck_count}}-truck operation runs tighter than ever.

Figured {{company}} might face similar challenges.

Want to see how they did it?

{{sender_name}}'''
        },
        {
            'subject': 'Quick question',
            'body': '''Hi {{name}},

Last one from me — promise.

Just curious: what's your current dispatch process look like? Are you using software, or still juggling spreadsheets and group texts?

No pitch here. If you're happy with your setup, that's genuinely great. But if dispatch chaos is eating your day, I can show you a 5-minute fix.

Reply with "show me" and I'll send a quick demo.

Cheers,
{{sender_name}}'''
        }
    ],
    'B': [
        {
            'subject': '3 trucks → 10 trucks in 18 months',
            'body': '''{{name}},

Mike at DFW Hauling started with 3 trucks in {{city}}, same as {{company}}.

18 months later? 10 trucks and booked solid 6 days a week.

His secret wasn't marketing — it was operations. Umuve automated his quotes, dispatch, and invoicing. He went from firefighting admin work to actually growing his business.

Think {{company}} could use that extra time?

Happy to show you his playbook.

Best,
{{sender_name}}'''
        },
        {
            'subject': '2-minute Umuve demo',
            'body': '''Hi {{name}},

Following up on my last email about scaling operations.

Instead of a long pitch, I recorded a 2-minute screen share showing exactly how Umuve handles:
• 30-second quotes
• GPS dispatch for {{truck_count}} trucks
• Auto-invoicing after job completion

Watch it here: https://goumuve.com/demo

If it clicks, we can chat. If not, no hard feelings.

{{sender_name}}'''
        },
        {
            'subject': 'Free trial?',
            'body': '''{{name}},

Last ping — want to offer {{company}} something concrete:

**Free 14-day trial + 30-minute setup call**

No credit card. No commitment. I'll personally get you configured for {{city}} pricing, import your customer list, and walk your team through day 1.

If it doesn't save you 5+ hours in the first week, just delete it.

Sound fair?

Reply "let's try it" and I'll get you started Monday.

{{sender_name}}'''
        }
    ],
    'C': [
        {
            'subject': 'Why 500+ haulers switched',
            'body': '''Hi {{name}},

Over 500 junk removal and hauling companies have switched to Umuve in the past year. Most from {{city}} and similar markets.

The #1 reason? They were tired of losing jobs to competitors with faster quotes and tighter operations.

Umuve isn't fancy — it just handles quotes, dispatch, and invoicing so you can focus on the actual work.

Want to see why companies like {{company}} are making the switch?

Best,
{{sender_name}}'''
        },
        {
            'subject': '{{city}} success story',
            'body': '''{{name}},

Wanted to share a local example:

A {{city}}-based hauler (similar size to {{company}} — {{truck_count}} trucks) implemented Umuve last fall. In Q4 alone:
• Revenue up 23%
• Quote-to-booking rate improved from 34% → 51%
• Admin time cut in half

They're not special. They just automated the boring stuff so they could take more jobs.

Worth 15 minutes to see if {{company}} could do the same?

{{sender_name}}'''
        },
        {
            'subject': 'Can I show you?',
            'body': '''Hi {{name}},

This is my last follow-up.

You're probably busy (running {{truck_count}} trucks isn't easy), so I'll make this simple:

**5-minute screen share. Your schedule. Zero pressure.**

I'll show you exactly how companies in {{city}} are using Umuve to close more jobs and cut admin chaos. If it's not a fit, we'll part as friends.

Reply with a day/time and I'll send a Zoom link.

Cheers,
{{sender_name}}

PS — If you're not interested, totally cool. Just reply "not now" and I'll stop reaching out.'''
        }
    ]
}

# ============================================================================
# PROSPECT MANAGEMENT
# ============================================================================

def load_prospects(csv_path: str) -> List[Dict]:
    """Load prospects from CSV file"""
    prospects = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prospects.append(row)
    print(f"✓ Loaded {len(prospects)} prospects from {csv_path}")
    return prospects

def personalize_email(template: Dict, prospect: Dict) -> Dict:
    """Replace template variables with prospect data"""
    subject = template['subject']
    body = template['body']
    
    # Merge prospect data with sender info
    variables = {
        **prospect,
        'sender_name': CONFIG['from_name']
    }
    
    # Replace all {{variable}} patterns
    for key, value in variables.items():
        subject = subject.replace(f'{{{{{key}}}}}', str(value))
        body = body.replace(f'{{{{{key}}}}}', str(value))
    
    return {
        'subject': subject,
        'body': body,
        'to_email': prospect['email'],
        'to_name': prospect['name']
    }

# ============================================================================
# EMAIL SENDING
# ============================================================================

def send_via_mailgun(email: Dict) -> bool:
    """Send email via Mailgun API"""
    import requests
    
    url = f"https://api.mailgun.net/v3/{CONFIG['mailgun_domain']}/messages"
    
    data = {
        'from': f"{CONFIG['from_name']} <{CONFIG['from_email']}>",
        'to': f"{email['to_name']} <{email['to_email']}>",
        'subject': email['subject'],
        'text': email['body'],
        'h:Reply-To': CONFIG['reply_to'],
    }
    
    # Add tracking
    if CONFIG['track_opens']:
        data['o:tracking-opens'] = 'yes'
    if CONFIG['track_clicks']:
        data['o:tracking-clicks'] = 'yes'
    
    try:
        response = requests.post(
            url,
            auth=('api', CONFIG['mailgun_api_key']),
            data=data
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"✗ Mailgun error: {e}")
        return False

def send_via_sendgrid(email: Dict) -> bool:
    """Send email via SendGrid API"""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, TrackingSettings, ClickTracking, OpenTracking
        
        message = Mail(
            from_email=(CONFIG['from_email'], CONFIG['from_name']),
            to_emails=(email['to_email'], email['to_name']),
            subject=email['subject'],
            plain_text_content=email['body']
        )
        
        message.reply_to = CONFIG['reply_to']
        
        # Add tracking
        message.tracking_settings = TrackingSettings()
        if CONFIG['track_opens']:
            message.tracking_settings.open_tracking = OpenTracking(enable=True)
        if CONFIG['track_clicks']:
            message.tracking_settings.click_tracking = ClickTracking(enable=True)
        
        sg = SendGridAPIClient(CONFIG['sendgrid_api_key'])
        response = sg.send(message)
        return response.status_code == 202
    except Exception as e:
        print(f"✗ SendGrid error: {e}")
        return False

def send_email(email: Dict) -> bool:
    """Route to appropriate email service"""
    if CONFIG['dry_run']:
        print(f"\n[DRY RUN] Would send to {email['to_email']}:")
        print(f"Subject: {email['subject']}")
        print(f"Body preview: {email['body'][:100]}...")
        return True
    
    if CONFIG['service'] == 'mailgun':
        return send_via_mailgun(email)
    elif CONFIG['service'] == 'sendgrid':
        return send_via_sendgrid(email)
    else:
        print(f"✗ Unknown email service: {CONFIG['service']}")
        return False

# ============================================================================
# CAMPAIGN EXECUTION
# ============================================================================

def run_campaign(csv_path: str, sequence_name: str = 'A'):
    """Execute email campaign for all prospects"""
    
    print(f"\n{'='*60}")
    print(f"Umuve Cold Email Campaign - Sequence {sequence_name}")
    print(f"{'='*60}\n")
    
    if CONFIG['dry_run']:
        print("⚠️  DRY RUN MODE - No emails will be sent\n")
    
    # Load prospects
    prospects = load_prospects(csv_path)
    sequence = SEQUENCES[sequence_name]
    
    # Track campaign status
    campaign_log = {
        'started': datetime.now().isoformat(),
        'sequence': sequence_name,
        'prospects': []
    }
    
    # Process each prospect
    for i, prospect in enumerate(prospects, 1):
        print(f"\n[{i}/{len(prospects)}] Processing: {prospect['name']} ({prospect['company']})")
        
        prospect_log = {
            'prospect': prospect,
            'emails': []
        }
        
        # Send each email in sequence
        for email_num, template in enumerate(sequence, 1):
            # Calculate send delay
            if email_num == 1:
                delay_days = 0
            else:
                delay_days = sum(CONFIG['email_delays'][:email_num])
            
            send_date = datetime.now() + timedelta(days=delay_days)
            
            # Personalize email
            personalized = personalize_email(template, prospect)
            
            print(f"  Email {email_num}: Scheduled for {send_date.strftime('%Y-%m-%d')}")
            
            # Send immediately or schedule
            if delay_days == 0:
                success = send_email(personalized)
                status = 'sent' if success else 'failed'
            else:
                # In production, integrate with scheduler (Celery, cron, etc.)
                status = 'scheduled'
                print(f"    → Would schedule for {send_date}")
            
            prospect_log['emails'].append({
                'email_num': email_num,
                'subject': personalized['subject'],
                'send_date': send_date.isoformat(),
                'status': status
            })
            
            # Rate limiting (be respectful)
            time.sleep(1)
        
        campaign_log['prospects'].append(prospect_log)
    
    # Save campaign log
    log_path = f"campaign-log-{sequence_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    with open(log_path, 'w') as f:
        json.dump(campaign_log, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✓ Campaign complete! Log saved to: {log_path}")
    print(f"{'='*60}\n")

# ============================================================================
# TRACKING & ANALYTICS
# ============================================================================

def track_responses():
    """Check for opens, clicks, and replies (implement with your email service)"""
    # Mailgun: GET https://api.mailgun.net/v3/{domain}/events
    # SendGrid: Use Event Webhook or Activity Feed API
    print("📊 Tracking implementation depends on your email service webhooks")
    print("   Mailgun: https://documentation.mailgun.com/en/latest/api-events.html")
    print("   SendGrid: https://docs.sendgrid.com/for-developers/tracking-events/event")

# ============================================================================
# CLI INTERFACE
# ============================================================================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Umuve Cold Email Outreach')
    parser.add_argument('--csv', default='prospect-list-template.csv', help='Path to prospect CSV')
    parser.add_argument('--sequence', choices=['A', 'B', 'C'], default='A', help='Email sequence to use')
    parser.add_argument('--live', action='store_true', help='Send real emails (disable dry-run)')
    parser.add_argument('--track', action='store_true', help='Show tracking analytics')
    
    args = parser.parse_args()
    
    if args.live:
        CONFIG['dry_run'] = False
        confirm = input("⚠️  This will send REAL emails. Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            exit(0)
    
    if args.track:
        track_responses()
    else:
        run_campaign(args.csv, args.sequence)

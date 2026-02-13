# Umuve Operator Guide

**Complete Manual for Junk Removal Operators**

Welcome to the comprehensive Umuve Operator Guide. This manual covers everything you need to know to run your junk removal business efficiently using Umuve.

---

## Table of Contents

1. [Dashboard Overview](#dashboard-overview)
2. [Managing Jobs](#managing-jobs)
3. [Driver Management](#driver-management)
4. [Customer Management](#customer-management)
5. [Invoicing & Payments](#invoicing--payments)
6. [Analytics & Reports](#analytics--reports)
7. [Settings & Configuration](#settings--configuration)
8. [Troubleshooting](#troubleshooting)

---

## Dashboard Overview

The Umuve dashboard is your command center for managing all aspects of your junk removal operation.

**[SCREENSHOT: Full dashboard overview]**

### Key Sections

#### 1. Top Navigation Bar

- **Company Logo/Name**: Click to return to dashboard
- **Search**: Quick search for jobs, customers, or drivers
- **Notifications**: Bell icon shows unread notifications
- **Profile Menu**: Account settings, help, logout

**[SCREENSHOT: Top navigation bar]**

#### 2. Left Sidebar Navigation

- **Dashboard**: Overview and quick stats
- **Jobs**: All job management
- **Calendar**: Schedule view
- **Drivers**: Driver management
- **Customers**: Customer database
- **Invoices**: Billing and payments
- **Analytics**: Reports and insights
- **Settings**: Configuration and preferences

**[SCREENSHOT: Sidebar navigation]**

#### 3. Dashboard Widgets

##### Today's Overview
- **Active Jobs**: Jobs scheduled for today
- **Completed Jobs**: Finished today
- **Revenue Today**: Total earnings
- **Pending Invoices**: Outstanding payments

**[SCREENSHOT: Today's overview widget]**

##### Upcoming Jobs
Shows next 5 scheduled jobs with:
- Time and date
- Customer name
- Service type
- Assigned driver
- Status

**[SCREENSHOT: Upcoming jobs widget]**

##### Driver Status
Real-time view of driver availability:
- **Available**: Ready for assignments
- **On Job**: Currently working
- **En Route**: Traveling to job
- **Off Duty**: Not working today

**[SCREENSHOT: Driver status widget]**

##### Recent Activity Feed
Chronological log of recent events:
- New bookings
- Job completions
- Invoice payments
- Customer messages

**[SCREENSHOT: Activity feed]**

#### 4. Quick Actions

Prominent buttons for common tasks:
- **+ New Job**: Create manual booking
- **+ Add Driver**: Onboard new driver
- **View Calendar**: Switch to calendar view
- **Send Invoice**: Generate invoice manually

---

## Managing Jobs

Jobs are the core of your operation. This section covers the complete job lifecycle.

### Job Lifecycle Stages

1. **Pending** → New booking awaiting confirmation
2. **Confirmed** → Accepted and scheduled
3. **Assigned** → Driver assigned
4. **En Route** → Driver traveling to site
5. **On Site** → Driver arrived
6. **In Progress** → Work underway
7. **Completed** → Job finished
8. **Invoiced** → Bill sent to customer
9. **Paid** → Payment received

**[SCREENSHOT: Job lifecycle diagram]**

### Creating a New Job

#### From Dashboard

1. Click **"+ New Job"** button
2. **Customer Information**:
   - Search existing customer or create new
   - Name, phone, email
   - Service address (may differ from billing address)
   - Access notes (gate codes, parking instructions)

**[SCREENSHOT: New job form - customer section]**

3. **Service Details**:
   - Select service type from dropdown
   - Estimated volume/quantity
   - Add specific items (couch, refrigerator, etc.)
   - Special handling requirements
   - Add photos (if customer provided them)

**[SCREENSHOT: New job form - service section]**

4. **Scheduling**:
   - Preferred date
   - Time window (2-hour slots recommended)
   - Set buffer time between jobs
   - Enable "Flexible" if customer has date flexibility

**[SCREENSHOT: New job form - scheduling section]**

5. **Pricing**:
   - Auto-calculated based on service and volume
   - Adjust pricing if needed
   - Add line items for extras
   - Add discount code if applicable
   - View total with tax

**[SCREENSHOT: New job form - pricing section]**

6. **Assign Driver** (optional):
   - Select driver immediately or assign later
   - View driver availability
   - Umuve suggests best match based on location and schedule

**[SCREENSHOT: Driver assignment dropdown]**

7. Click **"Create Job"**

### Managing Incoming Bookings

When customers book online, they appear in **"Pending"** status.

#### Review Pending Booking

1. Navigate to **"Jobs"** → **"Pending"** tab
2. Click on the booking to review details
3. Check:
   - Service area coverage
   - Driver availability
   - Pricing accuracy
   - Any special requirements

**[SCREENSHOT: Pending bookings list]**

#### Accept Booking

1. Click **"Accept Booking"**
2. Assign a driver (or leave for later)
3. Confirm date/time or propose alternative
4. Add internal notes if needed
5. Click **"Confirm"**

Customer receives automatic confirmation email.

**[SCREENSHOT: Accept booking dialog]**

#### Decline or Reschedule

If you can't fulfill the booking:
1. Click **"Decline"** or **"Request Reschedule"**
2. Select reason:
   - Outside service area
   - No driver availability
   - Service not offered
   - Other (explain)
3. For reschedule: Propose 3 alternative time slots
4. Click **"Send"**

Customer receives notification with options.

**[SCREENSHOT: Decline/reschedule dialog]**

### Dispatching Jobs

#### Manual Assignment

1. Open job details
2. Click **"Assign Driver"**
3. View available drivers with:
   - Current location
   - Schedule conflicts
   - Skills/certifications
   - Truck capacity
4. Select driver
5. Add dispatch notes
6. Click **"Assign"**

Driver receives push notification and/or SMS.

**[SCREENSHOT: Driver assignment with availability]**

#### Auto-Dispatch (Recommended)

Enable intelligent auto-dispatch:
1. Go to **Settings** → **"Dispatch"**
2. Toggle **"Auto-Dispatch"** ON
3. Set rules:
   - Assign to closest available driver
   - Balance workload evenly
   - Prioritize senior drivers
   - Consider driver preferences
4. Set time threshold (e.g., assign 24 hours before job)

**[SCREENSHOT: Auto-dispatch settings]**

### Tracking Job Progress

#### Real-Time Status Updates

Drivers update status via mobile app:
- **En Route**: Click for ETA and GPS tracking
- **On Site**: Timestamp of arrival
- **In Progress**: View elapsed time
- **Completed**: See completion photos and notes

**[SCREENSHOT: Job tracking map view]**

#### Communication During Jobs

##### Send Message to Driver
1. Open job details
2. Click **"Message Driver"**
3. Type message
4. Optional: Request photo or status update
5. Click **"Send"**

Driver sees message in app and can reply.

**[SCREENSHOT: Message driver interface]**

##### Customer Updates
Keep customers informed:
- **Auto-notifications** (can be customized):
  - Day-before reminder
  - "Driver en route" with ETA
  - "Arriving in 15 minutes"
  - Job completion summary

- **Manual updates**:
  1. Click **"Notify Customer"**
  2. Select template or write custom message
  3. Send via SMS or email

**[SCREENSHOT: Customer notification templates]**

### Handling Job Changes

#### Price Adjustments

If on-site volume differs from estimate:
1. Driver reports actual volume via app
2. You receive notification of price difference
3. Review adjustment:
   - View before/after photos
   - Check driver notes
4. **Approve** or **Modify** adjustment
5. Customer sees updated invoice

**[SCREENSHOT: Price adjustment approval]**

#### Rescheduling

1. Open job details
2. Click **"Reschedule"**
3. Select new date/time
4. Add reason for reschedule
5. Click **"Reschedule & Notify Customer"**

Customer receives notification with new appointment details.

**[SCREENSHOT: Reschedule job dialog]**

#### Cancellations

1. Click **"Cancel Job"**
2. Select reason:
   - Customer requested
   - Weather/emergency
   - Unable to fulfill
   - Other
3. Set cancellation fee (if applicable per your policy)
4. Add notes
5. Click **"Confirm Cancellation"**

**[SCREENSHOT: Cancel job dialog]**

### Job Notes and Documentation

#### Internal Notes
Add notes visible only to your team:
- Special instructions
- Customer history
- Lessons learned
- Follow-up needed

**[SCREENSHOT: Internal notes section]**

#### Photos
Review photos uploaded by drivers:
- Before photos (required)
- After photos (required)
- Additional documentation
- Download or attach to invoice

**[SCREENSHOT: Job photo gallery]**

#### Disposal Receipts
Track disposal costs for accurate profit calculation:
- Upload dump receipts
- Enter tonnage and fees
- Attach to job record

**[SCREENSHOT: Disposal receipt upload]**

---

## Driver Management

Effective driver management is crucial for smooth operations.

### Driver Dashboard

View all drivers at a glance:
- **Active**: Currently employed drivers
- **Inactive**: Former drivers (archived)
- **Pending**: Invitations not yet accepted

**[SCREENSHOT: Driver list view]**

### Adding Drivers

See [Quick Start Guide - Step 3](#step-3-add-your-first-driver-2-minutes) for basic driver setup.

#### Advanced Driver Setup

##### Skills & Certifications
Track driver qualifications:
1. Open driver profile
2. Click **"Skills & Certifications"**
3. Add:
   - Heavy lifting certification
   - Hazmat training
   - Forklift license
   - CDL class
   - First aid/CPR
4. Set expiration dates for renewal tracking

**[SCREENSHOT: Driver skills management]**

##### Equipment Assignment
Assign vehicles and equipment:
1. Go to **"Drivers"** → **"Equipment"**
2. Click **"+ Add Vehicle"**
3. Enter vehicle details:
   - Make, model, year
   - Capacity (cubic yards)
   - License plate
   - VIN
   - Insurance info
4. Assign to driver
5. Set maintenance schedule

**[SCREENSHOT: Vehicle assignment]**

##### Pay Settings
Configure driver compensation:
1. Open driver profile → **"Compensation"**
2. Select pay structure:
   - **Hourly rate**: Set $/hour
   - **Per job**: Flat rate per completion
   - **Commission**: Percentage of job revenue
   - **Hybrid**: Combination of above
3. Set overtime rules
4. Enable mileage reimbursement
5. Save settings

**[SCREENSHOT: Driver compensation settings]**

### Driver Availability

#### Schedules
Set recurring driver schedules:
1. Go to **"Drivers"** → Select driver → **"Schedule"**
2. Set weekly availability:
   - Days of week
   - Start and end times
   - Break times
3. Add time-off requests:
   - Vacation
   - Sick leave
   - Personal days

**[SCREENSHOT: Driver schedule calendar]**

#### Real-Time Status
Monitor driver availability in real-time:
- **Available** (green): Ready for assignments
- **Busy** (orange): On active job
- **Offline** (gray): Not logged into app
- **Break** (blue): On scheduled break

**[SCREENSHOT: Real-time driver status]**

### Performance Tracking

#### Driver Metrics
View individual driver performance:
- **Jobs Completed**: Total and monthly
- **Average Rating**: Customer reviews
- **On-Time Rate**: Percentage arriving within time window
- **Revenue Generated**: Total earnings from assigned jobs
- **Efficiency**: Jobs per hour/day

**[SCREENSHOT: Driver performance dashboard]**

#### Customer Ratings
Review driver feedback:
1. Go to driver profile → **"Reviews"**
2. See all customer ratings and comments
3. Filter by date range
4. Respond to concerns
5. Recognize excellent performance

**[SCREENSHOT: Driver reviews]**

### Driver Communication

#### Broadcast Messages
Send messages to all drivers:
1. Go to **"Drivers"** → **"Broadcast"**
2. Compose message
3. Select recipients:
   - All drivers
   - Active only
   - Specific drivers
4. Choose delivery: Push notification, SMS, or email
5. Click **"Send"**

**[SCREENSHOT: Broadcast message interface]**

#### Individual Messages
Direct communication with a driver:
1. Open driver profile
2. Click **"Send Message"**
3. Type message
4. Attach files if needed
5. Click **"Send"**

**[SCREENSHOT: Individual driver message]**

---

## Customer Management

Build and maintain strong customer relationships.

### Customer Database

#### Customer List
View all customers:
- Sort by: Name, last job date, total spent
- Filter by: Active, inactive, VIP
- Search by name, phone, or email

**[SCREENSHOT: Customer list]**

### Customer Profiles

Each customer profile includes:

#### Contact Information
- Name and company (if commercial)
- Phone number(s)
- Email address(es)
- Service address(es)
- Billing address

**[SCREENSHOT: Customer contact info]**

#### Job History
- All past jobs with dates
- Services provided
- Total spent
- Average job value

**[SCREENSHOT: Customer job history]**

#### Payment History
- All invoices
- Payment methods used
- Outstanding balance
- Payment reliability score

**[SCREENSHOT: Customer payment history]**

#### Notes & Tags
- Internal notes about customer
- Preferences (e.g., "prefers morning appointments")
- Special instructions
- Tags for segmentation (VIP, commercial, seasonal, etc.)

**[SCREENSHOT: Customer notes and tags]**

### Adding Customers

#### Manual Entry
1. Click **"Customers"** → **"+ Add Customer"**
2. Enter contact details
3. Add service address
4. Add notes or tags
5. Click **"Save"**

**[SCREENSHOT: Add customer form]**

#### Automatic Creation
Customers are automatically created when:
- They book online
- You create a job for a new customer
- They appear on an imported invoice

### Customer Communication

#### Send Message
1. Open customer profile
2. Click **"Send Message"**
3. Choose delivery method:
   - Email
   - SMS
   - Both
4. Select template or compose custom message
5. Click **"Send"**

**[SCREENSHOT: Customer message interface]**

#### Email Templates
Create reusable templates for:
- Appointment reminders
- Thank you messages
- Review requests
- Special offers
- Seasonal promotions

**[SCREENSHOT: Email template editor]**

### Customer Loyalty

#### Loyalty Programs
Set up repeat customer rewards:
1. Go to **Settings** → **"Loyalty"**
2. Enable **"Loyalty Program"**
3. Configure rewards:
   - Points per dollar spent
   - Redemption value
   - Bonus milestones
4. Set auto-apply discounts

**[SCREENSHOT: Loyalty program settings]**

#### Referral Tracking
Track customer referrals:
- Each customer gets unique referral code
- Offer rewards for successful referrals
- View referral sources in analytics

**[SCREENSHOT: Referral dashboard]**

---

## Invoicing & Payments

Streamline your billing and payment collection.

### Creating Invoices

#### Automatic Invoicing
Invoices are auto-generated when job status changes to **"Completed"**:
- Pull data from job record
- Calculate total with tax
- Apply discounts if set
- Send to customer automatically (if enabled)

**[SCREENSHOT: Auto-generated invoice]**

#### Manual Invoicing
Create invoice without a job:
1. Click **"Invoices"** → **"+ New Invoice"**
2. Select customer
3. Add line items:
   - Description
   - Quantity
   - Rate
   - Tax
4. Set payment terms
5. Click **"Create & Send"**

**[SCREENSHOT: Manual invoice creation]**

### Invoice Management

#### Invoice List
View all invoices with filters:
- **Paid**: Completed payments
- **Unpaid**: Outstanding invoices
- **Overdue**: Past due date
- **Draft**: Not yet sent

**[SCREENSHOT: Invoice list view]**

#### Invoice Details
Each invoice shows:
- Invoice number and date
- Customer information
- Itemized charges
- Subtotal, tax, and total
- Payment status
- Payment history
- Download PDF button

**[SCREENSHOT: Invoice detail view]**

### Payment Collection

#### Payment Methods

Umuve supports multiple payment methods through Stripe:

##### Online Payments
Customers can pay via invoice link:
- Credit/debit cards
- ACH bank transfer
- Apple Pay / Google Pay

**[SCREENSHOT: Customer payment page]**

##### In-Person Payments
Drivers can collect payment on-site using mobile app:
1. Driver completes job
2. App generates invoice
3. Customer pays via:
   - Card reader (if equipped)
   - Cash (driver marks as cash payment)
   - Check (driver photographs check)

**[SCREENSHOT: Mobile payment in driver app]**

##### Offline Payment Recording
Record payments made outside Umuve:
1. Open invoice
2. Click **"Record Payment"**
3. Select method: Cash, check, wire transfer, other
4. Enter amount and date
5. Add reference number
6. Click **"Record"**

**[SCREENSHOT: Record offline payment]**

### Payment Tracking

#### Payment Dashboard
Overview of financial health:
- **Total Outstanding**: Unpaid invoices
- **Collected This Month**: Revenue received
- **Average Payment Time**: Days from invoice to payment
- **Payment Method Breakdown**: Pie chart

**[SCREENSHOT: Payment dashboard]**

#### Overdue Management
Handle late payments:
1. Go to **"Invoices"** → **"Overdue"**
2. Select invoice
3. Options:
   - **Send Reminder**: Auto-generated reminder email
   - **Apply Late Fee**: Add percentage or flat fee
   - **Payment Plan**: Set up installment schedule
   - **Write Off**: Mark as uncollectible

**[SCREENSHOT: Overdue invoice actions]**

### Refunds & Credits

#### Issue Refund
1. Open paid invoice
2. Click **"Issue Refund"**
3. Select refund amount:
   - Full refund
   - Partial refund (enter amount)
4. Choose method:
   - Original payment method
   - Store credit
5. Add reason for records
6. Click **"Process Refund"**

Refunds typically process in 5-10 business days.

**[SCREENSHOT: Refund processing]**

#### Store Credits
Give customers credit for future services:
1. Open customer profile
2. Click **"Add Credit"**
3. Enter amount and reason
4. Credit appears on customer account
5. Auto-applied to next invoice

**[SCREENSHOT: Store credit management]**

---

## Analytics & Reports

Make data-driven decisions with comprehensive reporting.

### Dashboard Analytics

#### Key Performance Indicators (KPIs)

**[SCREENSHOT: Analytics dashboard overview]**

##### Revenue Metrics
- **Total Revenue**: By day, week, month, year
- **Average Job Value**: Mean revenue per job
- **Revenue by Service**: Breakdown by service type
- **Revenue by Driver**: Top performers

##### Operational Metrics
- **Jobs Completed**: Total and by time period
- **Completion Rate**: Percentage of scheduled jobs completed
- **On-Time Performance**: Jobs starting within time window
- **Average Job Duration**: Mean time from start to completion

##### Customer Metrics
- **New Customers**: First-time bookings
- **Repeat Customers**: Return rate
- **Customer Lifetime Value**: Average total spent per customer
- **Customer Acquisition Cost**: Marketing spend / new customers

### Standard Reports

#### Revenue Reports

##### Daily Revenue
Shows each day's earnings with:
- Number of jobs
- Total revenue
- Average job value
- Payment methods used

**[SCREENSHOT: Daily revenue report]**

##### Revenue by Service Type
Compare profitability across services:
- Service name
- Number of jobs
- Total revenue
- Average price
- Profit margin

**[SCREENSHOT: Revenue by service report]**

##### Revenue by Driver
Track driver earnings contribution:
- Driver name
- Jobs completed
- Revenue generated
- Average job value

**[SCREENSHOT: Revenue by driver report]**

#### Job Reports

##### Job Summary
Overview of all jobs in date range:
- Total jobs
- By status (completed, canceled, pending)
- By service type
- By customer type (new vs. repeat)

**[SCREENSHOT: Job summary report]**

##### Completion Rate
Analyze job fulfillment:
- Jobs scheduled vs completed
- Cancellation reasons
- Rescheduling frequency

**[SCREENSHOT: Completion rate report]**

#### Customer Reports

##### Customer Acquisition
Track new customer growth:
- New customers by month
- Acquisition sources (online, referral, repeat)
- First job value

**[SCREENSHOT: Customer acquisition report]**

##### Customer Retention
Measure repeat business:
- Repeat customer rate
- Average time between jobs
- Customer churn rate

**[SCREENSHOT: Customer retention report]**

#### Driver Reports

##### Driver Performance
Compare driver metrics:
- Jobs completed
- Customer ratings
- On-time percentage
- Revenue generated

**[SCREENSHOT: Driver performance report]**

##### Driver Utilization
Track driver workload:
- Hours worked
- Jobs per hour
- Idle time
- Utilization rate

**[SCREENSHOT: Driver utilization report]**

### Custom Reports

#### Report Builder
Create custom reports:
1. Go to **"Analytics"** → **"Custom Reports"**
2. Click **"+ New Report"**
3. Select data source:
   - Jobs
   - Invoices
   - Customers
   - Drivers
4. Choose fields to include
5. Add filters (date range, status, etc.)
6. Set grouping and sorting
7. Click **"Generate Report"**

**[SCREENSHOT: Custom report builder]**

#### Scheduled Reports
Auto-generate and email reports:
1. Create or open report
2. Click **"Schedule"**
3. Set frequency:
   - Daily
   - Weekly (choose day)
   - Monthly (choose date)
4. Add email recipients
5. Select format: PDF or CSV
6. Click **"Schedule Report"**

**[SCREENSHOT: Schedule report interface]**

### Exporting Data

#### Export Options
Export any report or data view:
1. Generate report or list
2. Click **"Export"** button
3. Choose format:
   - **CSV**: For Excel/Google Sheets
   - **PDF**: For printing or sharing
   - **JSON**: For developers/integrations
4. Click **"Download"**

**[SCREENSHOT: Export options]**

#### Bulk Exports
Export all data for backup or migration:
1. Go to **Settings** → **"Data Export"**
2. Select data types:
   - Jobs
   - Customers
   - Invoices
   - Drivers
3. Click **"Request Export"**
4. Receive email when ready (usually within 1 hour)
5. Download zip file

**[SCREENSHOT: Bulk data export]**

---

## Settings & Configuration

Customize Umuve to fit your business.

### Company Settings

#### Business Profile
Update your company information:
- Company name and logo
- Contact information
- Business hours
- Service areas
- Tax ID / EIN

**[SCREENSHOT: Business profile settings]**

#### Branding
Customize customer-facing appearance:
- Upload logo (recommended: 500x500px PNG)
- Choose brand colors
- Set email header
- Customize booking page

**[SCREENSHOT: Branding settings]**

### Service Configuration

#### Service Types
Manage offered services:
- Enable/disable services
- Edit pricing
- Set minimum charges
- Configure add-ons

See [Step 4: Configure Services & Pricing](#step-4-configure-services--pricing-4-minutes) in Quick Start Guide.

#### Booking Settings

##### Availability
Configure when customers can book:
1. Go to **Settings** → **"Booking"**
2. Set **"Advance Booking"**: Minimum hours notice required
3. Set **"Booking Window"**: How far in advance (days/weeks)
4. Enable **"Same-Day Booking"** if offered
5. Set **"Time Slot Duration"** (recommended: 2 hours)

**[SCREENSHOT: Booking availability settings]**

##### Booking Requirements
Set what customers must provide:
- Photos (optional/required)
- Detailed item list (yes/no)
- Estimated volume (yes/no)
- Access instructions (optional/required)

**[SCREENSHOT: Booking requirements settings]**

##### Auto-Acceptance
Enable automatic booking confirmation:
1. Toggle **"Auto-Accept Bookings"** ON
2. Set conditions:
   - Only during business hours
   - Only if driver available
   - Only within X days
3. Set maximum auto-accept per day (to avoid overbooking)

**[SCREENSHOT: Auto-acceptance settings]**

### Payment Settings

#### Stripe Configuration
Manage payment processing:
- View connected account status
- Update bank details (via Stripe dashboard)
- Set payout schedule
- Enable/disable payment methods

**[SCREENSHOT: Stripe settings]**

#### Invoice Settings
Customize invoicing:
- Invoice prefix (e.g., "INV-2026-")
- Payment terms (Net 15, Net 30, Due on Receipt)
- Late fee policy (percentage or flat fee after X days)
- Auto-send invoices when job completes
- Include payment link in invoice emails

**[SCREENSHOT: Invoice settings]**

#### Tax Configuration
Set up sales tax:
1. Go to **Settings** → **"Payments"** → **"Tax"**
2. Enable **"Charge Sales Tax"**
3. Add tax rates by location:
   - State/Province
   - City (if applicable)
   - Tax rate percentage
4. Set tax exemption rules (if applicable)

**[SCREENSHOT: Tax configuration]**

### Notification Settings

#### Customer Notifications
Configure automated customer messages:
- **Booking Confirmation**: Immediate
- **Day-Before Reminder**: 24 hours before job
- **Driver En Route**: When driver starts navigation
- **Job Completed**: When marked complete
- **Invoice Sent**: When invoice generated
- **Payment Received**: When payment processes

Toggle each on/off and customize message templates.

**[SCREENSHOT: Customer notification settings]**

#### Driver Notifications
Configure driver alerts:
- **New Job Assignment**: Immediate
- **Job Reminder**: 1 hour before scheduled time
- **Schedule Changes**: When job rescheduled/canceled
- **Customer Messages**: When customer sends message

**[SCREENSHOT: Driver notification settings]**

#### Operator Notifications
Get alerted about important events:
- **New Booking**: Immediate email/SMS
- **Job Completion**: Email summary at end of day
- **Payment Received**: Immediate notification
- **Driver Check-In/Out**: Optional location updates
- **System Alerts**: Service issues or maintenance

**[SCREENSHOT: Operator notification settings]**

### Team Management

#### User Roles
Add team members with different permission levels:

##### Admin
Full access to everything:
- All settings
- Financial data
- Driver management
- Customer management

##### Dispatcher
Manage day-to-day operations:
- Create/edit jobs
- Assign drivers
- Customer communication
- **Cannot**: Access financial settings or reports

##### Accountant
Financial access only:
- View/create invoices
- Process payments
- View financial reports
- **Cannot**: Access operations or settings

**[SCREENSHOT: User roles and permissions]**

#### Adding Team Members
1. Go to **Settings** → **"Team"**
2. Click **"+ Invite Team Member"**
3. Enter email address
4. Select role
5. Click **"Send Invitation"**

Team member receives email with login instructions.

**[SCREENSHOT: Invite team member]**

### Integration Settings

#### Website Integration
Add booking widget to your website:
1. Go to **Settings** → **"Integrations"** → **"Website Widget"**
2. Customize appearance and fields
3. Copy embed code
4. Paste into your website HTML

**[SCREENSHOT: Website widget code]**

#### API Access
For custom integrations:
1. Go to **Settings** → **"Integrations"** → **"API"**
2. Click **"Generate API Key"**
3. View API documentation
4. Test endpoints in sandbox mode

**[SCREENSHOT: API key management]**

#### Third-Party Integrations
Connect to other tools:
- **QuickBooks**: Sync invoices and payments
- **Google Calendar**: Sync job schedule
- **Zapier**: Automate workflows
- **Mailchimp**: Email marketing

**[SCREENSHOT: Third-party integrations list]**

---

## Troubleshooting

Common issues and solutions.

### Login Issues

#### Can't Remember Password
1. Go to login page
2. Click **"Forgot Password?"**
3. Enter email address
4. Check inbox for reset link (check spam folder)
5. Click link and set new password

#### Account Locked
After 5 failed login attempts, account locks for 15 minutes.
- Wait 15 minutes and try again
- OR contact support to unlock immediately

#### Email Not Received
- Check spam/junk folder
- Verify email address is correct in account settings
- Add noreply@goumuve.com to contacts
- Try resending verification email

### Booking Issues

#### Customers Can't Book Online
**Check:**
1. **Service Area**: Ensure customer address is in your service area
2. **Availability**: Verify you have open time slots
3. **Booking Window**: Check your advance booking settings aren't too restrictive
4. **Browser Cache**: Have customer clear cache or try incognito mode

**[SCREENSHOT: Service area check]**

#### Bookings Not Appearing
1. Check **"Pending"** tab (may need approval)
2. Verify email notifications are enabled
3. Check spam folder for booking notifications
4. Refresh dashboard (F5 or Cmd+R)

### Driver Issues

#### Driver Can't Log Into Mobile App
1. Verify invitation email was accepted
2. Check driver status is **"Active"** not **"Inactive"**
3. Ensure driver is using correct email
4. Reset driver password:
   - Go to driver profile
   - Click **"Reset Password"**
   - Driver receives new temporary password

#### Driver Not Receiving Job Assignments
1. Check driver's notification settings in mobile app
2. Verify phone number is correct
3. Ensure phone has internet connection
4. Check driver's schedule shows as "Available"

#### GPS Tracking Not Working
1. Ensure driver has enabled location permissions in app settings
2. Check phone has GPS/location services enabled
3. Verify internet connection (need data or WiFi)
4. Try logging out and back into app

### Payment Issues

#### Stripe Not Connecting
1. Clear browser cache and cookies
2. Try different browser
3. Ensure pop-ups are not blocked
4. Check Stripe system status: status.stripe.com
5. Contact support with error message screenshot

#### Customer Payment Declined
Common reasons:
- **Insufficient funds**: Ask customer to use different card
- **Card expired**: Request updated payment method
- **Fraud prevention**: Customer should contact their bank
- **Incorrect details**: Verify card number and CVV

You'll receive email notification with decline reason.

#### Payout Not Received
1. Check payout schedule (daily/weekly/monthly)
2. Verify bank account details in Stripe dashboard
3. Check for holds due to disputes or verification
4. Payouts typically take 2-3 business days
5. Contact Stripe support for payout-specific issues

### Invoice Issues

#### Invoice Not Sent to Customer
1. Check customer email address is correct
2. Verify email notifications are enabled in Settings
3. Check sent email logs:
   - Go to invoice → **"Email History"**
4. Ask customer to check spam folder
5. Manually resend: Click **"Resend Invoice"**

#### Invoice Total Incorrect
1. Verify all line items are correct
2. Check tax rate is accurate for location
3. Ensure discounts applied correctly
4. Review any on-site price adjustments
5. Edit invoice and regenerate if needed

### Performance Issues

#### Dashboard Loading Slowly
1. Check internet connection speed
2. Clear browser cache:
   - Chrome: Cmd/Ctrl + Shift + Delete
3. Close unnecessary browser tabs
4. Try different browser
5. Check Umuve status page: status.goumuve.com

#### Mobile App Crashing
1. Ensure app is updated to latest version
2. Restart phone
3. Clear app cache (in phone settings)
4. Uninstall and reinstall app (won't lose data)
5. Report crash to support with:
   - Phone model and OS version
   - What you were doing when it crashed

### Getting Help

#### Support Resources

##### Help Center
Search articles and guides:
- Visit help.goumuve.com
- Search by keyword or browse categories

##### Video Tutorials
Watch how-to videos:
- YouTube: youtube.com/umuve
- In-app video library

##### Community Forum
Ask questions and share tips:
- community.goumuve.com
- Connect with other operators

##### Email Support
For specific issues:
- Email: support@goumuve.com
- Include:
  - Account email
  - Description of issue
  - Screenshots if applicable
  - Steps you've already tried
- Response time: Within 24 hours (usually faster)

##### Phone Support
For urgent issues:
- Call: 1-800-JUNK-OS (1-800-586-5667)
- Hours: Mon-Fri 8am-8pm EST, Sat 9am-5pm EST
- Have your account email ready

##### Live Chat
For quick questions:
- Click chat icon in bottom-right of dashboard
- Available during business hours
- Average response: Under 5 minutes

**[SCREENSHOT: Support contact options]**

---

## Appendix

### Keyboard Shortcuts

Speed up your workflow with shortcuts:

- **Cmd/Ctrl + K**: Quick search
- **Cmd/Ctrl + N**: New job
- **Cmd/Ctrl + D**: Go to dashboard
- **Cmd/Ctrl + J**: Go to jobs
- **Cmd/Ctrl + I**: Go to invoices
- **Cmd/Ctrl + ,**: Settings
- **Esc**: Close dialog/modal

### Glossary

- **Booking**: Customer request for service
- **Job**: Confirmed service appointment
- **Dispatch**: Assigning a driver to a job
- **On-site**: Driver has arrived at customer location
- **Completion**: Job is finished, ready for invoicing
- **Load**: Amount of junk (typically measured in truck fractions)
- **Cubic Yard**: Standard volume measurement (3ft x 3ft x 3ft)
- **Disposal Receipt**: Proof of proper disposal at dump/transfer station
- **ETA**: Estimated Time of Arrival
- **Time Window**: Range of time for appointment (e.g., 10am-12pm)

### Best Practices

#### Respond Quickly
- Accept/decline bookings within 2 hours
- Industry standard: 73% of customers book with first responder

#### Communicate Proactively
- Send driver ETA to customers
- Give updates if running late
- Thank customers after job completion

#### Document Everything
- Require before/after photos on every job
- Keep disposal receipts for 3 years
- Save customer communications

#### Price Accurately
- Get detailed item lists before quoting
- Build in 10-15% buffer for unknowns
- Update prices quarterly based on disposal costs

#### Take Care of Drivers
- Provide necessary equipment
- Recognize top performers
- Solicit feedback on processes

#### Monitor Analytics
- Review weekly revenue trends
- Track customer acquisition costs
- Identify most profitable services

---

**Questions?** Contact us at support@goumuve.com

*Last updated: February 2026*

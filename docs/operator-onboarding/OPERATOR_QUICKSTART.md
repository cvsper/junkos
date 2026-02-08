# JunkOS Operator Quick Start Guide

**Get up and running in 15 minutes** 🚀

This guide will walk you through the essential steps to set up your junk removal business on JunkOS and accept your first booking.

---

## Prerequisites

- A modern web browser (Chrome, Firefox, Safari, or Edge)
- Business information (company name, address, phone)
- Bank account details for payments (for Stripe Connect)
- At least one driver's contact information

---

## Step 1: Create Your Account (2 minutes)

### 1.1 Sign Up

1. Navigate to **https://junkos.app/signup**
2. Click **"Sign Up as Operator"**
3. Enter your details:
   - Email address
   - Password (minimum 8 characters)
   - First and last name
4. Click **"Create Account"**

**[SCREENSHOT: Sign up form]**

### 1.2 Verify Your Email

1. Check your inbox for a verification email from JunkOS
2. Click the **"Verify Email"** link
3. You'll be redirected to the login page

**[SCREENSHOT: Email verification success]**

---

## Step 2: Complete Company Profile (3 minutes)

After logging in for the first time, you'll be prompted to complete your company profile.

### 2.1 Basic Information

1. **Company Name**: Your business name as it appears to customers
2. **Business Phone**: Primary contact number
3. **Business Email**: Customer-facing email address
4. **Business Address**: Your main office or depot location

**[SCREENSHOT: Company profile form - basic info]**

### 2.2 Service Area

1. Click **"Add Service Area"**
2. Enter your zip codes or use the map to draw your service radius
3. Set a maximum travel distance (optional)
4. Click **"Save Service Area"**

**[SCREENSHOT: Service area configuration with map]**

### 2.3 Business Hours

1. Set your operating hours for each day of the week
2. Add special hours for holidays (optional)
3. Enable **"Accept After-Hours Bookings"** if applicable
4. Click **"Save Hours"**

**[SCREENSHOT: Business hours configuration]**

---

## Step 3: Add Your First Driver (2 minutes)

### 3.1 Navigate to Drivers

1. From the dashboard, click **"Drivers"** in the left sidebar
2. Click **"+ Add Driver"** button

**[SCREENSHOT: Drivers page]**

### 3.2 Enter Driver Information

1. **First Name** and **Last Name**
2. **Email**: Driver will receive login credentials here
3. **Phone Number**: For job notifications
4. **License Number** (optional but recommended)
5. **Vehicle Information**:
   - Truck size (e.g., "16ft box truck")
   - License plate
   - Vehicle capacity (cubic yards)

6. Click **"Send Invitation"**

**[SCREENSHOT: Add driver form]**

### 3.3 Driver Receives Invitation

Your driver will receive an email with:
- Login credentials
- Link to download the mobile app (when available)
- Instructions to complete their profile

---

## Step 4: Configure Services & Pricing (4 minutes)

### 4.1 Navigate to Services

1. Click **"Services"** in the left sidebar
2. You'll see default service templates

**[SCREENSHOT: Services overview page]**

### 4.2 Add or Edit Services

#### Option 1: Use Default Templates
JunkOS provides common service templates:
- **Full-Service Junk Removal** (labor + disposal)
- **Curbside Pickup** (disposal only)
- **Furniture Removal**
- **Appliance Removal**
- **Yard Waste Removal**

Simply click **"Enable"** on the services you offer.

#### Option 2: Create Custom Service

1. Click **"+ Add Custom Service"**
2. Enter:
   - **Service Name**: E.g., "Hot Tub Removal"
   - **Description**: Brief explanation for customers
   - **Base Price**: Starting rate
   - **Pricing Model**:
     - Fixed price
     - Per cubic yard
     - Per item
     - Hourly rate
3. Click **"Save Service"**

**[SCREENSHOT: Service pricing configuration]**

### 4.3 Set Volume-Based Pricing (Recommended)

For full-service junk removal:

1. Select **"Full-Service Junk Removal"**
2. Click **"Configure Pricing"**
3. Set rates by volume:
   - **1/8 truck load**: $99
   - **1/4 truck load**: $179
   - **1/2 truck load**: $299
   - **3/4 truck load**: $449
   - **Full truck load**: $599

4. Enable **"Allow Price Adjustments"** for on-site changes
5. Set **minimum charge** (e.g., $99)
6. Click **"Save Pricing"**

**[SCREENSHOT: Volume-based pricing table]**

### 4.4 Add-On Services (Optional)

Create add-on services for common extras:
- Heavy lifting surcharge
- Stairs/elevator fee
- Same-day service fee
- Hazardous material handling

---

## Step 5: Test First Booking (2 minutes)

Before going live, create a test booking to familiarize yourself with the workflow.

### 5.1 Create Test Booking

1. Click **"Jobs"** in the sidebar
2. Click **"+ New Job"**
3. Enter test customer information:
   - Name: "Test Customer"
   - Phone: Your personal phone
   - Address: Your business address

4. Select service: **"Full-Service Junk Removal"**
5. Choose date and time window
6. Add items: "Old couch, mattress"
7. Estimated volume: **1/4 truck load**
8. Click **"Create Job"**

**[SCREENSHOT: New job creation form]**

### 5.2 Assign Driver

1. From the job detail page, click **"Assign Driver"**
2. Select your driver from the dropdown
3. Click **"Assign"**

**[SCREENSHOT: Job assigned to driver]**

### 5.3 Walk Through Job Lifecycle

Practice changing job statuses:
1. **"En Route"** - Driver heading to customer
2. **"On Site"** - Driver arrived
3. **"In Progress"** - Work started
4. **"Completed"** - Job finished
5. **"Invoiced"** - Invoice sent to customer

**[SCREENSHOT: Job status progression]**

---

## Step 6: Payment Setup - Stripe Connect (2 minutes)

To receive payments from customers, you need to connect your bank account via Stripe.

### 6.1 Navigate to Payment Settings

1. Click your **profile icon** in the top-right
2. Select **"Settings"**
3. Click **"Payments"** tab

**[SCREENSHOT: Settings navigation]**

### 6.2 Connect Stripe Account

1. Click **"Connect with Stripe"**
2. You'll be redirected to Stripe's secure onboarding
3. Choose **"Create new account"** or **"Use existing account"**

**[SCREENSHOT: Stripe Connect button]**

### 6.3 Complete Stripe Onboarding

Stripe will ask for:
- **Business information**: Legal name, type (LLC, sole proprietor, etc.)
- **Personal information**: For identity verification
- **Bank account**: For receiving payouts
- **Tax information**: EIN or SSN

This typically takes 3-5 minutes.

**[SCREENSHOT: Stripe onboarding flow]**

### 6.4 Verify Connection

1. After completing Stripe setup, you'll be redirected back to JunkOS
2. You should see **"✓ Stripe Connected"** status
3. Set your **payout schedule**:
   - Daily (available next business day)
   - Weekly (every Friday)
   - Monthly (1st of each month)

**[SCREENSHOT: Stripe connected successfully]**

---

## 🎉 You're Ready to Go!

Congratulations! Your JunkOS account is now set up and ready to accept real bookings.

### Next Steps

1. **Go Live**: Enable your booking widget on your website
2. **Share Your Link**: Give customers your JunkOS booking URL
3. **Test Mobile App**: Have your driver log in and test the mobile experience
4. **Explore Features**: Check out the full Operator Guide for advanced features

### Quick Tips for Success

✅ **Respond quickly** - Accept or decline bookings within 2 hours  
✅ **Keep drivers updated** - Assign jobs as soon as possible  
✅ **Communicate with customers** - Use the built-in messaging for updates  
✅ **Take photos** - Document before/after for every job  
✅ **Invoice promptly** - Send invoices immediately after completion  

---

## Need Help?

- **📚 Full Guide**: Read the complete [Operator Guide](./OPERATOR_GUIDE.md)
- **💬 Support**: Email support@junkos.app
- **📞 Phone**: 1-800-JUNK-OS (1-800-586-5667)
- **💡 Community**: Join our [Operator Forum](https://community.junkos.app)

---

**Welcome to JunkOS!** 🚛

*Last updated: February 2026*

# JunkOS Legal Documents

This directory contains production-ready legal documents for the JunkOS mobile app.

## 📁 Files Included

### Privacy Policy
- **PRIVACY_POLICY.md** - Full privacy policy (Markdown format)
- **PRIVACY_POLICY_SHORT.md** - App Store summary version
- **privacy-policy.html** - HTML version for web hosting

### Terms of Service
- **TERMS_OF_SERVICE.md** - Full terms of service (Markdown format)
- **terms-of-service.html** - HTML version for web hosting

---

## ✅ Before Using These Documents

**You MUST customize the following placeholders:**

1. **Contact Information** (appears in all documents):
   - `[insert support email]` → Replace with actual support email (e.g., support@junkos.com)
   - `[privacy email]` → Replace with privacy contact (can be same as support)
   - `[Tampa, FL address if applicable]` → Add physical business address
   - `[support phone number]` → Add support phone number

2. **Privacy Policy Short Version**:
   - `[link to hosted privacy policy]` → Add URL where full policy is hosted

3. **Consider these optional additions**:
   - Add a data protection officer (DPO) contact if you expand internationally
   - Add California-specific contact for CCPA requests
   - Customize retention periods if your business requirements differ

---

## 🚀 How to Use

### For App Store Submission (iOS)

1. **In App Store Connect:**
   - Upload the **privacy-policy.html** file to your website
   - Add the URL in "Privacy Policy URL" field
   - Use **PRIVACY_POLICY_SHORT.md** content for any in-app privacy displays

2. **App Privacy Details:**
   - You'll need to fill out Apple's privacy questionnaire
   - Based on these documents, select:
     - ✅ Contact Info (name, email, phone)
     - ✅ Location (used during booking, not stored)
     - ✅ Photos (uploaded for quotes)
     - ✅ User Content (booking history)
     - ✅ Financial Info (when Stripe is added)

### For Google Play Store (Android)

1. **In Google Play Console:**
   - Upload **privacy-policy.html** to your website
   - Add the URL in "Store Presence" → "Privacy Policy"
   - Use **PRIVACY_POLICY_SHORT.md** for any in-app displays

2. **Data Safety Section:**
   - Select data types collected (location, photos, contact info, etc.)
   - Indicate they're used for "App functionality"
   - Mark that data can be deleted on request

### For Your Website

1. Host both HTML files on your website:
   - `https://yourdomain.com/privacy-policy.html`
   - `https://yourdomain.com/terms-of-service.html`

2. Link to them from your:
   - Homepage footer
   - App download pages
   - In-app settings menu

### In-App Integration

Add links in your app settings:
```
Settings
├── Privacy Policy (link to hosted privacy-policy.html)
├── Terms of Service (link to hosted terms-of-service.html)
└── Delete Account (trigger account deletion flow)
```

---

## 📝 Compliance Notes

### CCPA (California Consumer Privacy Act)
✅ **Compliant** - Users can access, delete, and opt-out of marketing
- Section 6.5 covers California-specific rights

### GDPR (General Data Protection Regulation)
✅ **Compliant** - Though you're Florida-based, these docs cover GDPR basics
- Section 6.6 covers EU/EEA resident rights
- If you expand internationally, consider adding a DPO

### Florida Privacy Laws
✅ **Compliant** - Florida doesn't have comprehensive state privacy law (yet)
- Documents follow general US consumer protection standards

### Children's Online Privacy Protection Act (COPPA)
✅ **Compliant** - App is 18+ only
- Section 7 explicitly states no collection from children under 13

---

## 🔄 Updating These Documents

**When to update:**
- Before launching new features (e.g., Stripe payments, SMS notifications)
- If data collection practices change
- When laws change (annually review recommended)
- After user feedback or legal review

**How to update:**
1. Edit the Markdown files
2. Regenerate HTML (or manually edit HTML files)
3. Update "Last Updated" date
4. Notify users if changes are significant

---

## ⚖️ Legal Disclaimer

These documents were created as production-ready templates based on industry best practices and common legal requirements. However:

- **They are NOT a substitute for legal advice**
- Consider having a lawyer review them before launch
- Laws vary by jurisdiction and change over time
- Your specific business needs may require additional terms

**Cost-effective option:** Use a service like [Termly](https://termly.io) or [iubenda](https://www.iubenda.com) to generate legally-reviewed policies, or have a lawyer review these for ~$300-500.

---

## 📋 Checklist for App Store Submission

- [ ] Replace all placeholder text with real contact info
- [ ] Upload HTML files to your website
- [ ] Test that privacy policy URL loads correctly
- [ ] Add privacy policy link in app settings
- [ ] Add terms of service link in app settings
- [ ] Implement account deletion feature
- [ ] Fill out App Store privacy questionnaire
- [ ] Fill out Google Play Data Safety section
- [ ] Add privacy policy acceptance during signup flow
- [ ] Test on real device before submitting

---

## 🎯 Next Steps

1. **Customize placeholders** (see checklist above)
2. **Get legal review** (recommended, ~$300-500)
3. **Host HTML files** on your domain
4. **Integrate links** into your app
5. **Submit to app stores** with confidence! 🚀

---

## 📞 Need Help?

If you have questions about implementing these documents:
- Check App Store Connect documentation
- Review Google Play Console help
- Consult with a lawyer for legal interpretation
- Use online policy generators as a comparison

---

**Created:** February 7, 2026  
**For:** JunkOS by Gymbuddy / Shamar Donaldson  
**Service Area:** Tampa, FL

Good luck with your app launch! 🗑️✨

# JunkOS Legal Documents - Customization Checklist

Use this checklist to customize your legal documents before publishing.

## 🔍 Find & Replace

Use your text editor's find-and-replace feature to update these placeholders across ALL files:

### 1. Contact Information

| Placeholder | Replace With | Example |
|-------------|--------------|---------|
| `[insert support email]` | Your support email | `support@junkos.app` |
| `[privacy email]` | Your privacy contact email | `privacy@junkos.app` or same as support |
| `[support phone number]` | Your support phone | `(813) 555-0123` |
| `[Tampa, FL address]` or `[Tampa, FL address if applicable]` | Your business address | `123 Main St, Tampa, FL 33602` |

### 2. Website Links

| Placeholder | Replace With | Example |
|-------------|--------------|---------|
| `[link to hosted privacy policy]` | URL where you'll host the policy | `https://junkos.app/privacy-policy.html` |

---

## 📄 Files to Update

### Update these 5 files:

- [ ] `PRIVACY_POLICY.md`
  - [ ] Support email (appears 2 times)
  - [ ] Privacy email (appears 1 time)
  - [ ] Address (appears 1 time)
  - [ ] Phone number (appears 1 time)

- [ ] `PRIVACY_POLICY_SHORT.md`
  - [ ] Support email (appears 1 time)
  - [ ] Hosted privacy policy link (appears 1 time)

- [ ] `privacy-policy.html`
  - [ ] Support email (appears 2 times)
  - [ ] Privacy email (appears 1 time)
  - [ ] Address (appears 1 time)
  - [ ] Phone number (appears 1 time)

- [ ] `TERMS_OF_SERVICE.md`
  - [ ] Support email (appears 2 times)
  - [ ] Address (appears 1 time)
  - [ ] Phone number (appears 1 time)

- [ ] `terms-of-service.html`
  - [ ] Support email (appears 2 times)
  - [ ] Address (appears 1 time)
  - [ ] Phone number (appears 1 time)

---

## 🎯 Quick Commands (macOS/Linux)

If you're comfortable with command line, use these to find all placeholders:

```bash
# Navigate to the legal directory
cd ~/Documents/programs/webapps/junkos/legal/

# Find all files with placeholders
grep -r "\[insert" .
grep -r "\[privacy" .
grep -r "\[support" .
grep -r "\[Tampa" .
grep -r "\[link" .
```

### Replace all at once (CAREFUL - backup first!):

```bash
# Replace support email
find . -type f \( -name "*.md" -o -name "*.html" \) -exec sed -i.bak 's/\[insert support email\]/support@junkos.app/g' {} +

# Replace privacy email
find . -type f \( -name "*.md" -o -name "*.html" \) -exec sed -i.bak 's/\[privacy email\]/privacy@junkos.app/g' {} +

# Replace phone number
find . -type f \( -name "*.md" -o -name "*.html" \) -exec sed -i.bak 's/\[support phone number\]/(813) 555-0123/g' {} +

# Replace address
find . -type f \( -name "*.md" -o -name "*.html" \) -exec sed -i.bak 's/\[Tampa, FL address\]/123 Main St, Tampa, FL 33602/g' {} +
find . -type f \( -name "*.md" -o -name "*.html" \) -exec sed -i.bak 's/\[Tampa, FL address if applicable\]/123 Main St, Tampa, FL 33602/g' {} +

# Replace privacy policy link
find . -type f \( -name "*.md" -o -name "*.html" \) -exec sed -i.bak 's|\[link to hosted privacy policy\]|https://junkos.app/privacy-policy.html|g' {} +

# Remove backup files after verifying
rm *.bak
```

---

## ✅ Verification Checklist

After customizing, verify:

- [ ] No `[` brackets remain in any document
- [ ] All contact info is correct
- [ ] Email addresses are valid
- [ ] Phone number is formatted correctly
- [ ] Business address is complete
- [ ] Privacy policy URL will be accessible
- [ ] Company name is correct throughout (Gymbuddy / Shamar Donaldson)

---

## 🚀 Publishing Checklist

Before going live:

- [ ] Upload `privacy-policy.html` to your website
- [ ] Upload `terms-of-service.html` to your website
- [ ] Test that both URLs load correctly
- [ ] Add links in your app's settings menu
- [ ] Have a lawyer review (recommended)
- [ ] Update App Store Connect with privacy URL
- [ ] Update Google Play Console with privacy URL

---

## 📧 Example Contact Info Format

**Good examples:**

- Email: `support@junkos.app` or `contact@junkos.com`
- Phone: `(813) 555-0123` or `813-555-0123`
- Address: `123 Main Street, Tampa, FL 33602` (include suite # if applicable)

**Avoid:**
- Generic emails like `info@gmail.com`
- Personal phone numbers (get a Google Voice number if needed)
- P.O. boxes (use actual business address if possible)

---

## 🔐 Privacy Tip

Consider setting up these email addresses:
- `support@yourdomain.com` - General support
- `privacy@yourdomain.com` - Privacy-specific requests (can forward to support)
- `hello@yourdomain.com` - General inquiries

This looks more professional and separates concerns.

---

## ⏱️ Estimated Time

- **Manual editing:** 15-20 minutes
- **Using find-and-replace:** 5-10 minutes
- **Using command line:** 2-3 minutes
- **Verification:** 5 minutes

**Total:** ~30 minutes to fully customize all documents.

---

**Ready to launch?** Once you've completed this checklist, your legal documents are production-ready! 🎉

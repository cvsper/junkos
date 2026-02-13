# Fastlane Automation for Umuve

This directory contains Fastlane configuration for automating Umuve iOS deployment.

## Installation

### 1. Install Fastlane

```bash
# Via Homebrew (recommended)
brew install fastlane

# Or via RubyGems
gem install fastlane
```

### 2. Configure Credentials

**Option A: Environment Variables (Recommended)**

Add to your `~/.zshrc` or `~/.bash_profile`:

```bash
export FASTLANE_APPLE_ID="your@email.com"
export FASTLANE_TEAM_ID="ABC123XYZ"
export FASTLANE_ITC_TEAM_ID="ABC123XYZ"  # Usually same as TEAM_ID
export FASTLANE_APP_SPECIFIC_PASSWORD="xxxx-xxxx-xxxx-xxxx"
```

**Find your Team ID:**
1. Go to: https://developer.apple.com/account
2. Click "Membership"
3. Copy "Team ID"

**Create App-Specific Password:**
1. Go to: https://appleid.apple.com
2. Sign in → Security → App-Specific Passwords
3. Generate password
4. Save it (you won't see it again)

**Option B: Edit Appfile Directly**

Edit `fastlane/Appfile` and replace placeholders:

```ruby
apple_id("your@email.com")
team_id("ABC123XYZ")
```

---

## Available Lanes

### 🚀 Deploy to TestFlight

**Upload new build to TestFlight:**

```bash
fastlane beta
```

This will:
1. Increment build number automatically
2. Build the app
3. Upload to App Store Connect
4. Wait for processing

---

### 🏗️ Build Only

**Build IPA without uploading:**

```bash
fastlane build_only
```

Output: `./build/Umuve.ipa`

---

### ⚡ Quick Build

**Fast build for testing (no code signing):**

```bash
fastlane quick_build
```

---

### 🧪 Run Tests

**Run all unit and UI tests:**

```bash
fastlane test
```

---

### 📸 Generate Screenshots

**Create App Store screenshots:**

```bash
fastlane screenshots
```

Output: `./screenshots/`

Requires: UI tests with snapshot integration

---

### 🔢 Version Management

**Increment build number:**

```bash
fastlane bump_build
```

**Bump version numbers:**

```bash
fastlane bump_major  # 1.0.0 -> 2.0.0
fastlane bump_minor  # 1.0.0 -> 1.1.0
fastlane bump_patch  # 1.0.0 -> 1.0.1
```

---

### ✅ Validate Build

**Validate without uploading:**

```bash
fastlane validate
```

---

### 🎯 Submit for App Store Review

**After TestFlight testing, submit for public release:**

```bash
fastlane release
```

**Note:** Ensure you have:
- Completed app metadata
- Added screenshots
- Filled privacy policy
- Tested thoroughly in TestFlight

---

### 🔧 Initial Setup

**First-time setup:**

```bash
fastlane setup
```

Checks:
- Xcode version
- Certificates
- Provisioning profiles

---

## Typical Workflow

### First Deployment

```bash
# 1. Setup
fastlane setup

# 2. Deploy to TestFlight
fastlane beta

# 3. Wait for processing (~15 min)
# Check: https://appstoreconnect.apple.com

# 4. Add testers in App Store Connect
```

### Subsequent Updates

```bash
# 1. Make code changes
# 2. Test locally
# 3. Commit changes

# 4. Deploy new build
fastlane beta
```

### Preparing for App Store

```bash
# 1. Complete TestFlight testing
# 2. Bump version if needed
fastlane bump_minor  # 1.0.0 -> 1.1.0

# 3. Create new build
fastlane beta

# 4. Submit for review
fastlane release
```

---

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/testflight.yml`:

```yaml
name: Deploy to TestFlight

on:
  push:
    tags:
      - 'v*'

jobs:
  deploy:
    runs-on: macos-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Ruby
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.0'
      
      - name: Install Fastlane
        run: |
          gem install bundler
          bundle install
      
      - name: Deploy to TestFlight
        env:
          FASTLANE_APPLE_ID: ${{ secrets.APPLE_ID }}
          FASTLANE_TEAM_ID: ${{ secrets.TEAM_ID }}
          FASTLANE_APP_SPECIFIC_PASSWORD: ${{ secrets.APP_SPECIFIC_PASSWORD }}
        run: |
          fastlane beta
```

**Required Secrets:**
- `APPLE_ID` - Your Apple ID email
- `TEAM_ID` - Your Apple Developer Team ID
- `APP_SPECIFIC_PASSWORD` - App-specific password

---

## Configuration Files

### Fastfile

**Location:** `fastlane/Fastfile`

Contains all lane definitions (beta, test, release, etc.)

### Appfile

**Location:** `fastlane/Appfile`

Contains app-specific configuration:
- Apple ID
- Team ID
- Bundle identifier

### Deliverfile (Optional)

**Location:** `fastlane/Deliverfile`

Contains App Store metadata:
- App description
- Keywords
- Screenshots
- Support URL

To generate:
```bash
fastlane deliver init
```

---

## Troubleshooting

### Error: "Could not find action, lane or variable"

**Solution:**
```bash
# Update Fastlane
brew upgrade fastlane

# Or via gem
gem update fastlane
```

---

### Error: "User credentials are invalid"

**Solution:**

1. **Check Apple ID:**
   ```bash
   echo $FASTLANE_APPLE_ID
   ```

2. **Verify app-specific password:**
   - Recreate at: https://appleid.apple.com
   - Update environment variable

3. **Re-authenticate:**
   ```bash
   fastlane spaceauth -u your@email.com
   ```

---

### Error: "No signing certificate found"

**Solution:**

```bash
# Download certificates
fastlane match development
fastlane match appstore

# Or let Xcode manage
# Xcode → Preferences → Accounts → Download Manual Profiles
```

---

### Error: "Build number already used"

**Solution:**

```bash
# Increment build manually
agvtool next-version -all

# Or let fastlane do it
fastlane bump_build
```

---

## Environment Variables Reference

```bash
# Required
FASTLANE_APPLE_ID             # Your Apple ID email
FASTLANE_TEAM_ID              # Apple Developer Team ID
FASTLANE_APP_SPECIFIC_PASSWORD # App-specific password from appleid.apple.com

# Optional
FASTLANE_ITC_TEAM_ID          # iTunes Connect Team ID (usually same as TEAM_ID)
FASTLANE_SESSION              # Session cookie (for 2FA, expires after 30 days)
FASTLANE_SKIP_UPDATE_CHECK    # Skip update check (set to "1")
FASTLANE_HIDE_TIMESTAMP       # Hide timestamp in logs
FL_VERBOSE                    # Enable verbose mode
```

---

## Best Practices

### ✅ Do's

- ✅ Use environment variables for credentials
- ✅ Increment build number for each upload
- ✅ Test locally before deploying
- ✅ Commit version bumps to git
- ✅ Tag releases (e.g., `v1.0.0-build-1`)
- ✅ Use `fastlane validate` before uploading
- ✅ Keep `Fastfile` in version control

### ❌ Don'ts

- ❌ Commit credentials to git
- ❌ Skip testing before deployment
- ❌ Upload same build number twice
- ❌ Hardcode sensitive values in files
- ❌ Use personal Apple ID for team projects

---

## Additional Resources

**Official Documentation:**
- https://docs.fastlane.tools/
- https://docs.fastlane.tools/actions/

**Useful Plugins:**
- `fastlane-plugin-versioning` - Advanced version management
- `fastlane-plugin-badge` - Add badges to app icon
- `fastlane-plugin-changelog` - Generate changelogs

**Install plugins:**
```bash
fastlane add_plugin versioning
```

---

## Support

**Fastlane Issues:**
- GitHub: https://github.com/fastlane/fastlane/issues
- Slack: https://fastlane.tools/slack

**Umuve Specific:**
- Email: support@goumuve.com
- See: [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)

---

**Last Updated:** February 7, 2026

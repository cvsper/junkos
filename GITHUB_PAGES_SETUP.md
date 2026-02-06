# GitHub Pages Setup Guide for JunkOS

## ✅ What's Been Completed

- ✅ Git repository initialized
- ✅ `docs/` folder created with privacy policy
- ✅ `.gitignore` configured (excludes node_modules, .env, etc.)
- ✅ Initial commit created with all project files
- ✅ Privacy policy copied to:
  - `docs/index.html` (main page)
  - `docs/privacy.html` (privacy page)

## 🚀 Next Steps: Create GitHub Repo & Enable Pages

### Step 1: Create GitHub Repository

**Option A: Using GitHub CLI (gh)**

```bash
cd ~/Documents/programs/webapps/junkos/
gh repo create junkos --public --source=. --remote=origin --push
```

**Option B: Using GitHub Web Interface**

1. Go to https://github.com/new
2. Repository name: `junkos`
3. Description: "JunkOS - Junk Removal Management System"
4. Choose: **Public** (required for free GitHub Pages)
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click "Create repository"

Then run these commands:

```bash
cd ~/Documents/programs/webapps/junkos/

# Add the remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/junkos.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### Step 2: Enable GitHub Pages

**Option A: Using GitHub CLI (gh)**

```bash
# Enable Pages with docs folder as source
gh api repos/:owner/junkos/pages -X POST -F source[branch]=main -F source[path]=/docs
```

**Option B: Using GitHub Web Interface**

1. Go to your repo: `https://github.com/YOUR_USERNAME/junkos`
2. Click **Settings** (top navigation)
3. Scroll down to **Pages** (left sidebar under "Code and automation")
4. Under **Source**, select:
   - Branch: `main`
   - Folder: `/docs`
5. Click **Save**
6. Wait 1-2 minutes for deployment

### Step 3: Verify Deployment

After a few minutes, your site will be live at:

**Main page (privacy policy):**
```
https://YOUR_USERNAME.github.io/junkos/
```

**Privacy policy page:**
```
https://YOUR_USERNAME.github.io/junkos/privacy.html
```

Both URLs serve the same content (privacy policy) since we copied it to both `index.html` and `privacy.html`.

### Step 4: Get the Exact URL

```bash
# Check deployment status and get URL
gh repo view --web

# Or check Pages URL programmatically
gh api repos/:owner/junkos/pages | grep html_url
```

## 📋 Quick Command Reference

### Push Future Changes

After making changes to the privacy policy:

```bash
cd ~/Documents/programs/webapps/junkos/

# Update the HTML files
cp legal/privacy-policy.html docs/index.html
cp legal/privacy-policy.html docs/privacy.html

# Commit and push
git add docs/
git commit -m "Update privacy policy"
git push
```

GitHub Pages will automatically redeploy within 1-2 minutes.

### Check Build Status

```bash
# View latest GitHub Actions run (Pages deployment)
gh run list --limit 5

# View deployment status
gh api repos/:owner/junkos/pages
```

## 🔧 Troubleshooting

### Pages not showing up?

1. **Check Settings**: Ensure Pages is enabled in Settings → Pages
2. **Wait**: First deployment can take 2-5 minutes
3. **Check Actions**: Go to Actions tab to see if deployment succeeded
4. **Force refresh**: Clear browser cache or try incognito mode

### Need to change source folder?

If you want to use a different folder:
1. Go to Settings → Pages
2. Change folder to `/` (root) or `/docs`
3. Move your HTML files accordingly

### Want to use a custom domain?

1. In Settings → Pages, add your custom domain
2. Add a `CNAME` file to `docs/` with your domain:
   ```bash
   echo "privacy.junkos.com" > docs/CNAME
   git add docs/CNAME
   git commit -m "Add custom domain"
   git push
   ```
3. Configure DNS:
   - Add CNAME record pointing to `YOUR_USERNAME.github.io`
   - Wait for DNS propagation (5-30 minutes)

## 🎯 Expected URL Format

Replace `YOUR_USERNAME` with your actual GitHub username:

- **Main page**: `https://YOUR_USERNAME.github.io/junkos/`
- **Privacy page**: `https://YOUR_USERNAME.github.io/junkos/privacy.html`

Example for username "johndoe":
- https://johndoe.github.io/junkos/
- https://johndoe.github.io/junkos/privacy.html

## 📝 Notes

- GitHub Pages is **free for public repositories**
- Updates deploy automatically on push to `main` branch
- First deployment: 2-5 minutes
- Subsequent updates: 1-2 minutes
- Pages uses the `docs/` folder on the `main` branch
- Both `index.html` and `privacy.html` contain the same privacy policy

## ✨ You're Done!

Once you complete the steps above, your privacy policy will be live and accessible at:
`https://YOUR_USERNAME.github.io/junkos/privacy.html`

You can use this URL in your app's privacy policy links, App Store submission, etc.

# Quick Command Reference

## 🚀 ONE-LINE SETUP (if you have GitHub CLI)

```bash
cd ~/Documents/programs/webapps/junkos/ && ./GITHUB_PAGES_QUICKSTART.sh
```

## 📋 MANUAL COMMANDS (copy-paste these)

### Create GitHub Repo & Push (replace YOUR_USERNAME)

```bash
cd ~/Documents/programs/webapps/junkos/

# Add GitHub remote
git remote add origin https://github.com/YOUR_USERNAME/junkos.git

# Push code
git branch -M main
git push -u origin main
```

### Enable GitHub Pages (using GitHub CLI)

```bash
gh api repos/:owner/junkos/pages -X POST -F source[branch]=main -F source[path]=/docs
```

### Or Enable Pages via Web

1. Go to: `https://github.com/YOUR_USERNAME/junkos/settings/pages`
2. Source: `main` branch
3. Folder: `/docs`
4. Click **Save**

## 🌐 Your URLs

```
https://YOUR_USERNAME.github.io/junkos/
https://YOUR_USERNAME.github.io/junkos/privacy.html
```

## 🔄 Update Privacy Policy Later

```bash
cd ~/Documents/programs/webapps/junkos/
cp legal/privacy-policy.html docs/index.html
cp legal/privacy-policy.html docs/privacy.html
git add docs/
git commit -m "Update privacy policy"
git push
```

Auto-deploys in 1-2 minutes! ✨

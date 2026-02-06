#!/bin/bash
# GitHub Pages Quick Setup for JunkOS
# Run this script or copy-paste individual commands

set -e  # Exit on error

echo "🚀 GitHub Pages Setup for JunkOS"
echo "================================="
echo ""

# Navigate to project directory
cd ~/Documents/programs/webapps/junkos/

# Check if gh CLI is installed
if command -v gh &> /dev/null; then
    echo "✓ GitHub CLI detected"
    echo ""
    echo "Creating GitHub repository and pushing code..."
    
    # Create repo and push (will prompt for confirmation)
    gh repo create junkos --public --source=. --remote=origin --push
    
    echo ""
    echo "Enabling GitHub Pages..."
    sleep 2  # Brief pause for repo creation
    
    # Enable Pages with docs folder
    gh api repos/:owner/junkos/pages -X POST -F source[branch]=main -F source[path]=/docs
    
    echo ""
    echo "✅ Setup complete!"
    echo ""
    echo "Your privacy policy will be live in 2-5 minutes at:"
    echo "https://$(gh api user --jq .login).github.io/junkos/"
    echo "https://$(gh api user --jq .login).github.io/junkos/privacy.html"
    
else
    echo "⚠️  GitHub CLI (gh) not found"
    echo ""
    echo "Please install it: https://cli.github.com/"
    echo ""
    echo "Or follow these manual steps:"
    echo ""
    echo "1. Create a new repo at: https://github.com/new"
    echo "   - Name: junkos"
    echo "   - Public repository"
    echo "   - Don't initialize with README"
    echo ""
    echo "2. Run these commands (replace YOUR_USERNAME):"
    echo ""
    echo "   git remote add origin https://github.com/YOUR_USERNAME/junkos.git"
    echo "   git branch -M main"
    echo "   git push -u origin main"
    echo ""
    echo "3. Enable Pages:"
    echo "   - Go to: Settings → Pages"
    echo "   - Source: main branch"
    echo "   - Folder: /docs"
    echo "   - Click Save"
    echo ""
    echo "4. Your site will be live at:"
    echo "   https://YOUR_USERNAME.github.io/junkos/"
fi

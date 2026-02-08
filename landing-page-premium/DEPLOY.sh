#!/bin/bash

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# JunkOS Premium Landing Page - Quick Deploy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -e  # Exit on error

echo "🚛 JunkOS Premium Landing Page Deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if Vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "⚠️  Vercel CLI not found. Installing..."
    npm install -g vercel
fi

# Confirm deployment
echo "📦 Ready to deploy to Vercel?"
echo ""
echo "Current directory: $(pwd)"
echo "Files to deploy:"
ls -lh index.html styles.css script.js
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled"
    exit 1
fi

# Deploy
echo ""
echo "🚀 Deploying to Vercel..."
vercel --prod

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Your landing page is now live!"
echo "📊 View deployment: https://vercel.com/dashboard"
echo ""
echo "Next steps:"
echo "  1. Test on mobile and desktop"
echo "  2. Check all CTAs (phone + SMS links)"
echo "  3. Verify animations run smoothly"
echo "  4. Set up custom domain (if needed)"
echo "  5. Add analytics tracking"
echo ""
echo "Questions? Text (561) 888-3427 📱"

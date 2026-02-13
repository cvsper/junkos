#!/bin/bash
# Umuve Asset Setup Script
# Integrates generated assets into mobile app

set -e

ASSETS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MOBILE_DIR="$ASSETS_DIR/../mobile"
IOS_NATIVE_DIR="$ASSETS_DIR/../ios-native"

echo "🚛 Umuve Asset Setup"
echo "====================="
echo ""

# Check if mobile directory exists
if [ ! -d "$MOBILE_DIR" ]; then
    echo "❌ Mobile app directory not found at $MOBILE_DIR"
    exit 1
fi

# Function to copy icon to React Native/Expo
setup_mobile_icon() {
    echo "📱 Setting up mobile app icon..."
    
    if [ -f "$ASSETS_DIR/icon/umuve-icon-1024.png" ]; then
        cp "$ASSETS_DIR/icon/umuve-icon-1024.png" "$MOBILE_DIR/assets/icon.png"
        echo "✅ Icon copied to mobile/assets/icon.png"
    else
        echo "⚠️  Icon not found. Generate it first by opening:"
        echo "   open $ASSETS_DIR/icon/generate-icon.html"
    fi
}

# Function to copy launch screen
setup_mobile_splash() {
    echo "🎨 Setting up launch screen..."
    
    if [ -f "$ASSETS_DIR/launch-screen/umuve-launch-16pro.png" ]; then
        cp "$ASSETS_DIR/launch-screen/umuve-launch-16pro.png" "$MOBILE_DIR/assets/splash.png"
        echo "✅ Launch screen copied to mobile/assets/splash.png"
    else
        echo "⚠️  Launch screen not found. Generate it first by opening:"
        echo "   open $ASSETS_DIR/launch-screen/generate-launch.html"
    fi
}

# Function to update app.json
update_app_config() {
    echo "⚙️  Updating app.json configuration..."
    
    APP_JSON="$MOBILE_DIR/app.json"
    
    if [ -f "$APP_JSON" ]; then
        # Backup original
        cp "$APP_JSON" "$APP_JSON.backup"
        
        # Update icon and splash config (basic example - adjust based on actual structure)
        echo "✅ app.json backed up"
        echo "📝 Manually update app.json with:"
        echo '   "icon": "./assets/icon.png"'
        echo '   "splash": {"image": "./assets/splash.png", "backgroundColor": "#F5F3FF"}'
    else
        echo "⚠️  app.json not found in mobile directory"
    fi
}

# Function to setup iOS native assets
setup_ios_native() {
    echo "🍎 iOS Native assets..."
    
    if [ -d "$IOS_NATIVE_DIR" ]; then
        echo "📋 To add icons to Xcode:"
        echo "   1. Open $IOS_NATIVE_DIR/Umuve.xcodeproj"
        echo "   2. Select Assets.xcassets → AppIcon"
        echo "   3. Drag icons from $ASSETS_DIR/icon/"
        echo "   4. Place:"
        echo "      - umuve-icon-1024.png → App Store"
        echo "      - umuve-icon-180.png → iPhone 60pt @3x"
        echo "      - umuve-icon-120.png → iPhone 60pt @2x"
        echo "      - umuve-icon-60.png → iPhone 20pt @3x"
    else
        echo "ℹ️  iOS native project not found (optional)"
    fi
}

# Create directories for screenshots
setup_screenshot_dirs() {
    echo "📸 Setting up screenshot directories..."
    mkdir -p "$ASSETS_DIR/screenshots/raw"
    mkdir -p "$ASSETS_DIR/screenshots/final"
    echo "✅ Created screenshot directories"
}

# Main execution
echo "Select setup option:"
echo "1) Mobile app (React Native/Expo)"
echo "2) iOS Native (Xcode)"
echo "3) Both"
echo "4) Just create directories"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        setup_mobile_icon
        setup_mobile_splash
        update_app_config
        setup_screenshot_dirs
        ;;
    2)
        setup_ios_native
        setup_screenshot_dirs
        ;;
    3)
        setup_mobile_icon
        setup_mobile_splash
        update_app_config
        setup_ios_native
        setup_screenshot_dirs
        ;;
    4)
        setup_screenshot_dirs
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next Steps:"
echo "1. Generate assets by opening HTML files in browser"
echo "2. Download all icon sizes and launch screens"
echo "3. Run this script again to copy them to the app"
echo "4. Follow $ASSETS_DIR/screenshots/SCREENSHOT_GUIDE.md to capture app screenshots"
echo "5. Use marketing copy in $ASSETS_DIR/marketing-copy/ for App Store"
echo ""
echo "🚀 Ready to ship!"

#!/bin/bash
# Automated screenshot capture for JunkOS iOS app
# Captures screenshots from running iOS simulator

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
RAW_DIR="$SCRIPT_DIR/raw"
DEVICE="iPhone 16 Pro Max"

echo "📸 JunkOS Screenshot Capture"
echo "============================"
echo ""

# Create output directory
mkdir -p "$RAW_DIR"

# Check if simulator is running
if ! pgrep -x "Simulator" > /dev/null; then
    echo "❌ iOS Simulator is not running"
    echo "Please start the simulator and run the app first"
    echo ""
    echo "To start:"
    echo "  cd ~/Documents/programs/webapps/junkos/mobile"
    echo "  npm start"
    echo "  # Press 'i' to launch iOS simulator"
    exit 1
fi

echo "✅ Simulator detected"
echo ""

# Get device UDID
DEVICE_UDID=$(xcrun simctl list devices | grep "$DEVICE" | grep "Booted" | awk -F'[()]' '{print $2}' | head -1)

if [ -z "$DEVICE_UDID" ]; then
    echo "❌ iPhone 16 Pro Max simulator is not booted"
    echo "Available devices:"
    xcrun simctl list devices | grep "Booted"
    exit 1
fi

echo "📱 Device: $DEVICE"
echo "🆔 UDID: $DEVICE_UDID"
echo ""

# Screenshot capture function
capture_screen() {
    local filename=$1
    local description=$2
    
    echo "📸 Capturing: $description"
    echo "   Navigate to the screen and press ENTER..."
    read
    
    xcrun simctl io "$DEVICE_UDID" screenshot "$RAW_DIR/$filename"
    
    # Verify dimensions
    local dimensions=$(sips -g pixelWidth -g pixelHeight "$RAW_DIR/$filename" | awk '{print $2}' | tr '\n' 'x' | sed 's/x$//')
    echo "   ✅ Saved: $filename ($dimensions)"
    echo ""
}

# Capture all 6 required screenshots
echo "🎬 Ready to capture screenshots"
echo "Make sure your app is running and you can navigate through it"
echo ""

capture_screen "01-welcome.png" "Welcome/Onboarding Screen"
capture_screen "02-address.png" "Address Input Screen"
capture_screen "03-photos.png" "Photo Upload Screen"
capture_screen "04-estimate.png" "Service/Estimate Screen"
capture_screen "05-schedule.png" "Date/Time Selection"
capture_screen "06-confirmation.png" "Confirmation/Tracking Screen"

echo "✅ All screenshots captured!"
echo ""
echo "📁 Screenshots saved to: $RAW_DIR"
echo ""
echo "📋 Next steps:"
echo "1. Review screenshots for quality"
echo "2. Add text overlays in Figma/Photoshop (see SCREENSHOT_GUIDE.md)"
echo "3. Export final versions to screenshots/final/"
echo "4. Verify all are 1290×2796 pixels"
echo ""
echo "🎨 Overlay text suggestions in SCREENSHOT_GUIDE.md"

# List captured files
echo ""
echo "Captured files:"
ls -lh "$RAW_DIR/"

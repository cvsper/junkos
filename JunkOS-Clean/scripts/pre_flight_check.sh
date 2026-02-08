#!/bin/bash

# Pre-flight Check Script for JunkOS TestFlight Deployment
# Run this before archiving and uploading to catch issues early

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "🚀 JunkOS Pre-Flight Check"
echo "=========================="
echo ""

# Change to project directory
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_DIR"

ERRORS=0
WARNINGS=0

# Function to print status
print_check() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        ((ERRORS++))
    fi
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARNINGS++))
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

echo "1. Checking Xcode Configuration..."
echo "-----------------------------------"

# Check if Xcode is installed
if command -v xcodebuild &> /dev/null; then
    XCODE_VERSION=$(xcodebuild -version | head -n 1)
    print_check 0 "Xcode installed: $XCODE_VERSION"
else
    print_check 1 "Xcode is not installed"
    exit 1
fi

# Check if xcodeproj exists
if [ -f "JunkOS.xcodeproj/project.pbxproj" ]; then
    print_check 0 "Project file found"
else
    print_check 1 "JunkOS.xcodeproj not found"
    exit 1
fi

echo ""
echo "2. Checking Build Configuration..."
echo "-----------------------------------"

# Get bundle identifier
BUNDLE_ID=$(xcodebuild -project JunkOS.xcodeproj -showBuildSettings 2>/dev/null | grep PRODUCT_BUNDLE_IDENTIFIER | head -n 1 | awk '{print $3}')
if [ -n "$BUNDLE_ID" ]; then
    print_check 0 "Bundle ID: $BUNDLE_ID"
else
    print_check 1 "Could not determine Bundle ID"
fi

# Get version number
VERSION=$(xcodebuild -project JunkOS.xcodeproj -showBuildSettings 2>/dev/null | grep MARKETING_VERSION | head -n 1 | awk '{print $3}')
if [ -n "$VERSION" ]; then
    print_check 0 "Version: $VERSION"
else
    print_check 1 "Could not determine version"
fi

# Get build number
BUILD=$(xcodebuild -project JunkOS.xcodeproj -showBuildSettings 2>/dev/null | grep CURRENT_PROJECT_VERSION | head -n 1 | awk '{print $3}')
if [ -n "$BUILD" ]; then
    print_check 0 "Build: $BUILD"
else
    print_check 1 "Could not determine build number"
fi

echo ""
echo "3. Checking Info.plist..."
echo "-----------------------------------"

INFO_PLIST="JunkOS/Info.plist"

# Check if Info.plist exists
if [ -f "$INFO_PLIST" ]; then
    print_check 0 "Info.plist found"
    
    # Check required keys
    if /usr/libexec/PlistBuddy -c "Print :CFBundleDisplayName" "$INFO_PLIST" &>/dev/null; then
        DISPLAY_NAME=$(/usr/libexec/PlistBuddy -c "Print :CFBundleDisplayName" "$INFO_PLIST")
        print_check 0 "Display Name: $DISPLAY_NAME"
    else
        print_warning "CFBundleDisplayName not set"
    fi
    
    if /usr/libexec/PlistBuddy -c "Print :NSPhotoLibraryUsageDescription" "$INFO_PLIST" &>/dev/null; then
        print_check 0 "NSPhotoLibraryUsageDescription present"
    else
        print_check 1 "NSPhotoLibraryUsageDescription missing (required for photo picker)"
    fi
    
    if /usr/libexec/PlistBuddy -c "Print :NSCameraUsageDescription" "$INFO_PLIST" &>/dev/null; then
        print_check 0 "NSCameraUsageDescription present"
    else
        print_check 1 "NSCameraUsageDescription missing (required for camera)"
    fi
    
else
    print_check 1 "Info.plist not found at $INFO_PLIST"
fi

echo ""
echo "4. Checking Assets..."
echo "-----------------------------------"

# Check for app icon
if [ -d "JunkOS/Assets.xcassets/AppIcon.appiconset" ]; then
    ICON_COUNT=$(ls -1 JunkOS/Assets.xcassets/AppIcon.appiconset/*.png 2>/dev/null | wc -l)
    if [ "$ICON_COUNT" -gt 0 ]; then
        print_check 0 "App icon assets found ($ICON_COUNT images)"
    else
        print_warning "App icon directory exists but no images found"
    fi
else
    print_check 1 "App icon asset catalog not found"
fi

echo ""
echo "5. Checking Code Signing..."
echo "-----------------------------------"

# Check for signing certificates
CERT_COUNT=$(security find-identity -v -p codesigning 2>/dev/null | grep "Apple Distribution" | wc -l)
if [ "$CERT_COUNT" -gt 0 ]; then
    print_check 0 "Distribution certificate found"
    security find-identity -v -p codesigning 2>/dev/null | grep "Apple Distribution" | head -n 1
else
    print_warning "No Apple Distribution certificate found (required for App Store)"
fi

# Check for provisioning profiles
PROFILE_COUNT=$(ls -1 ~/Library/MobileDevice/Provisioning\ Profiles/*.mobileprovision 2>/dev/null | wc -l)
if [ "$PROFILE_COUNT" -gt 0 ]; then
    print_check 0 "Provisioning profiles found ($PROFILE_COUNT)"
else
    print_warning "No provisioning profiles found"
fi

echo ""
echo "6. Testing Build..."
echo "-----------------------------------"

print_info "Attempting clean build..."

# Try to build (without signing)
if xcodebuild -project JunkOS.xcodeproj \
    -scheme JunkOS \
    -configuration Release \
    -destination 'generic/platform=iOS' \
    clean build \
    CODE_SIGN_IDENTITY="" \
    CODE_SIGNING_REQUIRED=NO \
    CODE_SIGNING_ALLOWED=NO \
    > /dev/null 2>&1; then
    print_check 0 "Build successful"
else
    print_check 1 "Build failed (see errors above)"
    print_info "Run full build to see details:"
    print_info "  xcodebuild -project JunkOS.xcodeproj -scheme JunkOS -configuration Release"
fi

echo ""
echo "7. Checking for Common Issues..."
echo "-----------------------------------"

# Check for .DS_Store files
DS_STORE_COUNT=$(find . -name ".DS_Store" -not -path "./build/*" -not -path "./.git/*" | wc -l)
if [ "$DS_STORE_COUNT" -eq 0 ]; then
    print_check 0 "No .DS_Store files in project"
else
    print_warning "Found $DS_STORE_COUNT .DS_Store file(s) (harmless but messy)"
fi

# Check derived data size
DERIVED_DATA="$HOME/Library/Developer/Xcode/DerivedData"
if [ -d "$DERIVED_DATA" ]; then
    DERIVED_SIZE=$(du -sh "$DERIVED_DATA" 2>/dev/null | awk '{print $1}')
    print_info "Derived data size: $DERIVED_SIZE"
    print_info "To clean: rm -rf ~/Library/Developer/Xcode/DerivedData"
fi

# Check git status (if in git repo)
if git rev-parse --git-dir > /dev/null 2>&1; then
    if git diff-index --quiet HEAD --; then
        print_check 0 "Git: No uncommitted changes"
    else
        print_warning "Git: Uncommitted changes present"
        print_info "Consider committing before deployment"
    fi
else
    print_info "Not a git repository"
fi

echo ""
echo "8. Environment Check..."
echo "-----------------------------------"

# Check for Fastlane
if command -v fastlane &> /dev/null; then
    FASTLANE_VERSION=$(fastlane --version | head -n 1)
    print_check 0 "Fastlane installed: $FASTLANE_VERSION"
    
    # Check for environment variables
    if [ -n "$FASTLANE_APPLE_ID" ]; then
        print_check 0 "FASTLANE_APPLE_ID configured"
    else
        print_warning "FASTLANE_APPLE_ID not set (needed for automated uploads)"
    fi
else
    print_info "Fastlane not installed (optional, but recommended)"
    print_info "Install: brew install fastlane"
fi

echo ""
echo "=================================="
echo "📊 Summary"
echo "=================================="

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Ready for deployment.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Open Xcode: open JunkOS.xcodeproj"
    echo "  2. Select 'Any iOS Device (arm64)'"
    echo "  3. Product → Archive"
    echo "  4. Distribute → App Store Connect"
    echo ""
    echo "Or use Fastlane:"
    echo "  fastlane beta"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  $WARNINGS warning(s) found.${NC}"
    echo "You can proceed, but review warnings above."
    exit 0
else
    echo -e "${RED}❌ $ERRORS error(s) found.${NC}"
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}⚠️  $WARNINGS warning(s) found.${NC}"
    fi
    echo ""
    echo "Fix errors before deploying."
    echo "See TROUBLESHOOTING.md for help."
    exit 1
fi

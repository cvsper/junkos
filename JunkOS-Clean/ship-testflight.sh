#!/usr/bin/env bash
# Ship Umuve to TestFlight.
#
# Prereqs (one-time):
#   sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
#   export APPLE_ID="your-apple-id@example.com"
#   export APP_SPECIFIC_PASSWORD="xxxx-xxxx-xxxx-xxxx"   # generate at https://appleid.apple.com
#
# Then just: ./ship-testflight.sh
set -euo pipefail

cd "$(dirname "$0")"

SCHEME="JunkOS"
PROJECT="JunkOS.xcodeproj"
ARCHIVE_PATH="./build/Umuve.xcarchive"
EXPORT_PATH="./build"
IPA_PATH="${EXPORT_PATH}/JunkOS.ipa"

: "${APPLE_ID:?Set APPLE_ID=your-apple-id@example.com}"
: "${APP_SPECIFIC_PASSWORD:?Set APP_SPECIFIC_PASSWORD=xxxx-xxxx-xxxx-xxxx (https://appleid.apple.com)}"

# Sanity check: xcode-select must point at Xcode, not CommandLineTools
DEV_DIR="$(xcode-select -p)"
if [[ "$DEV_DIR" != *"/Xcode.app/"* ]]; then
  echo "ERROR: xcode-select points at $DEV_DIR"
  echo "Run: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
  exit 1
fi

VERSION=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" JunkOS/Info.plist)
BUILD=$(/usr/libexec/PlistBuddy -c "Print :CFBundleVersion" JunkOS/Info.plist)
echo ">> Shipping Umuve v${VERSION} (build ${BUILD}) to TestFlight"

mkdir -p "$EXPORT_PATH"
rm -rf "$ARCHIVE_PATH"

echo ">> [1/3] Archiving..."
xcodebuild \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath "$ARCHIVE_PATH" \
  -allowProvisioningUpdates \
  clean archive

if [ ! -d "$ARCHIVE_PATH" ]; then
  echo "ERROR: Archive failed — no archive at $ARCHIVE_PATH"
  exit 1
fi

echo ">> [2/3] Exporting IPA..."
xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE_PATH" \
  -exportPath "$EXPORT_PATH" \
  -exportOptionsPlist ExportOptions.plist \
  -allowProvisioningUpdates

if [ ! -f "$IPA_PATH" ]; then
  echo "ERROR: Export failed — no IPA at $IPA_PATH"
  exit 1
fi

echo ">> [3/3] Uploading to TestFlight..."
xcrun altool --upload-app \
  --type ios \
  --file "$IPA_PATH" \
  --username "$APPLE_ID" \
  --password "$APP_SPECIFIC_PASSWORD"

echo ""
echo "Build ${BUILD} uploaded. Apple typically processes for 10-30 min."
echo "Track at: https://appstoreconnect.apple.com/apps"

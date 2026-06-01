#!/usr/bin/env bash
#
# Umuve Pro — archive + upload to App Store Connect.
#
# Prereqs (one-time):
#   1. Be signed into your Apple Developer account in Xcode
#      (Xcode → Settings → Accounts → add the Gymbuddy LLC Apple ID).
#   2. Bundle id com.goumuve.pro registered in App Store Connect and an app
#      record created (see Docs/AppStore-Metadata.md).
#   3. Xcode (full) installed; this script points DEVELOPER_DIR at it.
#
# Then just:  ./archive-and-upload.sh
#
# It uses automatic signing (-allowProvisioningUpdates), so Xcode will fetch /
# create the Distribution cert + provisioning profile for you.
set -euo pipefail

export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
SCHEME="Umuve Pro"
PROJECT="JunkOS-Driver.xcodeproj"
ARCHIVE="build/UmuvePro.xcarchive"
EXPORT_DIR="build/export"

echo "==> Regenerating project from project.yml"
xcodegen generate

echo "==> Archiving (Release, signed)"
xcodebuild \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath "$ARCHIVE" \
  -allowProvisioningUpdates \
  clean archive

echo "==> Exporting + uploading to App Store Connect"
xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE" \
  -exportOptionsPlist ExportOptions.plist \
  -exportPath "$EXPORT_DIR" \
  -allowProvisioningUpdates

echo "==> Done. Build uploaded — check App Store Connect → TestFlight in ~10-30 min."
echo "    If export-method upload is disabled, the .ipa is in $EXPORT_DIR —"
echo "    upload it with Transporter.app instead."

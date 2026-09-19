#!/usr/bin/env bash
# Umuve Desk — archive + upload to App Store Connect (TestFlight).
#
# One-time prereqs, all in your Apple Developer / App Store Connect account:
#   1. App ID com.goumuve.desk with Push Notifications enabled
#   2. An App Store Connect app record for that bundle id
#   3. Xcode signed in to the team (Xcode → Settings → Accounts)
# Then:  ./archive-and-upload.sh
set -euo pipefail
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
SCHEME="Umuve Desk"; PROJECT="UmuveDesk.xcodeproj"
ARCHIVE="build/UmuveDesk.xcarchive"; EXPORT_DIR="build/export"

echo "==> Regenerating project from project.yml"; xcodegen generate
echo "==> Archiving (Release, signed)"
xcodebuild -project "$PROJECT" -scheme "$SCHEME" -configuration Release \
  -destination 'generic/platform=iOS' -archivePath "$ARCHIVE" \
  -allowProvisioningUpdates clean archive
echo "==> Exporting + uploading to App Store Connect"
xcodebuild -exportArchive -archivePath "$ARCHIVE" \
  -exportOptionsPlist ExportOptions.plist -exportPath "$EXPORT_DIR" -allowProvisioningUpdates
echo "==> Uploaded. App Store Connect → TestFlight shows it in ~10-30 min."

#!/bin/bash
# Simple script to add NavigationOverlay.swift to pbxproj
FILE_PATH="Views/Map/NavigationOverlay.swift"
UUID=$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | cut -c1-24)

# This is a simplified approach - may need manual verification
echo "File needs to be added manually in Xcode"
echo "File: $FILE_PATH"
echo "Generated UUID: $UUID"

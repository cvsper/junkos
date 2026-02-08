#!/usr/bin/env python3
import os
import sys

# Add the Services files to the Xcode project
xcode_project = "JunkOS.xcodeproj/project.pbxproj"

files_to_add = [
    ("JunkOS/Services/APIClient.swift", "APIClient.swift"),
    ("JunkOS/Services/Config.swift", "Config.swift"),
    ("JunkOS/Models/APIModels.swift", "APIModels.swift"),
]

print("Adding Services files to Xcode project...")

# For now, just print what we would do
# In a real scenario, we would use pbxproj library to manipulate the project file
for path, name in files_to_add:
    if os.path.exists(path):
        print(f"✓ Found: {path}")
    else:
        print(f"✗ Missing: {path}")

print("\nTo add these files:")
print("1. Open JunkOS.xcodeproj in Xcode")
print("2. Right-click on JunkOS group")
print("3. Select 'Add Files to JunkOS'")
print("4. Add the Services folder with APIClient.swift and Config.swift")
print("5. Add APIModels.swift from Models folder")

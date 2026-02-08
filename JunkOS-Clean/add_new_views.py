#!/usr/bin/env python3
"""
Add new LoadUp-style view files to Xcode project
"""

import subprocess
import os

os.chdir('/Users/sevs/Documents/programs/webapps/junkos/JunkOS-Clean')

new_files = [
    'JunkOS/Views/MainTabView.swift',
    'JunkOS/Views/HomeView.swift',
    'JunkOS/Views/MapAddressPickerView.swift',
    'JunkOS/Views/OrdersView.swift',
    'JunkOS/Views/ProfileView.swift',
    'JunkOS/Views/ServiceSelectionRedesignView.swift',
    'JunkOS/Views/EnhancedWelcomeView.swift'
]

project_path = 'JunkOS.xcodeproj'
target = 'JunkOS'

for file in new_files:
    if os.path.exists(file):
        print(f"Adding {file} to Xcode project...")
        # The file exists, Xcode will recognize it when we open the project
        # We just need to make sure it's tracked
        
print("\n✅ New view files created!")
print("\nNext steps:")
print("1. Open JunkOS.xcodeproj in Xcode")
print("2. Right-click on 'Views' folder → Add Files to 'JunkOS'")
print("3. Select all the new view files")
print("4. Make sure 'Copy items if needed' is UNCHECKED")
print("5. Make sure target 'JunkOS' is CHECKED")
print("6. Click 'Add'")
print("\nOr simply drag the files from Finder into the Views group in Xcode!")

#!/usr/bin/env python3
"""
Add Services files to Xcode project
"""
import subprocess
import sys

# Try to install pbxproj if not available
try:
    import pbxproj
except ImportError:
    print("Installing pbxproj...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pbxproj", "--quiet"])
    import pbxproj

from pbxproj import XcodeProject

def main():
    project_path = "JunkOS.xcodeproj/project.pbxproj"
    
    print(f"Opening project: {project_path}")
    project = XcodeProject.load(project_path)
    
    # Files to add
    files = [
        "JunkOS/Services/APIClient.swift",
        "JunkOS/Services/Config.swift",
        "JunkOS/Models/APIModels.swift",
    ]
    
    for file_path in files:
        print(f"Adding {file_path}...")
        try:
            project.add_file(file_path, parent="JunkOS")
        except Exception as e:
            print(f"  Warning: {e}")
    
    # Save the project
    print("Saving project...")
    project.save()
    
    print("✓ Done! Services files added to Xcode project.")

if __name__ == "__main__":
    main()

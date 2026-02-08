#!/usr/bin/env python3
"""Fix the malformed PBXBuildFile line in project.pbxproj"""

pbxproj_path = "JunkOS.xcodeproj/project.pbxproj"

# Read the file
with open(pbxproj_path, 'r') as f:
    content = f.read()

# The problematic line (spaces after the semicolon are actually tabs)
old_line = "A1000020000000000000001 /* ConfirmationViewModel.swift in Sources */ = {isa = PBXBuildFile; fileRef = A2000020000000000000001 /* ConfirmationViewModel.swift */; \t\tEDB5AD06CF7547388A232826 /* SkeletonView.swift in Sources */ = {isa = PBXBuildFile; fileRef = E5D5500A0E3C45398C236E76 /* SkeletonView.swift */; };"

# What it should be (two separate lines)
new_lines = """A1000020000000000000001 /* ConfirmationViewModel.swift in Sources */ = {isa = PBXBuildFile; fileRef = A2000020000000000000001 /* ConfirmationViewModel.swift */; };
\t\tEDB5AD06CF7547388A232826 /* SkeletonView.swift in Sources */ = {isa = PBXBuildFile; fileRef = E5D5500A0E3C45398C236E76 /* SkeletonView.swift */; };"""

# Replace
if old_line in content:
    content = content.replace(old_line, new_lines)
    print("✅ Fixed formatting error")
else:
    print("⚠️  Pattern not found, trying alternative...")
    # Try without exact tab matching
    import re
    pattern = r"(A1000020000000000000001 /\* ConfirmationViewModel\.swift in Sources \*/ = \{isa = PBXBuildFile; fileRef = A2000020000000000000001 /\* ConfirmationViewModel\.swift \*/; )\s+(EDB5AD06CF7547388A232826 /\* SkeletonView\.swift in Sources \*/ = \{isa = PBXBuildFile; fileRef = E5D5500A0E3C45398C236E76 /\* SkeletonView\.swift \*/; \};)"
    
    replacement = r"\1};\n\t\t\2"
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        content = new_content
        print("✅ Fixed using regex pattern")
    else:
        print("❌ Could not find pattern to fix")
        exit(1)

# Write back
with open(pbxproj_path, 'w') as f:
    f.write(content)

print("✅ File updated successfully")

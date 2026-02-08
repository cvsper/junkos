#!/usr/bin/env python3
"""Complete fix for project.pbxproj - fix formatting and move files to Sources"""
import re

pbxproj_path = "JunkOS.xcodeproj/project.pbxproj"

# Read
with open(pbxproj_path, 'r') as f:
    content = f.read()

print("Step 1: Fix malformed PBXBuildFile line...")
# Fix the malformed line where ConfirmationViewModel is missing closing brace
old_pattern = r'(A1000020000000000000001 /\* ConfirmationViewModel\.swift in Sources \*/ = \{isa = PBXBuildFile; fileRef = A2000020000000000000001 /\* ConfirmationViewModel\.swift \*/; )\s+(EDB5AD06CF7547388A232826)'

new_replacement = r'\1};\n\t\t\2'

content = re.sub(old_pattern, new_replacement, content)
print("✅ Fixed PBXBuildFile formatting")

print("\nStep 2: Remove Swift files from Resources build phase...")
# Remove the 8 Swift files from Resources
swift_files_in_resources = [
    r'\s+EDB5AD06CF7547388A232826 /\* SkeletonView\.swift in Sources \*/,\n',
    r'\s+EAB4385A705349A3BE29C095 /\* EmptyStateView\.swift in Sources \*/,\n',
    r'\s+A608E6013ABD4F99A431633A /\* ErrorView\.swift in Sources \*/,\n',
    r'\s+D203C1ED3E0E47E3BF472668 /\* ConfettiView\.swift in Sources \*/,\n',
    r'\s+3D29D8304EE74DADB975FA76 /\* OnboardingView\.swift in Sources \*/,\n',
    r'\s+D9CB329E5AF6433CBA580C0C /\* TrustComponents\.swift in Sources \*/,\n',
    r'\s+5D84AD4CF6DB4ABFA6F1C593 /\* ProgressiveDisclosureComponents\.swift in Sources \*/,\n',
    r'\s+0729A757ED1E4F0F8971212D /\* AccessibilityHelpers\.swift in Sources \*/,\n',
]

for pattern in swift_files_in_resources:
    content = re.sub(pattern, '', content)
print("✅ Removed Swift files from Resources")

print("\nStep 3: Add Swift files to Sources build phase...")
# Find the Sources build phase and add the files before the closing
sources_phase_pattern = r'(A1000020000000000000001 /\* ConfirmationViewModel\.swift in Sources \*/,\n)(\s+\);)'

sources_additions = '''				EDB5AD06CF7547388A232826 /* SkeletonView.swift in Sources */,
				EAB4385A705349A3BE29C095 /* EmptyStateView.swift in Sources */,
				A608E6013ABD4F99A431633A /* ErrorView.swift in Sources */,
				D203C1ED3E0E47E3BF472668 /* ConfettiView.swift in Sources */,
				3D29D8304EE74DADB975FA76 /* OnboardingView.swift in Sources */,
				D9CB329E5AF6433CBA580C0C /* TrustComponents.swift in Sources */,
				5D84AD4CF6DB4ABFA6F1C593 /* ProgressiveDisclosureComponents.swift in Sources */,
				0729A757ED1E4F0F8971212D /* AccessibilityHelpers.swift in Sources */,
'''

content = re.sub(sources_phase_pattern, r'\1' + sources_additions + r'\2', content)
print("✅ Added Swift files to Sources")

# Validate
print("\nValidating...")
open_braces = content.count('{')
close_braces = content.count('}')
print(f"  Braces: {open_braces} open, {close_braces} close")

if open_braces == close_braces and content.startswith('// !$*UTF8*$!'):
    print("✅ File structure is valid")
    # Write
    with open(pbxproj_path, 'w') as f:
        f.write(content)
    print("\n🎉 Success! File updated.")
else:
    print("❌ File structure is invalid! Not writing.")
    if open_braces != close_braces:
        print(f"  Brace mismatch: {open_braces} open vs {close_braces} close")
    exit(1)

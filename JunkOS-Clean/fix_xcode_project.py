#!/usr/bin/env python3
"""
Fix Umuve Xcode project by:
1. Moving component files from Resources to Sources build phase
2. Adding proper group structure for Components subdirectories
"""

import re
import sys

def fix_project(pbxproj_path):
    with open(pbxproj_path, 'r') as f:
        content = f.read()
    
    # Files that need to be moved from Resources to Sources
    files_to_move = [
        'SkeletonView.swift',
        'EmptyStateView.swift', 
        'ErrorView.swift',
        'ConfettiView.swift',
        'OnboardingView.swift',
        'TrustComponents.swift',
        'ProgressiveDisclosureComponents.swift',
        'AccessibilityHelpers.swift'
    ]
    
    # Step 1: Find the Resources build phase section
    resources_section_match = re.search(
        r'(/\* Begin PBXResourcesBuildPhase section \*/.*?)/\* End PBXResourcesBuildPhase section \*/',
        content,
        re.DOTALL
    )
    
    if not resources_section_match:
        print("ERROR: Could not find Resources build phase section")
        return False
        
    resources_section = resources_section_match.group(1)
    
    # Step 2: Extract the lines for our files from Resources
    lines_to_move = []
    for filename in files_to_move:
        pattern = rf'(\s+\w+ /\* {re.escape(filename)} in Sources \*/,)\n'
        match = re.search(pattern, resources_section)
        if match:
            lines_to_move.append(match.group(1))
            # Remove from resources section
            resources_section = resources_section.replace(match.group(0), '')
    
    # Rebuild the resources section
    new_resources_section = resources_section.replace(
        'A1000014000000000000001 /* Assets.xcassets in Resources */,',
        'A1000014000000000000001 /* Assets.xcassets in Resources */,'
    )
    
    # Step 3: Find the Sources build phase section
    sources_section_match = re.search(
        r'(/\* Begin PBXSourcesBuildPhase section \*/.*?)(\s+\);)',
        content,
        re.DOTALL
    )
    
    if not sources_section_match:
        print("ERROR: Could not find Sources build phase section")
        return False
    
    sources_section = sources_section_match.group(1)
    sources_end = sources_section_match.group(2)
    
    # Step 4: Add our files to Sources (before the closing)
    new_sources_section = sources_section
    for line in lines_to_move:
        if line not in sources_section:
            new_sources_section += '\n\t\t\t\t' + line.strip()
    
    # Step 5: Rebuild the full content
    content = content.replace(
        resources_section_match.group(0),
        new_resources_section + '/* End PBXResourcesBuildPhase section */'
    )
    
    content = content.replace(
        sources_section_match.group(0),
        new_sources_section + sources_end
    )
    
    # Step 6: Add Components group structure
    # Find the Utilities group
    utilities_group_match = re.search(
        r'(A5000007000000000000001 /\* Utilities \*/ = \{.*?\};)',
        content,
        re.DOTALL
    )
    
    if utilities_group_match:
        # Add AccessibilityHelpers.swift to Utilities group
        utilities_group = utilities_group_match.group(1)
        if '2EF7094708704F9B99725F9F' not in utilities_group:
            utilities_group = utilities_group.replace(
                'A2000006000000000000001 /* LocationManager.swift */,',
                'A2000006000000000000001 /* LocationManager.swift */,\n\t\t\t\t2EF7094708704F9B99725F9F /* AccessibilityHelpers.swift */,'
            )
            content = content.replace(utilities_group_match.group(1), utilities_group)
    
    # Step 7: Add Components group if it doesn't exist
    if 'Components */' not in content:
        # Find where to insert the Components group (after ViewModels)
        viewmodels_group_match = re.search(
            r'(A5000008000000000000001 /\* ViewModels \*/ = \{.*?\};)',
            content,
            re.DOTALL
        )
        
        if viewmodels_group_match:
            components_group = '''
\t\tA5000009000000000000001 /* Components */ = {
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t35ED0C8A011D45B3AE5E04FF /* ProgressiveDisclosureComponents.swift */,
\t\t\t\t4F363430F0D04B2A8FA3572D /* TrustComponents.swift */,
\t\t\t\tA5000010000000000000001 /* ErrorHandling */,
\t\t\t\tA5000011000000000000001 /* LoadingStates */,
\t\t\t\tA5000012000000000000001 /* EmptyStates */,
\t\t\t\tA5000013000000000000001 /* Animations */,
\t\t\t\tA5000014000000000000001 /* Onboarding */,
\t\t\t);
\t\t\tpath = Components;
\t\t\tsourceTree = "<group>";
\t\t};
\t\tA5000010000000000000001 /* ErrorHandling */ = {
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t91F81FB42D2144C88FE03D6A /* ErrorView.swift */,
\t\t\t);
\t\t\tpath = ErrorHandling;
\t\t\tsourceTree = "<group>";
\t\t};
\t\tA5000011000000000000001 /* LoadingStates */ = {
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\tE5D5500A0E3C45398C236E76 /* SkeletonView.swift */,
\t\t\t);
\t\t\tpath = LoadingStates;
\t\t\tsourceTree = "<group>";
\t\t};
\t\tA5000012000000000000001 /* EmptyStates */ = {
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\tCF416FA2DC8B449299A24A93 /* EmptyStateView.swift */,
\t\t\t);
\t\t\tpath = EmptyStates;
\t\t\tsourceTree = "<group>";
\t\t};
\t\tA5000013000000000000001 /* Animations */ = {
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\tB609AF1DD8A94ADE952E4546 /* ConfettiView.swift */,
\t\t\t);
\t\t\tpath = Animations;
\t\t\tsourceTree = "<group>";
\t\t};
\t\tA5000014000000000000001 /* Onboarding */ = {
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t5B2C4238B45E417FA833C56F /* OnboardingView.swift */,
\t\t\t);
\t\t\tpath = Onboarding;
\t\t\tsourceTree = "<group>";
\t\t};'''
            
            content = content.replace(
                viewmodels_group_match.group(0),
                viewmodels_group_match.group(0) + components_group
            )
            
            # Add Components group reference to main JunkOS group
            junkos_group_match = re.search(
                r'(A5000002000000000000001 /\* JunkOS \*/ = \{.*?children = \(.*?)(A5000004000000000000001)',
                content,
                re.DOTALL
            )
            if junkos_group_match:
                content = content.replace(
                    junkos_group_match.group(0),
                    junkos_group_match.group(1) + 'A5000009000000000000001 /* Components */,\n\t\t\t\t' + junkos_group_match.group(2)
                )
    
    # Write the fixed content
    with open(pbxproj_path, 'w') as f:
        f.write(content)
    
    print("✅ Successfully fixed project.pbxproj")
    return True

if __name__ == '__main__':
    pbxproj_path = sys.argv[1] if len(sys.argv) > 1 else 'JunkOS.xcodeproj/project.pbxproj'
    if fix_project(pbxproj_path):
        sys.exit(0)
    else:
        sys.exit(1)

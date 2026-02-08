#!/usr/bin/env python3
"""Move Swift files from Resources to Sources build phase"""

pbxproj_path = "JunkOS.xcodeproj/project.pbxproj"

# Read the file
with open(pbxproj_path, 'r') as f:
    lines = f.readlines()

# Component file IDs that need to be moved
component_ids = [
    'EDB5AD06CF7547388A232826',  # SkeletonView.swift
    'EAB4385A705349A3BE29C095',  # EmptyStateView.swift
    'A608E6013ABD4F99A431633A',  # ErrorView.swift
    'D203C1ED3E0E47E3BF472668',  # ConfettiView.swift
    '3D29D8304EE74DADB975FA76',  # OnboardingView.swift
    'D9CB329E5AF6433CBA580C0C',  # TrustComponents.swift
    '5D84AD4CF6DB4ABFA6F1C593',  # ProgressiveDisclosureComponents.swift
    '0729A757ED1E4F0F8971212D',  # AccessibilityHelpers.swift
]

# Track which section we're in
in_resources = False
in_sources = False
resources_start = -1
sources_end = -1

# Find the sections and collect lines to move
lines_to_add_to_sources = []
lines_to_remove_from_resources = []

for i, line in enumerate(lines):
    if '/* Begin PBXResourcesBuildPhase section */' in line:
        in_resources = True
        resources_start = i
    elif '/* End PBXResourcesBuildPhase section */' in line:
        in_resources = False
    elif '/* Begin PBXSourcesBuildPhase section */' in line:
        in_sources = True
    elif '/* End PBXSourcesBuildPhase section */' in line:
        sources_end = i
        in_sources = False
    elif in_resources:
        # Check if this line references one of our component files
        for comp_id in component_ids:
            if comp_id in line:
                lines_to_remove_from_resources.append(i)
                lines_to_add_to_sources.append(line)
                break
    elif in_sources and any(comp_id in line for comp_id in component_ids):
        # Already in sources, don't add again
        comp_id_in_line = [cid for cid in component_ids if cid in line][0]
        if comp_id_in_line in [l for l in lines_to_add_to_sources for cid in component_ids if cid in l]:
            lines_to_add_to_sources = [l for l in lines_to_add_to_sources if comp_id_in_line not in l]

# Remove duplicates from resources
for i in sorted(lines_to_remove_from_resources, reverse=True):
    del lines[i]
    # Adjust sources_end if it's after this deletion
    if i < sources_end:
        sources_end -= 1

# Add to sources if not already there
if lines_to_add_to_sources:
    # Insert before the closing of Sources build phase
    for line in reversed(lines_to_add_to_sources):
        lines.insert(sources_end, line)

# Write back
with open(pbxproj_path, 'w') as f:
    f.writelines(lines)

print(f"✅ Moved {len(lines_to_remove_from_resources)} files from Resources to Sources")
print(f"✅ Added {len(lines_to_add_to_sources)} new entries to Sources")

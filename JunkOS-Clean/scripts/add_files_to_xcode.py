#!/usr/bin/env python3
"""
Script to add new Swift files to Xcode project
"""
import os
import uuid
import re

project_file = '../JunkOS.xcodeproj/project.pbxproj'

# Files to add with their groups
files_to_add = [
    ('JunkOS/Components/LoadingStates/SkeletonView.swift', 'Components/LoadingStates'),
    ('JunkOS/Components/EmptyStates/EmptyStateView.swift', 'Components/EmptyStates'),
    ('JunkOS/Components/ErrorHandling/ErrorView.swift', 'Components/ErrorHandling'),
    ('JunkOS/Components/Animations/ConfettiView.swift', 'Components/Animations'),
    ('JunkOS/Components/Onboarding/OnboardingView.swift', 'Components/Onboarding'),
    ('JunkOS/Components/TrustComponents.swift', 'Components'),
    ('JunkOS/Components/ProgressiveDisclosureComponents.swift', 'Components'),
    ('JunkOS/Utilities/AccessibilityHelpers.swift', 'Utilities'),
]

def generate_uuid():
    """Generate a 24-character UUID for Xcode"""
    return uuid.uuid4().hex[:24].upper()

def add_files_to_project():
    """Add files to Xcode project.pbxproj"""
    
    with open(project_file, 'r') as f:
        content = f.read()
    
    # Find the PBXBuildFile section
    build_file_section = re.search(r'/\* Begin PBXBuildFile section \*/(.*?)/\* End PBXBuildFile section \*/', content, re.DOTALL)
    
    # Find the PBXFileReference section
    file_ref_section = re.search(r'/\* Begin PBXFileReference section \*/(.*?)/\* End PBXFileReference section \*/', content, re.DOTALL)
    
    # Find the PBXGroup section for adding to groups
    group_section = re.search(r'/\* Begin PBXGroup section \*/(.*?)/\* End PBXGroup section \*/', content, re.DOTALL)
    
    # Find the PBXSourcesBuildPhase section
    sources_section = re.search(r'/\* Begin PBXSourcesBuildPhase section \*/(.*?)/\* End PBXSourcesBuildPhase section \*/', content, re.DOTALL)
    
    new_build_files = []
    new_file_refs = []
    new_source_refs = []
    
    for file_path, group_name in files_to_add:
        # Check if file already exists
        filename = os.path.basename(file_path)
        if filename in content:
            print(f"⚠️  {filename} already exists in project")
            continue
            
        print(f"➕ Adding {filename}...")
        
        # Generate UUIDs
        build_file_uuid = generate_uuid()
        file_ref_uuid = generate_uuid()
        
        # Create build file entry
        build_file_entry = f"\t\t{build_file_uuid} /* {filename} in Sources */ = {{isa = PBXBuildFile; fileRef = {file_ref_uuid} /* {filename} */; }};\n"
        new_build_files.append(build_file_entry)
        
        # Create file reference entry
        file_ref_entry = f"\t\t{file_ref_uuid} /* {filename} */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = {filename}; sourceTree = \"<group>\"; }};\n"
        new_file_refs.append(file_ref_entry)
        
        # Create source build phase entry
        source_entry = f"\t\t\t\t{build_file_uuid} /* {filename} in Sources */,\n"
        new_source_refs.append(source_entry)
    
    if not new_build_files:
        print("✅ All files already exist in project!")
        return
    
    # Insert new entries
    # Add build files
    build_file_insert_pos = build_file_section.end() - len('/* End PBXBuildFile section */') - 3
    content = content[:build_file_insert_pos] + ''.join(new_build_files) + content[build_file_insert_pos:]
    
    # Add file references
    file_ref_insert_pos = content.find('/* End PBXFileReference section */')
    content = content[:file_ref_insert_pos] + ''.join(new_file_refs) + content[file_ref_insert_pos:]
    
    # Add to sources build phase
    sources_insert_pos = content.find('files = (', sources_section.start()) + len('files = (\n')
    content = content[:sources_insert_pos] + ''.join(new_source_refs) + content[sources_insert_pos:]
    
    # Write back
    with open(project_file, 'w') as f:
        f.write(content)
    
    print(f"\n✅ Successfully added {len(new_build_files)} new files to Xcode project!")
    print("\n⚠️  Note: You may need to manually organize files into groups in Xcode.")
    print("   Open Xcode and drag files to the correct folders in the Project Navigator.")

if __name__ == '__main__':
    try:
        add_files_to_project()
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Alternative: Open Xcode and manually add files:")
        print("   1. Right-click on the JunkOS folder")
        print("   2. Choose 'Add Files to JunkOS...'")
        print("   3. Select the new files in JunkOS/Components/")
        print("   4. Make sure 'Copy items if needed' is unchecked")
        print("   5. Make sure 'JunkOS' target is selected")

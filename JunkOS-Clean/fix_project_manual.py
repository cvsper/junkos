#!/usr/bin/env python3
"""
Manually add Services and APIModels files to Xcode project
"""
import os
import uuid
import re

def generate_id():
    """Generate a 24-character hex ID like Xcode uses"""
    return ''.join([format(x, '02X') for x in os.urandom(12)])

def main():
    project_path = "JunkOS.xcodeproj/project.pbxproj"
    
    # Read the project file
    with open(project_path, 'r') as f:
        content = f.read()
    
    # Generate IDs for new files
    apimodels_ref_id = generate_id()
    apimodels_build_id = generate_id()
    apiclient_ref_id = generate_id()
    apiclient_build_id = generate_id()
    config_ref_id = generate_id()
    config_build_id = generate_id()
    
    # Find the Models group (where BookingModels.swift is)
    models_group_match = re.search(r'/\* Models \*/ = \{[^}]+children = \([^)]+\);', content, re.DOTALL)
    
    if models_group_match:
        models_section = models_group_match.group(0)
        # Add APIModels.swift to Models group
        new_models = models_section.replace(
            'children = (',
            f'children = (\n\t\t\t\t{apimodels_ref_id} /* APIModels.swift */,'
        )
        content = content.replace(models_section, new_models)
        print("✓ Added APIModels.swift to Models group")
    
    # Find PBXBuildFile section and add our files
    build_file_section = re.search(r'/\* Begin PBXBuildFile section \*/.*?/\* End PBXBuildFile section \*/', content, re.DOTALL)
    if build_file_section:
        section_text = build_file_section.group(0)
        new_entries = f"""\t\t{apimodels_build_id} /* APIModels.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {apimodels_ref_id} /* APIModels.swift */; }};
\t\t{apiclient_build_id} /* APIClient.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {apiclient_ref_id} /* APIClient.swift */; }};
\t\t{config_build_id} /* Config.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {config_ref_id} /* Config.swift */; }};
/* End PBXBuildFile section */"""
        content = content.replace('/* End PBXBuildFile section */', new_entries)
        print("✓ Added build file entries")
    
    # Find PBXFileReference section and add our files
    file_ref_section = re.search(r'/\* Begin PBXFileReference section \*/.*?/\* End PBXFileReference section \*/', content, re.DOTALL)
    if file_ref_section:
        new_refs = f"""\t\t{apimodels_ref_id} /* APIModels.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = APIModels.swift; sourceTree = "<group>"; }};
\t\t{apiclient_ref_id} /* APIClient.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = APIClient.swift; sourceTree = "<group>"; }};
\t\t{config_ref_id} /* Config.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = Config.swift; sourceTree = "<group>"; }};
/* End PBXFileReference section */"""
        content = content.replace('/* End PBXFileReference section */', new_refs)
        print("✓ Added file reference entries")
    
    # Find the PBXSourcesBuildPhase and add our build files
    sources_phase = re.search(r'isa = PBXSourcesBuildPhase;[^}]+files = \([^)]+\);', content, re.DOTALL)
    if sources_phase:
        phase_text = sources_phase.group(0)
        new_phase = phase_text.replace(
            'files = (',
            f'files = (\n\t\t\t\t{apimodels_build_id} /* APIModels.swift in Sources */,\n\t\t\t\t{apiclient_build_id} /* APIClient.swift in Sources */,\n\t\t\t\t{config_build_id} /* Config.swift in Sources */,'
        )
        content = content.replace(phase_text, new_phase)
        print("✓ Added to sources build phase")
    
    # Backup and save
    os.rename(project_path, project_path + '.backup')
    with open(project_path, 'w') as f:
        f.write(content)
    
    print(f"\n✓ Done! Project file updated.")
    print(f"  Backup saved as: {project_path}.backup")

if __name__ == "__main__":
    main()

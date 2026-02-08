#!/usr/bin/env python3
"""
Add Services and APIModels files to Xcode project with correct paths
"""
import os
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
    services_group_id = generate_id()
    
    # Find the JunkOS group's children list (main app group)
    junkos_group_match = re.search(r'([A-F0-9]{24}) /\* JunkOS \*/ = \{[^}]+isa = PBXGroup;[^}]+children = \(([^)]+)\);[^}]+path = JunkOS;', content, re.DOTALL)
    
    if junkos_group_match:
        group_id = junkos_group_match.group(1)
        children_list = junkos_group_match.group(2)
        
        # Add Services group to JunkOS group if not already there
        if services_group_id not in children_list:
            new_children = children_list.rstrip() + f'\n\t\t\t\t{services_group_id} /* Services */,'
            content = content.replace(
                f'children = ({children_list})',
                f'children = ({new_children}\n\t\t\t)',
                1
            )
            print("✓ Added Services group to JunkOS group")
    
    # Create Services group
    services_group = f"""\t\t{services_group_id} /* Services */ = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t{apiclient_ref_id} /* APIClient.swift */,
\t\t\t\t{config_ref_id} /* Config.swift */,
\t\t\t);
\t\t\tpath = Services;
\t\t\tsourceTree = "<group>";
\t\t}};
"""
    
    # Find Models group and add APIModels
    models_group_match = re.search(r'([A-F0-9]{24}) /\* Models \*/ = \{[^}]+children = \(([^)]+)\);', content, re.DOTALL)
    if models_group_match:
        models_group_id = models_group_match.group(1)
        models_children = models_group_match.group(2)
        new_models_children = models_children.rstrip() + f'\n\t\t\t\t{apimodels_ref_id} /* APIModels.swift */,'
        
        old_models_def = f'children = ({models_children})'
        new_models_def = f'children = ({new_models_children}\n\t\t\t)'
        content = content.replace(old_models_def, new_models_def, 1)
        print("✓ Added APIModels.swift to Models group")
    
    # Add Services group definition before End PBXGroup section
    content = content.replace(
        '/* End PBXGroup section */',
        services_group + '\t/* End PBXGroup section */'
    )
    print("✓ Added Services group definition")
    
    # Add PBXBuildFile entries
    build_file_entries = f"""\t\t{apimodels_build_id} /* APIModels.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {apimodels_ref_id} /* APIModels.swift */; }};
\t\t{apiclient_build_id} /* APIClient.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {apiclient_ref_id} /* APIClient.swift */; }};
\t\t{config_build_id} /* Config.swift in Sources */ = {{isa = PBXBuildFile; fileRef = {config_ref_id} /* Config.swift */; }};
"""
    content = content.replace(
        '/* End PBXBuildFile section */',
        build_file_entries + '\t/* End PBXBuildFile section */'
    )
    print("✓ Added build file entries")
    
    # Add PBXFileReference entries with correct paths
    file_ref_entries = f"""\t\t{apimodels_ref_id} /* APIModels.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = APIModels.swift; sourceTree = "<group>"; }};
\t\t{apiclient_ref_id} /* APIClient.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = APIClient.swift; sourceTree = "<group>"; }};
\t\t{config_ref_id} /* Config.swift */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = Config.swift; sourceTree = "<group>"; }};
"""
    content = content.replace(
        '/* End PBXFileReference section */',
        file_ref_entries + '\t/* End PBXFileReference section */'
    )
    print("✓ Added file reference entries")
    
    # Add to PBXSourcesBuildPhase
    sources_phase_match = re.search(r'(isa = PBXSourcesBuildPhase;[^}]+files = \()([^)]+)\);', content, re.DOTALL)
    if sources_phase_match:
        prefix = sources_phase_match.group(1)
        files_list = sources_phase_match.group(2)
        new_files = files_list.rstrip() + f'\n\t\t\t\t{apimodels_build_id} /* APIModels.swift in Sources */,\n\t\t\t\t{apiclient_build_id} /* APIClient.swift in Sources */,\n\t\t\t\t{config_build_id} /* Config.swift in Sources */,'
        
        old_phase = f'{prefix}{files_list});'
        new_phase = f'{prefix}{new_files}\n\t\t\t);'
        content = content.replace(old_phase, new_phase, 1)
        print("✓ Added to sources build phase")
    
    # Backup and save
    os.rename(project_path, project_path + '.backup')
    with open(project_path, 'w') as f:
        f.write(content)
    
    print(f"\n✓ Done! Project file updated.")
    print(f"  Backup saved as: {project_path}.backup")

if __name__ == "__main__":
    main()

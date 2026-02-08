#!/usr/bin/env python3
"""
Script to add JunkOSTests and JunkOSUITests targets to the Xcode project
"""

import re
import uuid

def generate_uuid():
    """Generate a unique 24-character hex ID for Xcode"""
    return uuid.uuid4().hex[:24].upper()

def add_test_targets_to_project(project_path):
    """Add test targets to project.pbxproj"""
    
    with open(project_path, 'r') as f:
        content = f.read()
    
    # Generate UUIDs for test targets and files
    tests_target_id = generate_uuid()
    tests_product_id = generate_uuid()
    tests_build_phase_sources_id = generate_uuid()
    tests_build_phase_frameworks_id = generate_uuid()
    tests_build_phase_resources_id = generate_uuid()
    tests_build_config_debug_id = generate_uuid()
    tests_build_config_release_id = generate_uuid()
    tests_build_config_list_id = generate_uuid()
    tests_dependency_id = generate_uuid()
    tests_target_dependency_id = generate_uuid()
    
    uitests_target_id = generate_uuid()
    uitests_product_id = generate_uuid()
    uitests_build_phase_sources_id = generate_uuid()
    uitests_build_phase_frameworks_id = generate_uuid()
    uitests_build_phase_resources_id = generate_uuid()
    uitests_build_config_debug_id = generate_uuid()
    uitests_build_config_release_id = generate_uuid()
    uitests_build_config_list_id = generate_uuid()
    uitests_dependency_id = generate_uuid()
    uitests_target_dependency_id = generate_uuid()
    
    # Test file UUIDs
    test_files = {
        'MockAPIClient.swift': (generate_uuid(), generate_uuid()),
        'MockLocationManager.swift': (generate_uuid(), generate_uuid()),
        'TestFixtures.swift': (generate_uuid(), generate_uuid()),
        'TestHelpers.swift': (generate_uuid(), generate_uuid()),
        'AddressInputViewModelTests.swift': (generate_uuid(), generate_uuid()),
        'ServiceSelectionViewModelTests.swift': (generate_uuid(), generate_uuid()),
        'DateTimePickerViewModelTests.swift': (generate_uuid(), generate_uuid()),
        'PhotoUploadViewModelTests.swift': (generate_uuid(), generate_uuid()),
        'ConfirmationViewModelTests.swift': (generate_uuid(), generate_uuid()),
    }
    
    ui_test_files = {
        'BookingFlowUITests.swift': (generate_uuid(), generate_uuid()),
        'NavigationUITests.swift': (generate_uuid(), generate_uuid()),
        'FormValidationUITests.swift': (generate_uuid(), generate_uuid()),
    }
    
    # Find the main app target ID
    main_target_match = re.search(r'([A-F0-9]{24}) \/\* JunkOS \*\/ = \{[^}]*isa = PBXNativeTarget', content)
    if not main_target_match:
        print("Error: Could not find main JunkOS target")
        return False
    main_target_id = main_target_match.group(1)
    
    # Add PBXBuildFile entries for test files
    build_file_section = content.find('/* Begin PBXBuildFile section */')
    if build_file_section == -1:
        print("Error: Could not find PBXBuildFile section")
        return False
    
    build_file_end = content.find('/* End PBXBuildFile section */', build_file_section)
    
    test_build_files = []
    for filename, (file_ref_id, build_file_id) in test_files.items():
        test_build_files.append(f"\t\t{build_file_id} /* {filename} in Sources */ = {{isa = PBXBuildFile; fileRef = {file_ref_id} /* {filename} */; }};\n")
    
    for filename, (file_ref_id, build_file_id) in ui_test_files.items():
        test_build_files.append(f"\t\t{build_file_id} /* {filename} in Sources */ = {{isa = PBXBuildFile; fileRef = {file_ref_id} /* {filename} */; }};\n")
    
    content = content[:build_file_end] + ''.join(test_build_files) + content[build_file_end:]
    
    # Add PBXFileReference entries
    file_ref_section = content.find('/* Begin PBXFileReference section */')
    file_ref_end = content.find('/* End PBXFileReference section */', file_ref_section)
    
    test_file_refs = []
    test_file_refs.append(f"\t\t{tests_product_id} /* JunkOSTests.xctest */ = {{isa = PBXFileReference; explicitFileType = wrapper.cfbundle; includeInIndex = 0; path = JunkOSTests.xctest; sourceTree = BUILT_PRODUCTS_DIR; }};\n")
    test_file_refs.append(f"\t\t{uitests_product_id} /* JunkOSUITests.xctest */ = {{isa = PBXFileReference; explicitFileType = wrapper.cfbundle; includeInIndex = 0; path = JunkOSUITests.xctest; sourceTree = BUILT_PRODUCTS_DIR; }};\n")
    
    for filename, (file_ref_id, _) in test_files.items():
        test_file_refs.append(f"\t\t{file_ref_id} /* {filename} */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = {filename}; sourceTree = \"<group>\"; }};\n")
    
    for filename, (file_ref_id, _) in ui_test_files.items():
        test_file_refs.append(f"\t\t{file_ref_id} /* {filename} */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = {filename}; sourceTree = \"<group>\"; }};\n")
    
    content = content[:file_ref_end] + ''.join(test_file_refs) + content[file_ref_end:]
    
    # Add PBXFrameworksBuildPhase entries
    frameworks_section = content.find('/* End PBXFrameworksBuildPhase section */')
    
    frameworks_entries = f"""
\t\t{tests_build_phase_frameworks_id} /* Frameworks */ = {{
\t\t\tisa = PBXFrameworksBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
\t\t{uitests_build_phase_frameworks_id} /* Frameworks */ = {{
\t\t\tisa = PBXFrameworksBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
"""
    content = content[:frameworks_section] + frameworks_entries + content[frameworks_section:]
    
    # Add PBXGroup entries
    group_section = content.find('/* End PBXGroup section */')
    
    # Create group IDs
    tests_group_id = generate_uuid()
    tests_mocks_group_id = generate_uuid()
    tests_utilities_group_id = generate_uuid()
    tests_viewmodels_group_id = generate_uuid()
    uitests_group_id = generate_uuid()
    uitests_tests_group_id = generate_uuid()
    
    groups_entries = f"""
\t\t{tests_group_id} /* JunkOSTests */ = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t{tests_mocks_group_id} /* Mocks */,
\t\t\t\t{tests_utilities_group_id} /* Utilities */,
\t\t\t\t{tests_viewmodels_group_id} /* ViewModels */,
\t\t\t);
\t\t\tpath = JunkOSTests;
\t\t\tsourceTree = \"<group>\";
\t\t}};
\t\t{tests_mocks_group_id} /* Mocks */ = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t{test_files['MockAPIClient.swift'][0]} /* MockAPIClient.swift */,
\t\t\t\t{test_files['MockLocationManager.swift'][0]} /* MockLocationManager.swift */,
\t\t\t);
\t\t\tpath = Mocks;
\t\t\tsourceTree = \"<group>\";
\t\t}};
\t\t{tests_utilities_group_id} /* Utilities */ = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t{test_files['TestFixtures.swift'][0]} /* TestFixtures.swift */,
\t\t\t\t{test_files['TestHelpers.swift'][0]} /* TestHelpers.swift */,
\t\t\t);
\t\t\tpath = Utilities;
\t\t\tsourceTree = \"<group>\";
\t\t}};
\t\t{tests_viewmodels_group_id} /* ViewModels */ = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t{test_files['AddressInputViewModelTests.swift'][0]} /* AddressInputViewModelTests.swift */,
\t\t\t\t{test_files['ServiceSelectionViewModelTests.swift'][0]} /* ServiceSelectionViewModelTests.swift */,
\t\t\t\t{test_files['DateTimePickerViewModelTests.swift'][0]} /* DateTimePickerViewModelTests.swift */,
\t\t\t\t{test_files['PhotoUploadViewModelTests.swift'][0]} /* PhotoUploadViewModelTests.swift */,
\t\t\t\t{test_files['ConfirmationViewModelTests.swift'][0]} /* ConfirmationViewModelTests.swift */,
\t\t\t);
\t\t\tpath = ViewModels;
\t\t\tsourceTree = \"<group>\";
\t\t}};
\t\t{uitests_group_id} /* JunkOSUITests */ = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t{uitests_tests_group_id} /* Tests */,
\t\t\t);
\t\t\tpath = JunkOSUITests;
\t\t\tsourceTree = \"<group>\";
\t\t}};
\t\t{uitests_tests_group_id} /* Tests */ = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t{ui_test_files['BookingFlowUITests.swift'][0]} /* BookingFlowUITests.swift */,
\t\t\t\t{ui_test_files['NavigationUITests.swift'][0]} /* NavigationUITests.swift */,
\t\t\t\t{ui_test_files['FormValidationUITests.swift'][0]} /* FormValidationUITests.swift */,
\t\t\t);
\t\t\tpath = Tests;
\t\t\tsourceTree = \"<group>\";
\t\t}};
"""
    content = content[:group_section] + groups_entries + content[group_section:]
    
    # Add test groups to root group (find Products group and add after JunkOS)
    root_group_match = re.search(r'(D0000001) = \{[^}]*isa = PBXGroup;[^}]*children = \([^)]*\)', content)
    if root_group_match:
        root_group_section = root_group_match.group(0)
        # Add test groups after JunkOS group
        new_root_group = root_group_section.replace(
            'D0000003 /* Products */',
            f'{tests_group_id} /* JunkOSTests */,\n\t\t\t\t{uitests_group_id} /* JunkOSUITests */,\n\t\t\t\tD0000003 /* Products */'
        )
        content = content.replace(root_group_section, new_root_group)
    
    # Add test products to Products group
    products_group_match = re.search(r'(D0000003 \/\* Products \*\/) = \{[^}]*children = \([^)]*\)', content)
    if products_group_match:
        products_section = products_group_match.group(0)
        new_products = products_section.replace(
            ');',
            f',\n\t\t\t\t{tests_product_id} /* JunkOSTests.xctest */,\n\t\t\t\t{uitests_product_id} /* JunkOSUITests.xctest */\n\t\t\t);'
        )
        content = content.replace(products_section, new_products)
    
    # Add PBXNativeTarget entries
    native_target_section = content.find('/* End PBXNativeTarget section */')
    
    # Build source files list for tests
    test_source_files = '\n'.join([f"\t\t\t\t{build_file_id} /* {filename} in Sources */," for filename, (_, build_file_id) in test_files.items()])
    ui_test_source_files = '\n'.join([f"\t\t\t\t{build_file_id} /* {filename} in Sources */," for filename, (_, build_file_id) in ui_test_files.items()])
    
    native_targets = f"""
\t\t{tests_target_id} /* JunkOSTests */ = {{
\t\t\tisa = PBXNativeTarget;
\t\t\tbuildConfigurationList = {tests_build_config_list_id} /* Build configuration list for PBXNativeTarget "JunkOSTests" */;
\t\t\tbuildPhases = (
\t\t\t\t{tests_build_phase_sources_id} /* Sources */,
\t\t\t\t{tests_build_phase_frameworks_id} /* Frameworks */,
\t\t\t\t{tests_build_phase_resources_id} /* Resources */,
\t\t\t);
\t\t\tbuildRules = (
\t\t\t);
\t\t\tdependencies = (
\t\t\t\t{tests_target_dependency_id} /* PBXTargetDependency */,
\t\t\t);
\t\t\tname = JunkOSTests;
\t\t\tproductName = JunkOSTests;
\t\t\tproductReference = {tests_product_id} /* JunkOSTests.xctest */;
\t\t\tproductType = "com.apple.product-type.bundle.unit-test";
\t\t}};
\t\t{uitests_target_id} /* JunkOSUITests */ = {{
\t\t\tisa = PBXNativeTarget;
\t\t\tbuildConfigurationList = {uitests_build_config_list_id} /* Build configuration list for PBXNativeTarget "JunkOSUITests" */;
\t\t\tbuildPhases = (
\t\t\t\t{uitests_build_phase_sources_id} /* Sources */,
\t\t\t\t{uitests_build_phase_frameworks_id} /* Frameworks */,
\t\t\t\t{uitests_build_phase_resources_id} /* Resources */,
\t\t\t);
\t\t\tbuildRules = (
\t\t\t);
\t\t\tdependencies = (
\t\t\t\t{uitests_target_dependency_id} /* PBXTargetDependency */,
\t\t\t);
\t\t\tname = JunkOSUITests;
\t\t\tproductName = JunkOSUITests;
\t\t\tproductReference = {uitests_product_id} /* JunkOSUITests.xctest */;
\t\t\tproductType = "com.apple.product-type.bundle.ui-testing";
\t\t}};
"""
    content = content[:native_target_section] + native_targets + content[native_target_section:]
    
    # Add PBXProject target references
    project_section_match = re.search(r'(E0000001 \/\* Project object \*\/) = \{[^}]*targets = \([^)]*\)', content)
    if project_section_match:
        project_targets = project_section_match.group(0)
        new_targets = project_targets.replace(
            ');',
            f',\n\t\t\t\t{tests_target_id} /* JunkOSTests */,\n\t\t\t\t{uitests_target_id} /* JunkOSUITests */\n\t\t\t);'
        )
        content = content.replace(project_targets, new_targets)
    
    # Add PBXResourcesBuildPhase
    resources_section = content.find('/* End PBXResourcesBuildPhase section */')
    if resources_section == -1:
        # Create section if it doesn't exist
        frameworks_end = content.find('/* End PBXFrameworksBuildPhase section */')
        resources_entries = f"""
/* Begin PBXResourcesBuildPhase section */
\t\t{tests_build_phase_resources_id} /* Resources */ = {{
\t\t\tisa = PBXResourcesBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
\t\t{uitests_build_phase_resources_id} /* Resources */ = {{
\t\t\tisa = PBXResourcesBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
/* End PBXResourcesBuildPhase section */
"""
        content = content[:frameworks_end] + '\n' + content[frameworks_end:frameworks_end] + resources_entries + content[frameworks_end:]
    else:
        resources_entries = f"""
\t\t{tests_build_phase_resources_id} /* Resources */ = {{
\t\t\tisa = PBXResourcesBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
\t\t{uitests_build_phase_resources_id} /* Resources */ = {{
\t\t\tisa = PBXResourcesBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
"""
        content = content[:resources_section] + resources_entries + content[resources_section:]
    
    # Add PBXSourcesBuildPhase
    sources_section = content.find('/* End PBXSourcesBuildPhase section */')
    
    sources_entries = f"""
\t\t{tests_build_phase_sources_id} /* Sources */ = {{
\t\t\tisa = PBXSourcesBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
{test_source_files}
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
\t\t{uitests_build_phase_sources_id} /* Sources */ = {{
\t\t\tisa = PBXSourcesBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
{ui_test_source_files}
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
"""
    content = content[:sources_section] + sources_entries + content[sources_section:]
    
    # Add PBXTargetDependency
    if '/* Begin PBXTargetDependency section */' not in content:
        # Add section after PBXSourcesBuildPhase
        sources_end = content.find('/* End PBXSourcesBuildPhase section */')
        dependency_section = f"""

/* Begin PBXTargetDependency section */
\t\t{tests_target_dependency_id} /* PBXTargetDependency */ = {{
\t\t\tisa = PBXTargetDependency;
\t\t\ttarget = {main_target_id} /* JunkOS */;
\t\t\ttargetProxy = {tests_dependency_id} /* PBXContainerItemProxy */;
\t\t}};
\t\t{uitests_target_dependency_id} /* PBXTargetDependency */ = {{
\t\t\tisa = PBXTargetDependency;
\t\t\ttarget = {main_target_id} /* JunkOS */;
\t\t\ttargetProxy = {uitests_dependency_id} /* PBXContainerItemProxy */;
\t\t}};
/* End PBXTargetDependency section */
"""
        insert_pos = content.find('\n', sources_end) + 1
        content = content[:insert_pos] + dependency_section + content[insert_pos:]
    
    # Add PBXContainerItemProxy
    if '/* Begin PBXContainerItemProxy section */' not in content:
        # Add section before PBXFileReference
        file_ref_start = content.find('/* Begin PBXFileReference section */')
        container_proxy_section = f"""/* Begin PBXContainerItemProxy section */
\t\t{tests_dependency_id} /* PBXContainerItemProxy */ = {{
\t\t\tisa = PBXContainerItemProxy;
\t\t\tcontainerPortal = E0000001 /* Project object */;
\t\t\tproxyType = 1;
\t\t\tremoteGlobalIDString = {main_target_id};
\t\t\tremoteInfo = JunkOS;
\t\t}};
\t\t{uitests_dependency_id} /* PBXContainerItemProxy */ = {{
\t\t\tisa = PBXContainerItemProxy;
\t\t\tcontainerPortal = E0000001 /* Project object */;
\t\t\tproxyType = 1;
\t\t\tremoteGlobalIDString = {main_target_id};
\t\t\tremoteInfo = JunkOS;
\t\t}};
/* End PBXContainerItemProxy section */

"""
        content = content[:file_ref_start] + container_proxy_section + content[file_ref_start:]
    
    # Add XCBuildConfiguration for test targets
    build_config_section = content.find('/* End XCBuildConfiguration section */')
    
    build_configs = f"""
\t\t{tests_build_config_debug_id} /* Debug */ = {{
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {{
\t\t\t\tBUNDLE_LOADER = "$(TEST_HOST)";
\t\t\t\tCODE_SIGN_STYLE = Automatic;
\t\t\t\tCURRENT_PROJECT_VERSION = 1;
\t\t\t\tGENERATE_INFOPLIST_FILE = YES;
\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 17.0;
\t\t\t\tMARKETING_VERSION = 1.0;
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = com.junkos.app.tests;
\t\t\t\tPRODUCT_NAME = "$(TARGET_NAME)";
\t\t\t\tSWIFT_EMIT_LOC_STRINGS = NO;
\t\t\t\tSWIFT_VERSION = 5.0;
\t\t\t\tTARGETED_DEVICE_FAMILY = "1,2";
\t\t\t\tTEST_HOST = "$(BUILT_PRODUCTS_DIR)/JunkOS.app/$(BUNDLE_EXECUTABLE_FOLDER_PATH)/JunkOS";
\t\t\t}};
\t\t\tname = Debug;
\t\t}};
\t\t{tests_build_config_release_id} /* Release */ = {{
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {{
\t\t\t\tBUNDLE_LOADER = "$(TEST_HOST)";
\t\t\t\tCODE_SIGN_STYLE = Automatic;
\t\t\t\tCURRENT_PROJECT_VERSION = 1;
\t\t\t\tGENERATE_INFOPLIST_FILE = YES;
\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 17.0;
\t\t\t\tMARKETING_VERSION = 1.0;
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = com.junkos.app.tests;
\t\t\t\tPRODUCT_NAME = "$(TARGET_NAME)";
\t\t\t\tSWIFT_EMIT_LOC_STRINGS = NO;
\t\t\t\tSWIFT_VERSION = 5.0;
\t\t\t\tTARGETED_DEVICE_FAMILY = "1,2";
\t\t\t\tTEST_HOST = "$(BUILT_PRODUCTS_DIR)/JunkOS.app/$(BUNDLE_EXECUTABLE_FOLDER_PATH)/JunkOS";
\t\t\t}};
\t\t\tname = Release;
\t\t}};
\t\t{uitests_build_config_debug_id} /* Debug */ = {{
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {{
\t\t\t\tCODE_SIGN_STYLE = Automatic;
\t\t\t\tCURRENT_PROJECT_VERSION = 1;
\t\t\t\tGENERATE_INFOPLIST_FILE = YES;
\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 17.0;
\t\t\t\tMARKETING_VERSION = 1.0;
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = com.junkos.app.uitests;
\t\t\t\tPRODUCT_NAME = "$(TARGET_NAME)";
\t\t\t\tSWIFT_EMIT_LOC_STRINGS = NO;
\t\t\t\tSWIFT_VERSION = 5.0;
\t\t\t\tTARGETED_DEVICE_FAMILY = "1,2";
\t\t\t\tTEST_TARGET_NAME = JunkOS;
\t\t\t}};
\t\t\tname = Debug;
\t\t}};
\t\t{uitests_build_config_release_id} /* Release */ = {{
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {{
\t\t\t\tCODE_SIGN_STYLE = Automatic;
\t\t\t\tCURRENT_PROJECT_VERSION = 1;
\t\t\t\tGENERATE_INFOPLIST_FILE = YES;
\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 17.0;
\t\t\t\tMARKETING_VERSION = 1.0;
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = com.junkos.app.uitests;
\t\t\t\tPRODUCT_NAME = "$(TARGET_NAME)";
\t\t\t\tSWIFT_EMIT_LOC_STRINGS = NO;
\t\t\t\tSWIFT_VERSION = 5.0;
\t\t\t\tTARGETED_DEVICE_FAMILY = "1,2";
\t\t\t\tTEST_TARGET_NAME = JunkOS;
\t\t\t}};
\t\t\tname = Release;
\t\t}};
"""
    content = content[:build_config_section] + build_configs + content[build_config_section:]
    
    # Add XCConfigurationList for test targets
    config_list_section = content.find('/* End XCConfigurationList section */')
    
    config_lists = f"""
\t\t{tests_build_config_list_id} /* Build configuration list for PBXNativeTarget "JunkOSTests" */ = {{
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t{tests_build_config_debug_id} /* Debug */,
\t\t\t\t{tests_build_config_release_id} /* Release */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t}};
\t\t{uitests_build_config_list_id} /* Build configuration list for PBXNativeTarget "JunkOSUITests" */ = {{
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t{uitests_build_config_debug_id} /* Debug */,
\t\t\t\t{uitests_build_config_release_id} /* Release */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t}};
"""
    content = content[:config_list_section] + config_lists + content[config_list_section:]
    
    # Write modified content
    with open(project_path, 'w') as f:
        f.write(content)
    
    print("✅ Successfully added test targets to Xcode project")
    return True

if __name__ == "__main__":
    project_path = "JunkOS.xcodeproj/project.pbxproj"
    success = add_test_targets_to_project(project_path)
    exit(0 if success else 1)

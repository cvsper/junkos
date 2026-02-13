#!/bin/bash
# Script to add test targets to JunkOS.xcodeproj
# This script uses xcodebuild and manual project modification

set -e

PROJECT_DIR="$HOME/Documents/programs/webapps/junkos/JunkOS-Clean"
PROJECT_FILE="$PROJECT_DIR/JunkOS.xcodeproj/project.pbxproj"

echo "🔧 Adding test targets to JunkOS project..."

# Check if xcodeproj gem is installed (Ruby gem for Xcode project manipulation)
if ! gem list xcodeproj -i > /dev/null 2>&1; then
    echo "⚠️  xcodeproj gem not found. Installing..."
    sudo gem install xcodeproj
fi

# Run Ruby script to add test targets
ruby - <<'RUBY_SCRIPT'
require 'xcodeproj'

project_path = File.expand_path('~/Documents/programs/webapps/junkos/JunkOS-Clean/JunkOS.xcodeproj')
project = Xcodeproj::Project.open(project_path)

# Find the main target
main_target = project.targets.find { |t| t.name == 'JunkOS' }

unless main_target
  puts "❌ Main target 'JunkOS' not found!"
  exit 1
end

# Create JunkOSTests target if it doesn't exist
unit_test_target = project.targets.find { |t| t.name == 'JunkOSTests' }

unless unit_test_target
  puts "📝 Creating JunkOSTests target..."
  
  unit_test_target = project.new_target(:unit_test_bundle, 'JunkOSTests', :ios, '16.0', main_target.platform_name, :swift)
  unit_test_target.product_name = 'JunkOSTests'
  
  # Set bundle identifier
  unit_test_target.build_configurations.each do |config|
    config.build_settings['PRODUCT_BUNDLE_IDENTIFIER'] = 'com.goumuve.app.tests'
    config.build_settings['CODE_SIGN_STYLE'] = 'Automatic'
    config.build_settings['INFOPLIST_FILE'] = 'JunkOSTests/Info.plist'
    config.build_settings['SWIFT_VERSION'] = '5.0'
    config.build_settings['ENABLE_CODE_COVERAGE'] = 'YES'
  end
  
  # Add test target dependency
  unit_test_target.add_dependency(main_target)
  
  puts "✅ JunkOSTests target created"
else
  puts "ℹ️  JunkOSTests target already exists"
end

# Create JunkOSUITests target if it doesn't exist
ui_test_target = project.targets.find { |t| t.name == 'JunkOSUITests' }

unless ui_test_target
  puts "📝 Creating JunkOSUITests target..."
  
  ui_test_target = project.new_target(:ui_test_bundle, 'JunkOSUITests', :ios, '16.0', main_target.platform_name, :swift)
  ui_test_target.product_name = 'JunkOSUITests'
  
  # Set bundle identifier
  ui_test_target.build_configurations.each do |config|
    config.build_settings['PRODUCT_BUNDLE_IDENTIFIER'] = 'com.goumuve.app.uitests'
    config.build_settings['CODE_SIGN_STYLE'] = 'Automatic'
    config.build_settings['INFOPLIST_FILE'] = 'JunkOSUITests/Info.plist'
    config.build_settings['SWIFT_VERSION'] = '5.0'
    config.build_settings['TEST_TARGET_NAME'] = 'JunkOS'
  end
  
  # Add test target dependency
  ui_test_target.add_dependency(main_target)
  
  puts "✅ JunkOSUITests target created"
else
  puts "ℹ️  JunkOSUITests target already exists"
end

# Add test files to the project
def add_files_to_target(project, group_path, target, files_pattern)
  group = project.main_group.find_subpath(group_path, true)
  
  Dir.glob(files_pattern).each do |file_path|
    file_ref = group.new_file(File.absolute_path(file_path))
    target.add_file_references([file_ref])
  end
end

# Add JunkOSTests files
tests_group = project.main_group.find_subpath('JunkOSTests', true)
Dir.glob('JunkOSTests/**/*.swift').each do |file_path|
  relative_path = file_path.sub('JunkOSTests/', '')
  subgroup_path = File.dirname(relative_path)
  
  if subgroup_path != '.'
    subgroup = tests_group.find_subpath(subgroup_path, true)
  else
    subgroup = tests_group
  end
  
  unless subgroup.files.any? { |f| f.path == File.basename(file_path) }
    file_ref = subgroup.new_file(File.absolute_path(file_path))
    unit_test_target.add_file_references([file_ref])
  end
end

# Add JunkOSUITests files
ui_tests_group = project.main_group.find_subpath('JunkOSUITests', true)
Dir.glob('JunkOSUITests/**/*.swift').each do |file_path|
  relative_path = file_path.sub('JunkOSUITests/', '')
  subgroup_path = File.dirname(relative_path)
  
  if subgroup_path != '.'
    subgroup = ui_tests_group.find_subpath(subgroup_path, true)
  else
    subgroup = ui_tests_group
  end
  
  unless subgroup.files.any? { |f| f.path == File.basename(file_path) }
    file_ref = subgroup.new_file(File.absolute_path(file_path))
    ui_test_target.add_file_references([file_ref])
  end
end

puts "📁 Added test files to project"

# Save the project
project.save

puts "✅ Project saved successfully!"
puts ""
puts "🎉 Test infrastructure setup complete!"
puts ""
puts "Next steps:"
puts "1. Open JunkOS.xcodeproj in Xcode"
puts "2. Build the project (Cmd+B)"
puts "3. Run tests (Cmd+U)"
puts ""
puts "Or run from command line:"
puts "  xcodebuild test -scheme JunkOS -destination 'platform=iOS Simulator,name=iPhone 15'"
RUBY_SCRIPT

echo ""
echo "Done! ✨"
ANTML:parameter>
</invoke>
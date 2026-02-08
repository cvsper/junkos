#!/usr/bin/env ruby
require 'xcodeproj'

project_path = '../JunkOS.xcodeproj'
project = Xcodeproj::Project.open(project_path)

# Get the main target
target = project.targets.first

# Get the JunkOS group
junkos_group = project.main_group['JunkOS']

# Create Components group if it doesn't exist
components_group = junkos_group['Components'] || junkos_group.new_group('Components')

# Define all new files to add
new_files = [
  'JunkOS/Components/LoadingStates/SkeletonView.swift',
  'JunkOS/Components/EmptyStates/EmptyStateView.swift',
  'JunkOS/Components/ErrorHandling/ErrorView.swift',
  'JunkOS/Components/Animations/ConfettiView.swift',
  'JunkOS/Components/Onboarding/OnboardingView.swift',
  'JunkOS/Components/TrustComponents.swift',
  'JunkOS/Components/ProgressiveDisclosureComponents.swift',
  'JunkOS/Utilities/AccessibilityHelpers.swift'
]

new_files.each do |file_path|
  # Check if file already exists in project
  existing_file = project.files.find { |f| f.path == file_path }
  
  unless existing_file
    puts "Adding #{file_path}..."
    
    # Determine the appropriate group
    if file_path.include?('LoadingStates')
      loading_group = components_group['LoadingStates'] || components_group.new_group('LoadingStates')
      file_ref = loading_group.new_file(file_path)
    elsif file_path.include?('EmptyStates')
      empty_group = components_group['EmptyStates'] || components_group.new_group('EmptyStates')
      file_ref = empty_group.new_file(file_path)
    elsif file_path.include?('ErrorHandling')
      error_group = components_group['ErrorHandling'] || components_group.new_group('ErrorHandling')
      file_ref = error_group.new_file(file_path)
    elsif file_path.include?('Animations')
      anim_group = components_group['Animations'] || components_group.new_group('Animations')
      file_ref = anim_group.new_file(file_path)
    elsif file_path.include?('Onboarding')
      onboard_group = components_group['Onboarding'] || components_group.new_group('Onboarding')
      file_ref = onboard_group.new_file(file_path)
    elsif file_path.include?('Components')
      file_ref = components_group.new_file(file_path)
    elsif file_path.include?('Utilities')
      utilities_group = junkos_group['Utilities'] || junkos_group.new_group('Utilities')
      file_ref = utilities_group.new_file(file_path)
    end
    
    # Add to target
    target.add_file_references([file_ref])
  else
    puts "File #{file_path} already exists in project."
  end
end

# Save the project
project.save

puts "✅ All new files added to Xcode project!"

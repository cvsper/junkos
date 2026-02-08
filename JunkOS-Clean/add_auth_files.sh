#!/bin/bash

# Script to add auth files to Xcode project
# Run from project root: bash add_auth_files.sh

PROJECT_FILE="JunkOS.xcodeproj/project.pbxproj"

# Files to add
AUTH_FILES=(
    "JunkOS/Views/Auth/WelcomeAuthView.swift"
    "JunkOS/Views/Auth/LoginOptionsView.swift"
    "JunkOS/Views/Auth/PhoneSignUpView.swift"
    "JunkOS/Views/Auth/VerificationCodeView.swift"
    "JunkOS/Views/Auth/EmailLoginView.swift"
    "JunkOS/Views/MainTabView.swift"
    "JunkOS/Views/OrdersView.swift"
    "JunkOS/Views/AccountView.swift"
    "JunkOS/Managers/AuthenticationManager.swift"
)

echo "🔧 Adding auth files to Xcode project..."

# Check if files exist
for file in "${AUTH_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing: $file"
    else
        echo "✅ Found: $file"
    fi
done

echo ""
echo "⚠️  Manual steps required:"
echo "1. Open JunkOS.xcodeproj in Xcode"
echo "2. Right-click 'JunkOS' folder → Add Files to 'JunkOS'"
echo "3. Select all files in Views/Auth/ and Managers/"
echo "4. Ensure 'Add to targets: JunkOS' is checked"
echo "5. Click Add"
echo ""
echo "Or use Xcode's File → Add Files to 'JunkOS' menu"

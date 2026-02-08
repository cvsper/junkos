#!/bin/bash
# Script to add new API integration files to Xcode project

set -e

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

echo "🔧 Adding API integration files to Xcode project..."

# Check if files exist
FILES_TO_ADD=(
    "JunkOS/Services/APIClient.swift"
    "JunkOS/Services/Config.swift"
    "JunkOS/Models/APIModels.swift"
)

for file in "${FILES_TO_ADD[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Error: $file not found"
        exit 1
    fi
done

echo "✅ All files found"

# Method 1: Try using xed (Xcode command line tool)
if command -v xed &> /dev/null; then
    echo "📝 Opening project in Xcode..."
    echo ""
    echo "Please manually add these files through Xcode:"
    echo "  1. Right-click 'JunkOS' folder in Project Navigator"
    echo "  2. Select 'Add Files to JunkOS...'"
    echo "  3. Navigate to and select:"
    for file in "${FILES_TO_ADD[@]}"; do
        echo "     - $file"
    done
    echo "  4. Make sure 'Copy items if needed' is UNCHECKED"
    echo "  5. Make sure target 'JunkOS' is CHECKED"
    echo "  6. Click 'Add'"
    echo ""
    
    # Open the project
    open "JunkOS.xcodeproj"
    
    echo "✅ Project opened in Xcode"
    echo ""
    echo "After adding files, build with: Cmd+B"
    
else
    echo "❌ Xcode command line tools not found"
    echo "Please open the project manually:"
    echo "  open JunkOS.xcodeproj"
    exit 1
fi

# Method 2: Check if xcodeproj Ruby gem is available
# if command -v xcodeproj &> /dev/null; then
#     echo "Using xcodeproj to add files..."
#     # This would require a Ruby script
# fi

echo ""
echo "📋 Quick verification after adding files:"
echo "  1. Build: Cmd+B in Xcode"
echo "  2. Check for any compile errors"
echo "  3. Run: Cmd+R"
echo ""
echo "🚀 Start backend with: cd backend && ./run.sh"

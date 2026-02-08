#!/bin/bash

# JunkOS Icon Generator
# Generates all required iOS app icon sizes from SVG template
# Requires: ImageMagick (brew install imagemagick)

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}JunkOS Icon Generator${NC}"
echo "=========================="

# Check if ImageMagick is installed
if ! command -v magick &> /dev/null && ! command -v convert &> /dev/null; then
    echo -e "${RED}Error: ImageMagick is not installed${NC}"
    echo "Install with: brew install imagemagick"
    exit 1
fi

# Use 'magick' command (ImageMagick 7) or fallback to 'convert' (ImageMagick 6)
if command -v magick &> /dev/null; then
    CONVERT_CMD="magick"
else
    CONVERT_CMD="convert"
fi

# Input and output
INPUT="icon-template.svg"
OUTPUT_DIR="./exported"

# Check if input exists
if [ ! -f "$INPUT" ]; then
    echo -e "${RED}Error: $INPUT not found${NC}"
    echo "Make sure you're in the icons directory"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"
echo -e "Output directory: ${GREEN}$OUTPUT_DIR${NC}"
echo ""

# iOS icon sizes (pt → px)
declare -a sizes=(
    "1024:App Store"
    "180:iPhone @3x"
    "167:iPad Pro"
    "152:iPad @2x"
    "120:iPhone @2x"
    "87:iPhone @3x Settings"
    "80:iPad @2x Settings"
    "76:iPad"
    "60:iPhone"
    "58:iPhone Settings"
    "40:Spotlight"
    "29:Settings"
    "20:Notification"
)

# Generate each size
echo "Generating icons..."
echo ""

for item in "${sizes[@]}"; do
    IFS=':' read -r size description <<< "$item"
    
    output_file="$OUTPUT_DIR/icon-${size}.png"
    
    echo -e "  [${BLUE}${size}x${size}${NC}] ${description}..."
    
    $CONVERT_CMD "$INPUT" \
        -background none \
        -resize "${size}x${size}" \
        -gravity center \
        -extent "${size}x${size}" \
        "$output_file"
    
    # Check file was created
    if [ -f "$output_file" ]; then
        file_size=$(ls -lh "$output_file" | awk '{print $5}')
        echo -e "           ${GREEN}✓${NC} Created (${file_size})"
    else
        echo -e "           ${RED}✗${NC} Failed"
    fi
done

echo ""
echo -e "${GREEN}✓ All icons generated successfully!${NC}"
echo ""
echo "Generated files:"
ls -lh "$OUTPUT_DIR" | tail -n +2 | awk '{printf "  - %s (%s)\n", $9, $5}'
echo ""
echo "Next steps:"
echo "1. Open your Xcode project"
echo "2. Go to Assets.xcassets"
echo "3. Select/Create AppIcon"
echo "4. Drag and drop icons from $OUTPUT_DIR"
echo ""
echo -e "📖 See ${BLUE}icon-generation-guide.md${NC} for detailed Xcode integration steps"

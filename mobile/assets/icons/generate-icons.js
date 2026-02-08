#!/usr/bin/env node

/**
 * JunkOS Icon Generator (Node.js)
 * Generates all required iOS app icon sizes from SVG template
 * 
 * Requirements: npm install sharp
 * Usage: node generate-icons.js
 */

const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

// Configuration
const INPUT_SVG = 'icon-template.svg';
const OUTPUT_DIR = './exported';

// iOS icon sizes with descriptions
const ICON_SIZES = [
  { size: 1024, description: 'App Store' },
  { size: 180, description: 'iPhone @3x' },
  { size: 167, description: 'iPad Pro' },
  { size: 152, description: 'iPad @2x' },
  { size: 120, description: 'iPhone @2x' },
  { size: 87, description: 'iPhone @3x Settings' },
  { size: 80, description: 'iPad @2x Settings' },
  { size: 76, description: 'iPad' },
  { size: 60, description: 'iPhone' },
  { size: 58, description: 'iPhone Settings' },
  { size: 40, description: 'Spotlight' },
  { size: 29, description: 'Settings' },
  { size: 20, description: 'Notification' }
];

// Colors
const colors = {
  reset: '\x1b[0m',
  blue: '\x1b[34m',
  green: '\x1b[32m',
  red: '\x1b[31m'
};

console.log(`${colors.blue}JunkOS Icon Generator${colors.reset}`);
console.log('==========================\n');

// Check if sharp is installed
try {
  require.resolve('sharp');
} catch (e) {
  console.error(`${colors.red}Error: 'sharp' module not found${colors.reset}`);
  console.error('Install with: npm install sharp\n');
  process.exit(1);
}

// Check if input file exists
if (!fs.existsSync(INPUT_SVG)) {
  console.error(`${colors.red}Error: ${INPUT_SVG} not found${colors.reset}`);
  console.error('Make sure you\'re in the icons directory\n');
  process.exit(1);
}

// Create output directory
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

console.log(`Output directory: ${colors.green}${OUTPUT_DIR}${colors.reset}\n`);
console.log('Generating icons...\n');

// Generate all icon sizes
async function generateIcons() {
  const results = [];
  
  for (const { size, description } of ICON_SIZES) {
    const outputPath = path.join(OUTPUT_DIR, `icon-${size}.png`);
    
    process.stdout.write(`  [${colors.blue}${size}x${size}${colors.reset}] ${description}...`);
    
    try {
      await sharp(INPUT_SVG)
        .resize(size, size, {
          fit: 'contain',
          background: { r: 0, g: 0, b: 0, alpha: 0 }
        })
        .png({
          compressionLevel: 9,
          palette: false
        })
        .toFile(outputPath);
      
      const stats = fs.statSync(outputPath);
      const fileSizeKB = (stats.size / 1024).toFixed(1);
      
      console.log(` ${colors.green}✓${colors.reset} Created (${fileSizeKB} KB)`);
      
      results.push({
        size,
        path: outputPath,
        fileSize: fileSizeKB,
        success: true
      });
      
    } catch (error) {
      console.log(` ${colors.red}✗${colors.reset} Failed`);
      console.error(`    Error: ${error.message}`);
      
      results.push({
        size,
        success: false,
        error: error.message
      });
    }
  }
  
  return results;
}

// Generate summary
function printSummary(results) {
  console.log('');
  
  const successful = results.filter(r => r.success).length;
  const failed = results.filter(r => !r.success).length;
  
  if (failed === 0) {
    console.log(`${colors.green}✓ All ${successful} icons generated successfully!${colors.reset}\n`);
  } else {
    console.log(`${colors.red}✗ ${failed} icon(s) failed to generate${colors.reset}`);
    console.log(`${colors.green}✓ ${successful} icon(s) generated successfully${colors.reset}\n`);
  }
  
  // List generated files
  console.log('Generated files:');
  results
    .filter(r => r.success)
    .forEach(r => {
      console.log(`  - icon-${r.size}.png (${r.fileSize} KB)`);
    });
  
  // Calculate total size
  const totalSize = results
    .filter(r => r.success)
    .reduce((sum, r) => sum + parseFloat(r.fileSize), 0);
  
  console.log(`\nTotal size: ${totalSize.toFixed(1)} KB\n`);
  
  // Next steps
  console.log('Next steps:');
  console.log('1. Open your Xcode project');
  console.log('2. Go to Assets.xcassets');
  console.log('3. Select/Create AppIcon');
  console.log(`4. Drag and drop icons from ${OUTPUT_DIR}`);
  console.log('');
  console.log(`📖 See ${colors.blue}icon-generation-guide.md${colors.reset} for detailed Xcode integration steps\n`);
}

// Main execution
(async () => {
  try {
    const results = await generateIcons();
    printSummary(results);
    
    // Exit with error code if any failed
    const failed = results.filter(r => !r.success).length;
    process.exit(failed > 0 ? 1 : 0);
    
  } catch (error) {
    console.error(`\n${colors.red}Fatal error: ${error.message}${colors.reset}\n`);
    process.exit(1);
  }
})();

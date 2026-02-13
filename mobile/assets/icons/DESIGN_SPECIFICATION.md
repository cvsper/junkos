# Umuve iOS App Icon - Design Specification

## Overview
Umuve app icon represents a modern, clean digital cleanup tool. The design features a stylized trash bin with an upward-pointing arrow, symbolizing the removal and clearing of unwanted items.

## Design Concept

### Visual Metaphor
- **Trash Bin**: Represents junk, clutter, and items to be removed
- **Upward Arrow**: Symbolizes removal, lifting away, and cleaning up
- **Clean Aesthetic**: Modern, minimal design that works at all sizes

### Brand Positioning
- Professional yet approachable
- Tech-forward and trustworthy
- Emphasizes positive action (cleaning/improving)

## Color Scheme

### Primary Colors
- **Indigo #6366F1** - Main background gradient
  - RGB: (99, 102, 241)
  - Used for: Background, shadows, details
  - Conveys: Trust, professionalism, technology

- **Emerald #10B981** - Accent color
  - RGB: (16, 185, 129)
  - Used for: Arrow, action elements, highlights
  - Conveys: Success, growth, positive action

### Supporting Colors
- **White #FFFFFF** - Contrast elements
  - Used for: Trash bin, sparkles, highlights
  - Opacity variations: 95%, 90%, 80% for depth

- **Light Indigo #7C7FF5** - Gradient accent
  - Used for: Background gradient top
  - Creates visual interest and depth

## Design Elements

### 1. Background
- Rounded rectangle (iOS standard)
- Corner radius: 180px (at 1024x1024)
- Linear gradient from light indigo to deep indigo
- Direction: Top-left to bottom-right

### 2. Trash Bin
- Position: Center-bottom
- Style: Modern, simplified geometric shape
- Color: White with 95% opacity
- Features:
  - Trapezoidal body (wider at top)
  - Rectangular lid with rounded corners
  - Handle on lid
  - Subtle vertical line details for texture
  - Soft shadow for depth

### 3. Upward Arrow
- Position: Center, overlapping bin
- Style: Bold, rounded
- Color: Emerald gradient (light to dark)
- Features:
  - Rounded shaft (pill shape)
  - Wide arrow head for visibility
  - Highlight/shine effect for polish
  - Shadow for depth and separation

### 4. Accent Details
- Sparkle elements in corners
- Various sizes (6px - 12px at 1024px)
- White with varying opacity (50% - 80%)
- Suggests cleanliness and freshness

## iOS Human Interface Guidelines Compliance

### Icon Design Principles
✅ **Simple and recognizable** - Clear trash bin + arrow metaphor
✅ **Scalable** - Design works from 20x20 to 1024x1024
✅ **Focused** - Single, clear concept without clutter
✅ **Memorable** - Distinctive shape and color combination
✅ **Consistent** - Follows iOS rounded square format

### Technical Requirements
✅ **No transparency** - Solid background with gradient
✅ **Rounded corners** - Applied automatically by iOS (included in template)
✅ **Proper safe area** - Important elements away from edges
✅ **High contrast** - White elements on colored background
✅ **RGB color space** - All colors defined in RGB

### Size Optimization
- **Large sizes (1024px, 180px, 167px, 152px)**:
  - Full detail including sparkles and textures
  - Subtle gradients and shadows
  
- **Medium sizes (120px, 87px, 80px, 76px)**:
  - Maintain all major elements
  - Slightly simplified shadows
  
- **Small sizes (60px, 58px, 40px, 29px, 20px)**:
  - Ensure arrow remains bold and visible
  - Test legibility of bin shape
  - Consider slightly thicker strokes if needed

## File Specifications

### Source File
- **Format**: SVG (vector)
- **Dimensions**: 1024x1024px viewBox
- **File**: `icon-template.svg`
- Editable in: Figma, Sketch, Illustrator, Inkscape

### Export Requirements
- **Format**: PNG (24-bit with alpha)
- **Color profile**: sRGB
- **Resolution**: 72 DPI
- **Compression**: Optimized for file size
- **Naming**: icon-{size}.png (e.g., icon-1024.png)

## Variations & Alternatives

### Alternative 1: Simplified (for very small sizes)
If legibility issues at 20px-40px:
- Remove sparkles
- Simplify bin to basic trapezoid
- Make arrow thicker/bolder

### Alternative 2: Dark Mode Consideration
While iOS handles dark mode automatically:
- Current design works well on both light/dark backgrounds
- High contrast maintained
- Consider testing in both modes

### Seasonal Variations (Future)
- Holiday sparkles (gold/silver)
- Spring cleaning (pastel variations)
- Earth Day (green emphasis)

## Design Rationale

### Why This Design Works

1. **Instant Recognition**: Trash bin is universally understood
2. **Action-Oriented**: Arrow clearly indicates upward/removal action
3. **Positive Association**: Bright, clean colors (not dull/negative)
4. **Platform Appropriate**: Follows iOS design language
5. **Scalable**: Clear silhouette at any size
6. **Distinctive**: Stands out in App Store and home screen

### Testing Recommendations

1. **Size Testing**: View at all required sizes on actual devices
2. **Background Testing**: Test on various wallpapers (light, dark, colorful)
3. **Group Testing**: Place among other apps to check visibility
4. **Distance Testing**: View from typical phone viewing distance
5. **Accessibility**: Ensure sufficient contrast for visibility

## Approval Checklist

- [ ] Design matches brand identity
- [ ] Colors are accurate (#6366F1, #10B981)
- [ ] Icon is recognizable at 20x20px
- [ ] No important details within 64px of edges (at 1024px)
- [ ] Exports cleanly at all required sizes
- [ ] Passes iOS App Store validation
- [ ] Tested on actual devices (iPhone & iPad)
- [ ] Approved by stakeholders

## Version History

- **v1.0** (2026-02-06): Initial design specification
  - Modern trash bin with upward arrow
  - Indigo/Emerald color scheme
  - iOS HIG compliant

---

**Designer Notes**: This specification provides the foundation for creating all required icon assets. The SVG template (`icon-template.svg`) can be edited in any vector graphics software. Follow the generation guide for creating all required sizes.

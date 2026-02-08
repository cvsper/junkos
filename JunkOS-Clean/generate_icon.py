#!/usr/bin/env python3
"""Generate JunkOS app icon with truck silhouette on gradient background."""

from PIL import Image, ImageDraw
import os

# Brand colors
PRIMARY_COLOR = (99, 102, 241)  # #6366F1 indigo
CTA_COLOR = (16, 185, 129)      # #10B981 emerald
WHITE = (255, 255, 255)

# Icon sizes needed
SIZES = {
    'AppIcon-20x20@1x.png': 20,
    'AppIcon-20x20@2x.png': 40,
    'AppIcon-20x20@2x-1.png': 40,
    'AppIcon-20x20@3x.png': 60,
    'AppIcon-29x29@1x.png': 29,
    'AppIcon-29x29@2x.png': 58,
    'AppIcon-29x29@2x-1.png': 58,
    'AppIcon-29x29@3x.png': 87,
    'AppIcon-40x40@1x.png': 40,
    'AppIcon-40x40@2x.png': 80,
    'AppIcon-40x40@2x-1.png': 80,
    'AppIcon-40x40@3x.png': 120,
    'AppIcon-60x60@2x.png': 120,
    'AppIcon-60x60@3x.png': 180,
    'AppIcon-76x76@1x.png': 76,
    'AppIcon-76x76@2x.png': 152,
    'AppIcon-83.5x83.5@2x.png': 167,
    'AppIcon-1024x1024@1x.png': 1024,
}

def create_gradient_background(size):
    """Create a gradient from primary to CTA color."""
    img = Image.new('RGB', (size, size))
    draw = ImageDraw.Draw(img)
    
    for y in range(size):
        # Interpolate between primary and CTA color
        ratio = y / size
        r = int(PRIMARY_COLOR[0] * (1 - ratio) + CTA_COLOR[0] * ratio)
        g = int(PRIMARY_COLOR[1] * (1 - ratio) + CTA_COLOR[1] * ratio)
        b = int(PRIMARY_COLOR[2] * (1 - ratio) + CTA_COLOR[2] * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b))
    
    return img, draw

def draw_truck(draw, size):
    """Draw a simple truck silhouette."""
    # Scale factor for truck elements
    s = size / 100
    
    # Truck body (main rectangle)
    body_left = 25 * s
    body_top = 35 * s
    body_right = 75 * s
    body_bottom = 65 * s
    draw.rounded_rectangle(
        [body_left, body_top, body_right, body_bottom],
        radius=3 * s,
        fill=WHITE
    )
    
    # Truck cab (front rectangle)
    cab_left = 60 * s
    cab_top = 25 * s
    cab_right = 75 * s
    cab_bottom = 65 * s
    draw.rounded_rectangle(
        [cab_left, cab_top, cab_right, cab_bottom],
        radius=3 * s,
        fill=WHITE
    )
    
    # Front wheel
    wheel1_center = (45 * s, 65 * s)
    wheel1_radius = 8 * s
    draw.ellipse(
        [wheel1_center[0] - wheel1_radius, wheel1_center[1] - wheel1_radius,
         wheel1_center[0] + wheel1_radius, wheel1_center[1] + wheel1_radius],
        fill=WHITE
    )
    
    # Rear wheel
    wheel2_center = (65 * s, 65 * s)
    wheel2_radius = 8 * s
    draw.ellipse(
        [wheel2_center[0] - wheel2_radius, wheel2_center[1] - wheel2_radius,
         wheel2_center[0] + wheel2_radius, wheel2_center[1] + wheel2_radius],
        fill=WHITE
    )
    
    # Window on cab
    window_left = 63 * s
    window_top = 30 * s
    window_right = 72 * s
    window_bottom = 45 * s
    draw.rounded_rectangle(
        [window_left, window_top, window_right, window_bottom],
        radius=2 * s,
        fill=PRIMARY_COLOR
    )

def generate_icon(size):
    """Generate icon at specified size."""
    img, draw = create_gradient_background(size)
    draw_truck(draw, size)
    return img

def main():
    """Generate all required icon sizes."""
    output_dir = 'JunkOS/Assets.xcassets/AppIcon.appiconset'
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Generating {len(SIZES)} icon sizes...")
    
    for filename, size in SIZES.items():
        print(f"  Creating {filename} ({size}x{size})...")
        icon = generate_icon(size)
        icon.save(os.path.join(output_dir, filename), 'PNG')
    
    print(f"\n✅ All icons generated successfully in {output_dir}/")

if __name__ == '__main__':
    main()

# Umuve SEO Image Guide

## What Photos to Take

Take 10-15 photos per job covering these angles:
- Truck arriving at the property
- Items before removal (the mess)
- Loading process (team in action)
- Empty space after (the transformation)
- Team photo with Umuve branding visible on truck

## Naming Convention

```
{city-slug}-{service-slug}-{before|after|loading}-{number}.webp
```

Examples:
- `boca-raton-furniture-removal-before-1.webp`
- `fort-lauderdale-estate-cleanout-after-2.webp`
- `miami-beach-appliance-removal-loading-1.webp`

## Directory Structure

```
images/seo/
├── services/          # One hero image per service type (14 needed)
│   ├── furniture-removal.webp
│   ├── appliance-removal.webp
│   ├── mattress-disposal.webp
│   ├── estate-cleanout.webp
│   ├── construction-debris.webp
│   ├── hot-tub-removal.webp
│   ├── yard-waste-removal.webp
│   ├── electronics-recycling.webp
│   ├── garage-cleanout.webp
│   ├── office-commercial-cleanout.webp
│   ├── couch-removal.webp
│   ├── refrigerator-disposal.webp
│   ├── tv-recycling.webp
│   └── dumpster-alternative.webp
├── cities/            # City-specific photos (organized by city)
│   ├── boca-raton/
│   ├── fort-lauderdale/
│   └── ... (42 cities)
├── before-after/      # Before/after comparison pairs
├── team/              # Team and truck branding photos
└── trust-badges/      # SVG badges (already created)
```

## Minimum Photos Needed

1. **14 service hero images** (one per service type) - most impactful
2. **3-5 team/truck photos** showing Umuve branding
3. **5-10 before/after pairs** from real jobs
4. City-specific photos are a bonus but not required initially

## Photo Tips

- Use iPhone camera, natural lighting preferred
- Always show Umuve branding on truck when possible
- Landscape orientation (16:9 ratio) works best for hero images
- Keep faces out of frame unless you have permission
- Convert to WebP format before uploading (use `cwebp` or any converter)
- Target 800px wide for hero images, 400px for thumbnails
- Compress to under 100KB per image for fast page loads

## How Images Appear on Pages

Service hero images auto-display on all 588 SEO pages when the file exists. The pages use an `onerror` handler to gracefully hide the image element if the file is missing, so pages look clean either way.

Just drop the correctly named `.webp` file into `images/seo/services/` and it goes live on every page for that service automatically.

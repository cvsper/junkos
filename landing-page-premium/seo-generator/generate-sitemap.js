#!/usr/bin/env node

/**
 * Umuve Sitemap Generator
 * Generates sitemap.xml with all pages, clean URLs
 */

const fs = require('fs');
const path = require('path');

const cities = require('./data/cities.json');
const services = require('./data/services.json');

const today = new Date().toISOString().split('T')[0];

let urls = [];

// Homepage
urls.push({ loc: 'https://goumuve.com/', changefreq: 'daily', priority: '1.0' });

// Operators page
urls.push({ loc: 'https://goumuve.com/operators', changefreq: 'weekly', priority: '0.8' });

// Partners page
urls.push({ loc: 'https://goumuve.com/partners/realtors', changefreq: 'weekly', priority: '0.8' });

// Blog
const blogSlugs = [
  'how-to-make-money-hauling-junk-florida',
  'junk-removal-miami',
  'junk-removal-fort-lauderdale',
  'junk-removal-boca-raton',
  'junk-removal-west-palm-beach',
  'cost-of-junk-removal-south-florida'
];
blogSlugs.forEach(slug => {
  urls.push({ loc: `https://goumuve.com/blog/${slug}`, changefreq: 'weekly', priority: '0.9' });
});

// Guides
urls.push({ loc: 'https://goumuve.com/guides/junk-removal-cost-south-florida', changefreq: 'weekly', priority: '0.9' });
urls.push({ loc: 'https://goumuve.com/guides/south-florida-recycling-resource-guide', changefreq: 'weekly', priority: '0.9' });
urls.push({ loc: 'https://goumuve.com/guides/south-florida-dump-sites-pricing-guide', changefreq: 'weekly', priority: '0.9' });

// How-To Disposal & Lifestyle Guides (Phase 2)
const guideSlug = [
  'how-to-dispose-of-a-mattress',
  'how-to-dispose-of-a-refrigerator',
  'how-to-dispose-of-electronics',
  'how-to-dispose-of-paint',
  'how-to-dispose-of-a-couch',
  'how-to-dispose-of-appliances',
  'how-to-dispose-of-a-tv',
  'how-to-dispose-of-tires',
  'how-to-dispose-of-a-hot-tub',
  'how-to-dispose-of-a-washer-dryer',
  'how-to-dispose-of-concrete',
  'how-to-dispose-of-drywall',
  'how-to-dispose-of-a-dishwasher',
  'how-to-dispose-of-a-dehumidifier',
  'how-to-dispose-of-a-stove-oven',
  'how-to-remove-a-toilet',
  'how-to-remove-drywall',
  'how-to-remove-a-kitchen-sink',
  'how-to-take-apart-a-bed-frame',
  'how-to-take-apart-a-couch',
  'declutter-before-moving',
  'declutter-for-spring-cleaning',
  'what-to-do-with-old-furniture',
  'garage-cleanout-guide',
  'estate-cleanout-checklist',
  'move-out-cleaning-checklist',
  'renovation-debris-disposal-guide',
  'hoarder-cleanout-guide',
  'storage-unit-cleanout-guide',
  'downsizing-tips',
];
guideSlug.forEach(slug => {
  urls.push({ loc: `https://goumuve.com/guides/${slug}`, changefreq: 'monthly', priority: '0.8' });
});

// City pages
cities.forEach(city => {
    urls.push({
        loc: `https://goumuve.com/junk-removal/${city.slug}-fl`,
        changefreq: 'weekly',
        priority: '0.8'
    });
});

// Service pages
services.forEach(service => {
    urls.push({
        loc: `https://goumuve.com/services/${service.slug}`,
        changefreq: 'weekly',
        priority: '0.8'
    });
});

// Service×City pages (long-tail)
cities.forEach(city => {
    services.forEach(service => {
        urls.push({
            loc: `https://goumuve.com/junk-removal/${city.slug}-fl/${service.slug}`,
            changefreq: 'weekly',
            priority: '0.7'
        });
    });
});

// Neighborhood sub-pages (Phase 3 — hyper-local SEO)
const neighborhoodsIndexPath = path.join(__dirname, 'data/neighborhoods-index.json');
if (fs.existsSync(neighborhoodsIndexPath)) {
    const neighborhoodsIndex = require('./data/neighborhoods-index.json');
    neighborhoodsIndex.forEach(n => {
        urls.push({
            loc: n.url,
            changefreq: 'weekly',
            priority: '0.6'
        });
    });
}

// Comparison pages (original + Phase 5)
const comparisons = [
  'umuve-vs-1800-got-junk',
  'umuve-vs-junk-king',
  'dumpster-rental-vs-junk-removal',
  'college-hunks',
  'trash-butler',
  'bagster',
  'junk-removal-near-me',
  'diy-junk-removal'
];
comparisons.forEach(slug => {
    urls.push({
        loc: `https://goumuve.com/vs/${slug}`,
        changefreq: 'monthly',
        priority: '0.7'
    });
});

// Phase 4: Commercial pages hub + sub-pages
urls.push({ loc: 'https://goumuve.com/commercial', changefreq: 'weekly', priority: '0.9' });
const commercialSlugs = [
  'office-cleanout',
  'retail-store-cleanout',
  'construction-debris',
  'restaurant-cleanout',
  'warehouse-cleanout',
  'property-management',
  'hoa-services'
];
commercialSlugs.forEach(slug => {
  urls.push({ loc: `https://goumuve.com/commercial/${slug}`, changefreq: 'weekly', priority: '0.8' });
});

// Phase 6: Hub/Pillar pages
urls.push({ loc: 'https://goumuve.com/services', changefreq: 'weekly', priority: '0.9' });
urls.push({ loc: 'https://goumuve.com/locations', changefreq: 'weekly', priority: '0.9' });
urls.push({ loc: 'https://goumuve.com/guides', changefreq: 'weekly', priority: '0.9' });
// Hubs
urls.push({ loc: 'https://goumuve.com/impact-2025', changefreq: 'monthly', priority: '0.9' });
urls.push({ loc: 'https://goumuve.com/pricing', changefreq: 'weekly', priority: '0.9' });

// Static pages
urls.push({ loc: 'https://goumuve.com/privacy', changefreq: 'monthly', priority: '0.3' });
urls.push({ loc: 'https://goumuve.com/terms', changefreq: 'monthly', priority: '0.3' });

// Build XML
const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map(u => `  <url>
    <loc>${u.loc}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>${u.changefreq}</changefreq>
    <priority>${u.priority}</priority>
  </url>`).join('\n')}
</urlset>
`;

const filepath = path.join(__dirname, '../sitemap.xml');
fs.writeFileSync(filepath, xml);
console.log(`✓ Generated sitemap.xml with ${urls.length} URLs`);

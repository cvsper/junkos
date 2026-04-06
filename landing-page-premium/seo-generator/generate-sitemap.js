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

// Blog
urls.push({ loc: 'https://goumuve.com/blog/how-to-make-money-hauling-junk-florida', changefreq: 'monthly', priority: '0.9' });

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

// Comparison pages
const comparisons = ['umuve-vs-1800-got-junk', 'umuve-vs-junk-king', 'dumpster-rental-vs-junk-removal'];
comparisons.forEach(slug => {
    urls.push({
        loc: `https://goumuve.com/vs/${slug}`,
        changefreq: 'monthly',
        priority: '0.7'
    });
});

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

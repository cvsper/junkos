#!/usr/bin/env node

/**
 * Umuve SEO Page Generator
 * Generates location pages, service pages, and comparison pages
 */

const fs = require('fs');
const path = require('path');

// Load data
const cities = require('./data/cities.json');
const services = require('./data/services.json');

// Read base template
const baseTemplate = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf-8');

// Extract head and footer from base template
const headMatch = baseTemplate.match(/<head>([\s\S]*?)<\/head>/);
const navMatch = baseTemplate.match(/<nav[\s\S]*?<\/nav>/);
const footerMatch = baseTemplate.match(/<footer[\s\S]*?<\/footer>/);
const scriptsMatch = baseTemplate.match(/<script src="script\.js"><\/script>/);

const baseHead = headMatch ? headMatch[1] : '';
const baseNav = navMatch ? navMatch[0] : '';
const baseFooter = footerMatch ? footerMatch[0] : '';

/**
 * Generate location page for a city
 */
function generateLocationPage(city) {
    const title = `Junk Removal in ${city.name}, FL — Same-Day Service | Umuve`;
    const description = `Professional junk removal in ${city.name}, Florida. ${city.operators} local operators, ${city.jobsCompleted}+ jobs completed, ${city.rating}★ rating. Average cost: $${city.avgJobCost}. Book online in 3 minutes.`;

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="${description}">

    <!-- Open Graph -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://goumuve.com/junk-removal/${city.slug}-fl">
    <meta property="og:title" content="${title}">
    <meta property="og:description" content="${description}">
    <meta property="og:image" content="https://app.goumuve.com/opengraph-image">

    <!-- Canonical -->
    <link rel="canonical" href="https://goumuve.com/junk-removal/${city.slug}-fl">

    <title>${title}</title>

    <link rel="stylesheet" href="../styles.css">
    <link rel="icon" type="image/png" href="../logo-icon.png">

    <!-- Google Analytics -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-CLGPJ5TS3G"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', 'G-CLGPJ5TS3G');
    </script>

    <!-- Preload fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@700;800;900&display=swap" rel="stylesheet">

    <!-- Structured Data - Service -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Service",
        "serviceType": "Junk Removal",
        "provider": {
            "@type": "Organization",
            "name": "Umuve",
            "url": "https://goumuve.com"
        },
        "areaServed": {
            "@type": "City",
            "name": "${city.name}",
            "containedIn": {
                "@type": "State",
                "name": "Florida"
            }
        },
        "offers": {
            "@type": "Offer",
            "priceRange": "$$"
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "${city.rating}",
            "reviewCount": "${city.reviewCount}"
        }
    }
    </script>

    <!-- Breadcrumb Schema -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": "https://goumuve.com"
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Junk Removal",
                "item": "https://goumuve.com/junk-removal"
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": "${city.name}, FL",
                "item": "https://goumuve.com/junk-removal/${city.slug}-fl"
            }
        ]
    }
    </script>
</head>
<body>
    <!-- Simple Nav -->
    <nav class="navbar" style="position: sticky; top: 0; background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); z-index: 100; border-bottom: 1px solid rgba(0,0,0,0.06);">
        <div class="container">
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem 0;">
                <a href="/" style="display: flex; align-items: center; text-decoration: none;">
                    <img src="../logo-nav.png" alt="Umuve" style="height: 36px;">
                </a>
                <a href="https://app.goumuve.com/book" class="btn btn-primary" style="padding: 0.75rem 1.5rem;">Book Now</a>
            </div>
        </div>
    </nav>

    <!-- Hero -->
    <section style="padding: 4rem 0 3rem; background: linear-gradient(135deg, #f9fafb 0%, #ffffff 100%);">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto; text-align: center;">
                <h1 style="font-family: Outfit, sans-serif; font-size: 2.5rem; font-weight: 800; margin-bottom: 1.5rem; line-height: 1.2;">
                    Junk Removal in ${city.name}, FL — Same-Day Service
                </h1>
                <p style="font-size: 1.25rem; color: #5c5c5c; margin-bottom: 2rem;">
                    Professional junk removal with ${city.operators} local operators serving ${city.name} and surrounding areas. ${city.jobsCompleted}+ jobs completed with ${city.rating}★ rating.
                </p>
                <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                    <a href="https://app.goumuve.com/book" class="btn btn-primary btn-xl">Book Online Now</a>
                    <a href="tel:+15618883427" class="btn btn-secondary btn-xl">Call (561) 888-3427</a>
                </div>
            </div>
        </div>
    </section>

    <!-- Stats -->
    <section style="padding: 3rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 2rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    Junk Removal Statistics for ${city.name}, FL
                </h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number">${city.operators}</div>
                        <div class="stat-label">Local Operators</div>
                        <div class="stat-source">Available in ${city.name}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${city.jobsCompleted}+</div>
                        <div class="stat-label">Jobs Completed</div>
                        <div class="stat-source">Since Feb 2024</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">$${city.avgJobCost}</div>
                        <div class="stat-label">Average Cost</div>
                        <div class="stat-source">In ${city.name}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${city.avgResponseMinutes} min</div>
                        <div class="stat-label">Response Time</div>
                        <div class="stat-source">Average matching time</div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- How It Works -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 2rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    How Junk Removal Works in ${city.name}
                </h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 2rem; margin-top: 3rem;">
                    <div style="text-align: center;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626; margin-bottom: 1rem;">01</div>
                        <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;">Book Online</h3>
                        <p style="color: #5c5c5c;">Upload photos, get instant pricing. No phone calls required.</p>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626; margin-bottom: 1rem;">02</div>
                        <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;">Same-Day Pickup</h3>
                        <p style="color: #5c5c5c;">We match you with nearby ${city.name} operators in ${city.avgResponseMinutes} minutes.</p>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626; margin-bottom: 1rem;">03</div>
                        <h3 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;">Done</h3>
                        <p style="color: #5c5c5c;">We load, haul, and dispose of everything eco-friendly.</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Popular Items -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 2rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    Most Requested Items in ${city.name}
                </h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem;">
                    ${city.topItems.map(item => `
                    <div style="padding: 1.5rem; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.75rem; text-align: center;">
                        <h3 style="font-weight: 600; color: #1a1a1a;">${item}</h3>
                    </div>
                    `).join('')}
                </div>
            </div>
        </div>
    </section>

    <!-- Neighborhoods -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 2rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    ${city.name} Neighborhoods We Serve
                </h2>
                <p style="font-size: 1.125rem; color: #5c5c5c; text-align: center; margin-bottom: 2rem;">
                    Umuve serves all ${city.name} neighborhoods including ${city.neighborhoods.join(', ')}, and surrounding areas within ${city.county} County.
                </p>
                <div style="text-align: center;">
                    <a href="https://app.goumuve.com/book" class="btn btn-primary btn-xl">Book Your ${city.name} Pickup</a>
                </div>
            </div>
        </div>
    </section>

    <!-- Pricing -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 2rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    Junk Removal Pricing in ${city.name}, FL
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    Average cost in ${city.name}: <strong>$${city.avgJobCost}</strong> • All prices include labor, hauling, and eco-friendly disposal
                </p>
                <div style="display: grid; gap: 1rem;">
                    <div style="display: flex; justify-content: space-between; padding: 1rem; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.5rem;">
                        <span><strong>1/8 Truck</strong> (single item)</span>
                        <span style="font-weight: 700; color: #DC2626;">$89</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 1rem; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.5rem;">
                        <span><strong>1/4 Truck</strong> (small load)</span>
                        <span style="font-weight: 700; color: #DC2626;">$149</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 1rem; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.5rem;">
                        <span><strong>1/2 Truck</strong> (medium load)</span>
                        <span style="font-weight: 700; color: #DC2626;">$249</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 1rem; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.5rem;">
                        <span><strong>3/4 Truck</strong> (large load)</span>
                        <span style="font-weight: 700; color: #DC2626;">$399</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 1rem; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.5rem;">
                        <span><strong>Full Truck</strong> (max capacity)</span>
                        <span style="font-weight: 700; color: #DC2626;">$599</span>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Final CTA -->
    <section style="padding: 4rem 0; background: linear-gradient(135deg, #DC2626, #E11D48); color: white; text-align: center;">
        <div class="container">
            <h2 style="font-family: Outfit; font-size: 2rem; font-weight: 800; margin-bottom: 1rem;">
                Ready for Junk Removal in ${city.name}?
            </h2>
            <p style="font-size: 1.125rem; margin-bottom: 2rem; opacity: 0.95;">
                Get your free quote in 3 minutes. ${city.operators} operators ready to serve ${city.name}.
            </p>
            <a href="https://app.goumuve.com/book" class="btn" style="background: white; color: #DC2626; padding: 1rem 2rem; font-weight: 700; border-radius: 0.5rem; text-decoration: none; display: inline-block;">
                Book Online Now →
            </a>
        </div>
    </section>

    ${baseFooter}

    <script src="../script.js"></script>
</body>
</html>`;

    return html;
}

// Generate all location pages
console.log('Generating location pages...');
cities.forEach(city => {
    const html = generateLocationPage(city);
    const filename = `${city.slug}-fl.html`;
    const filepath = path.join(__dirname, '../pages/junk-removal', filename);
    fs.writeFileSync(filepath, html);
    console.log(`✓ Generated: pages/junk-removal/${filename}`);
});

console.log(`\n✓ Generated ${cities.length} location pages`);
console.log('\nNext steps:');
console.log('1. Generate service pages (run with --services flag)');
console.log('2. Generate comparison pages (run with --comparisons flag)');
console.log('3. Generate sitemap');
console.log('4. Deploy to production');

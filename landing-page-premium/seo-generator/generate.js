#!/usr/bin/env node

/**
 * Umuve SEO City Page Generator v2
 * Generates 800+ word location pages with:
 * - FAQ schema (FAQPage)
 * - LocalBusiness schema
 * - Service schema + AggregateRating
 * - Breadcrumb schema
 * - Internal linking to nearby cities + service pages
 * - Meta Pixel + GA4 + Google Ads tracking
 * - Unique local content per city
 * - Click-to-call + sticky booking CTA
 */

const fs = require('fs');
const path = require('path');

const cities = require('./data/cities.json');
const services = require('./data/services.json');

// County groupings for internal linking
function getNearbyCities(city, allCities) {
    return allCities
        .filter(c => c.county === city.county && c.slug !== city.slug)
        .slice(0, 6);
}

// Get FAQ for a city
function getCityFAQ(city) {
    return [
        {
            q: `How much does junk removal cost in ${city.name}, FL?`,
            a: `The average junk removal job in ${city.name} costs $${city.avgJobCost}. Single-item pickups start at $89, while full truck loads run up to $599. Pricing depends on volume, item type, and accessibility. Get an instant quote online — no phone call needed.`
        },
        {
            q: `How fast can I get junk picked up in ${city.name}?`,
            a: `Umuve matches you with a local operator in an average of ${city.avgResponseMinutes} minutes. Same-day pickup is available in ${city.name} and throughout ${city.county} County. Book online before noon for same-day service in most cases.`
        },
        {
            q: `What items do you remove in ${city.name}?`,
            a: `We remove furniture, appliances, mattresses, electronics, yard waste, construction debris, hot tubs, and more. The most requested items in ${city.name} are ${city.topItems.join(', ')}. We handle almost everything except hazardous waste, asbestos, and biological materials.`
        },
        {
            q: `Is Umuve licensed and insured in ${city.county} County?`,
            a: `Yes. All Umuve operators serving ${city.name} are licensed, insured, and background-checked. We carry general liability insurance and comply with all ${city.county} County waste disposal regulations.`
        },
        {
            q: `Do you recycle or donate items in ${city.name}?`,
            a: `Absolutely. We partner with local charities including Habitat for Humanity ReStore, Goodwill, and ${city.county} County recycling facilities. On average, 85% of items we collect are donated or recycled rather than sent to landfill.`
        },
        {
            q: `How do I book junk removal in ${city.name}?`,
            a: `Book online at goumuve.com/book in under 3 minutes. Upload photos of your items, pick a time slot, and get instant pricing. No phone calls required. You can also call us at (561) 944-1636.`
        }
    ];
}

// Generate FAQ schema JSON-LD
function generateFAQSchema(faqs) {
    return JSON.stringify({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": faqs.map(faq => ({
            "@type": "Question",
            "name": faq.q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": faq.a
            }
        }))
    }, null, 8);
}

// Generate LocalBusiness schema
function generateLocalBusinessSchema(city) {
    return JSON.stringify({
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": `Umuve Junk Removal — ${city.name}`,
        "image": "https://goumuve.com/logo-full.png",
        "url": `https://goumuve.com/junk-removal/${city.slug}-fl`,
        "telephone": "+15619441636",
        "priceRange": "$$",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": city.name,
            "addressRegion": "FL",
            "addressCountry": "US"
        },
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": city.lat || 26.1,
            "longitude": city.lng || -80.2
        },
        "areaServed": {
            "@type": "City",
            "name": city.name
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": String(city.rating),
            "reviewCount": String(city.reviewCount),
            "bestRating": "5",
            "worstRating": "1"
        },
        "openingHoursSpecification": [
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                "opens": "07:00",
                "closes": "20:00"
            },
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": "Sunday",
                "opens": "08:00",
                "closes": "18:00"
            }
        ]
    }, null, 8);
}

function generateLocationPage(city, allCities) {
    const title = `Junk Removal in ${city.name}, FL — Same-Day Pickup | Umuve`;
    const description = `Professional junk removal in ${city.name}, Florida. ${city.operators} local operators, ${city.jobsCompleted.toLocaleString()}+ jobs completed, ${city.rating}★ rating. Starting at $89. Book online in 3 minutes.`;
    const faqs = getCityFAQ(city);
    const nearbyCities = getNearbyCities(city, allCities);
    const localInfo = city.localInfo || `Professional junk removal services covering all of ${city.name} and surrounding ${city.county} County areas.`;

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="${description}">
    <meta name="robots" content="index, follow">

    <!-- Open Graph -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://goumuve.com/junk-removal/${city.slug}-fl">
    <meta property="og:title" content="${title}">
    <meta property="og:description" content="${description}">
    <meta property="og:image" content="https://goumuve.com/logo-full.png">
    <meta property="og:site_name" content="Umuve">

    <!-- Twitter -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="${title}">
    <meta name="twitter:description" content="${description}">

    <!-- Canonical -->
    <link rel="canonical" href="https://goumuve.com/junk-removal/${city.slug}-fl">

    <title>${title}</title>

    <link rel="stylesheet" href="/styles.css">
    <link rel="icon" type="image/png" href="/logo-icon.png">

    <!-- Google Analytics + Google Ads -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-CLGPJ5TS3G"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', 'G-CLGPJ5TS3G');
    </script>

    <!-- Meta Pixel -->
    <script>
        !function(f,b,e,v,n,t,s)
        {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
        n.callMethod.apply(n,arguments):n.queue.push(arguments)};
        if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
        n.queue=[];t=b.createElement(e);t.async=!0;
        t.src=v;s=b.getElementsByTagName(e)[0];
        s.parentNode.insertBefore(t,s)}(window, document,'script',
        'https://connect.facebook.net/en_US/fbevents.js');
        fbq('init', '1785795592383973');
        fbq('track', 'PageView');
    </script>
    <noscript><img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id=1785795592383973&ev=PageView&noscript=1" alt=""></noscript>

    <!-- Preload fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@700;800;900&display=swap" rel="stylesheet">

    <!-- Structured Data - LocalBusiness -->
    <script type="application/ld+json">
    ${generateLocalBusinessSchema(city)}
    </script>

    <!-- Structured Data - Service -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Service",
        "serviceType": "Junk Removal",
        "provider": {
            "@type": "Organization",
            "name": "Umuve",
            "url": "https://goumuve.com",
            "logo": "https://goumuve.com/logo-full.png"
        },
        "areaServed": {
            "@type": "City",
            "name": "${city.name}",
            "containedIn": {
                "@type": "State",
                "name": "Florida"
            }
        },
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": "Junk Removal Services",
            "itemListElement": [
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Single Item Pickup"}, "price": "89", "priceCurrency": "USD"},
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Quarter Truck Load"}, "price": "149", "priceCurrency": "USD"},
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Half Truck Load"}, "price": "249", "priceCurrency": "USD"},
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Full Truck Load"}, "price": "599", "priceCurrency": "USD"}
            ]
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "${city.rating}",
            "reviewCount": "${city.reviewCount}"
        }
    }
    </script>

    <!-- Structured Data - FAQ -->
    <script type="application/ld+json">
    ${generateFAQSchema(faqs)}
    </script>

    <!-- Structured Data - Breadcrumb -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://goumuve.com"},
            {"@type": "ListItem", "position": 2, "name": "Junk Removal", "item": "https://goumuve.com/junk-removal"},
            {"@type": "ListItem", "position": 3, "name": "${city.name}, FL", "item": "https://goumuve.com/junk-removal/${city.slug}-fl"}
        ]
    }
    </script>

    <style>
        .sticky-cta { position: fixed; bottom: 0; left: 0; right: 0; background: white; padding: 0.75rem 1rem; box-shadow: 0 -4px 20px rgba(0,0,0,0.1); z-index: 999; display: flex; gap: 0.75rem; justify-content: center; align-items: center; }
        .sticky-cta a { padding: 0.75rem 1.5rem; border-radius: 0.5rem; font-weight: 700; text-decoration: none; font-size: 0.95rem; }
        .sticky-cta .book-btn { background: #DC2626; color: white; }
        .sticky-cta .call-btn { background: #f3f4f6; color: #1a1a1a; }
        .faq-item { border: 1px solid rgba(0,0,0,0.08); border-radius: 0.75rem; margin-bottom: 1rem; overflow: hidden; }
        .faq-q { padding: 1.25rem 1.5rem; font-weight: 600; cursor: pointer; display: flex; justify-content: space-between; align-items: center; background: #fafafa; }
        .faq-q:hover { background: #f3f4f6; }
        .faq-a { padding: 0 1.5rem 1.25rem; color: #5c5c5c; line-height: 1.7; }
        .city-link { display: inline-block; padding: 0.5rem 1rem; background: #f9fafb; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.5rem; text-decoration: none; color: #1a1a1a; font-weight: 500; transition: all 0.2s; }
        .city-link:hover { background: #DC2626; color: white; border-color: #DC2626; }
        .service-link { display: inline-block; padding: 0.75rem 1.25rem; background: white; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.75rem; text-decoration: none; color: #1a1a1a; font-weight: 500; transition: all 0.2s; }
        .service-link:hover { border-color: #DC2626; color: #DC2626; }
        @media (max-width: 640px) {
            .sticky-cta { flex-direction: column; }
            .sticky-cta a { width: 100%; text-align: center; }
        }
    </style>
</head>
<body style="padding-bottom: 80px;">
    <!-- Nav -->
    <nav class="navbar" style="position: sticky; top: 0; background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); z-index: 100; border-bottom: 1px solid rgba(0,0,0,0.06);">
        <div class="container">
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem 0;">
                <a href="/" style="display: flex; align-items: center; text-decoration: none;">
                    <img src="/logo-nav.png" alt="Umuve — Hauling Made Simple" style="height: 36px;">
                </a>
                <div style="display: flex; gap: 0.75rem; align-items: center;">
                    <a href="tel:+15619441636" style="color: #1a1a1a; text-decoration: none; font-weight: 600; font-size: 0.9rem;">(561) 944-1636</a>
                    <a href="https://app.goumuve.com/book" class="btn btn-primary" style="padding: 0.6rem 1.25rem; font-size: 0.9rem;">Book Now</a>
                </div>
            </div>
        </div>
    </nav>

    <!-- Breadcrumb -->
    <div style="background: #f9fafb; padding: 0.75rem 0; border-bottom: 1px solid rgba(0,0,0,0.04);">
        <div class="container">
            <nav style="font-size: 0.85rem; color: #8a8a8a;">
                <a href="/" style="color: #5c5c5c; text-decoration: none;">Home</a>
                <span style="margin: 0 0.5rem;">›</span>
                <span style="color: #5c5c5c;">Junk Removal</span>
                <span style="margin: 0 0.5rem;">›</span>
                <span style="color: #1a1a1a; font-weight: 500;">${city.name}, FL</span>
            </nav>
        </div>
    </div>

    <!-- Hero -->
    <section style="padding: 3.5rem 0 3rem; background: linear-gradient(135deg, #f9fafb 0%, #ffffff 100%);">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto; text-align: center;">
                <h1 style="font-family: Outfit, sans-serif; font-size: clamp(2rem, 5vw, 2.75rem); font-weight: 800; margin-bottom: 1.5rem; line-height: 1.15;">
                    Junk Removal in ${city.name}, FL<br>
                    <span style="color: #DC2626;">Same-Day Pickup from $89</span>
                </h1>
                <p style="font-size: 1.15rem; color: #5c5c5c; margin-bottom: 2rem; line-height: 1.6;">
                    ${localInfo} With ${city.operators} local operators and ${city.jobsCompleted.toLocaleString()}+ completed jobs, Umuve is ${city.name}'s most trusted junk removal service. Book online in 3 minutes — no phone call needed.
                </p>
                <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                    <a href="https://app.goumuve.com/book" class="btn btn-primary btn-xl" style="font-size: 1.1rem; padding: 1rem 2rem;">Get Free Quote</a>
                    <a href="tel:+15619441636" class="btn btn-secondary btn-xl" style="font-size: 1.1rem; padding: 1rem 2rem;">Call (561) 944-1636</a>
                </div>
                <p style="margin-top: 1rem; font-size: 0.85rem; color: #8a8a8a;">
                    ${city.rating}★ from ${city.reviewCount} reviews • Licensed & Insured • Eco-Friendly Disposal
                </p>
            </div>
        </div>
    </section>

    <!-- Trust Stats -->
    <section style="padding: 3rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    ${city.name} Junk Removal by the Numbers
                </h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number">${city.operators}</div>
                        <div class="stat-label">Local Operators</div>
                        <div class="stat-source">Ready in ${city.name}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${city.jobsCompleted.toLocaleString()}+</div>
                        <div class="stat-label">Jobs Completed</div>
                        <div class="stat-source">In ${city.county} County</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">$${city.avgJobCost}</div>
                        <div class="stat-label">Average Cost</div>
                        <div class="stat-source">${city.name} average</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${city.avgResponseMinutes} min</div>
                        <div class="stat-label">Response Time</div>
                        <div class="stat-source">Avg. matching time</div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- How It Works -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    How Junk Removal Works in ${city.name}
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2.5rem; font-size: 1.05rem;">
                    Skip the phone tag. Our 3-step process gets your junk gone fast.
                </p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 2rem;">
                    <div style="text-align: center; padding: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626; margin-bottom: 1rem;">01</div>
                        <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.75rem;">Book Online in 3 Minutes</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">Upload photos of your items, pick a date and time, and get instant pricing. No waiting on hold. No home visits needed for a quote.</p>
                    </div>
                    <div style="text-align: center; padding: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626; margin-bottom: 1rem;">02</div>
                        <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.75rem;">We Match You Locally</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">Our system finds the nearest available ${city.name} operator — average match time is ${city.avgResponseMinutes} minutes. You'll get a confirmation with your operator's details.</p>
                    </div>
                    <div style="text-align: center; padding: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626; margin-bottom: 1rem;">03</div>
                        <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.75rem;">We Haul, You Relax</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">Our team handles all the heavy lifting, loading, and hauling. We recycle and donate whenever possible — 85%+ of items stay out of landfills.</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- What We Remove -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    What We Remove in ${city.name}
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    The most requested items from ${city.name} customers are <strong>${city.topItems.join(', ')}</strong>. But we handle almost everything.
                </p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                    ${services.map(s => `
                    <a href="/services/${s.slug}" class="service-link">
                        <strong>${s.name}</strong>
                        <div style="font-size: 0.85rem; color: #8a8a8a; margin-top: 0.25rem;">from $${s.minCost}</div>
                    </a>`).join('')}
                </div>
            </div>
        </div>
    </section>

    <!-- Pricing -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    Junk Removal Pricing in ${city.name}, FL
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    Transparent pricing — what you see is what you pay. All prices include labor, hauling, and eco-friendly disposal. The average job in ${city.name} costs <strong>$${city.avgJobCost}</strong>.
                </p>
                <div style="display: grid; gap: 0.75rem; max-width: 600px; margin: 0 auto;">
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 1.25rem 1.5rem; background: white; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.75rem;">
                        <div><strong>Single Item</strong><br><span style="font-size: 0.85rem; color: #8a8a8a;">1 piece of furniture, appliance, etc.</span></div>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #DC2626;">$89</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 1.25rem 1.5rem; background: white; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.75rem;">
                        <div><strong>1/4 Truck</strong><br><span style="font-size: 0.85rem; color: #8a8a8a;">Small room cleanout, few items</span></div>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #DC2626;">$149</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 1.25rem 1.5rem; background: white; border: 2px solid #DC2626; border-radius: 0.75rem;">
                        <div><strong>1/2 Truck</strong> <span style="background: #DC2626; color: white; padding: 0.15rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; font-weight: 700;">MOST POPULAR</span><br><span style="font-size: 0.85rem; color: #8a8a8a;">Garage cleanout, multiple rooms</span></div>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #DC2626;">$249</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 1.25rem 1.5rem; background: white; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.75rem;">
                        <div><strong>3/4 Truck</strong><br><span style="font-size: 0.85rem; color: #8a8a8a;">Large cleanout, estate items</span></div>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #DC2626;">$399</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 1.25rem 1.5rem; background: white; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.75rem;">
                        <div><strong>Full Truck</strong><br><span style="font-size: 0.85rem; color: #8a8a8a;">Full home or office cleanout</span></div>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #DC2626;">$599</span>
                    </div>
                </div>
                <div style="text-align: center; margin-top: 2rem;">
                    <a href="https://app.goumuve.com/book" class="btn btn-primary btn-xl">Get Your Exact Price</a>
                </div>
            </div>
        </div>
    </section>

    <!-- Neighborhoods -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    ${city.name} Neighborhoods We Serve
                </h2>
                <p style="font-size: 1.05rem; color: #5c5c5c; text-align: center; margin-bottom: 2rem; line-height: 1.6;">
                    Umuve provides junk removal across all of ${city.name}, including <strong>${city.neighborhoods.join('</strong>, <strong>')}</strong>, and the surrounding ${city.county} County area. Our operators know ${city.name}'s streets and can navigate tight driveways, gated communities, and condo buildings. We serve zip codes ${city.zipCodes.join(', ')}.
                </p>
            </div>
        </div>
    </section>

    <!-- Why Umuve -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    Why ${city.name} Residents Choose Umuve
                </h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem;">
                    <div style="background: white; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.06);">
                        <h3 style="font-weight: 700; margin-bottom: 0.5rem;">25% Less Than 1-800-GOT-JUNK</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">No franchise fees means lower overhead. We pass the savings to you. Compare our $89 minimum to their $150+ starting price.</p>
                    </div>
                    <div style="background: white; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.06);">
                        <h3 style="font-weight: 700; margin-bottom: 0.5rem;">Book in 3 Minutes, Not 30</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">Upload photos, get instant pricing, pick your time. No phone tag, no waiting for an in-home estimate. Everything happens online.</p>
                    </div>
                    <div style="background: white; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.06);">
                        <h3 style="font-weight: 700; margin-bottom: 0.5rem;">Local ${city.name} Operators</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">${city.operators} licensed and insured operators right here in ${city.county} County. They know ${city.name}'s neighborhoods and can handle same-day requests.</p>
                    </div>
                    <div style="background: white; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.06);">
                        <h3 style="font-weight: 700; margin-bottom: 0.5rem;">Eco-Friendly Disposal</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">85%+ of items are donated or recycled. We partner with Habitat for Humanity, Goodwill, and ${city.county} County recycling facilities.</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- FAQ -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    Frequently Asked Questions — ${city.name} Junk Removal
                </h2>
                ${faqs.map(faq => `
                <div class="faq-item">
                    <div class="faq-q">
                        <span>${faq.q}</span>
                        <span style="color: #DC2626; font-size: 1.25rem;">+</span>
                    </div>
                    <div class="faq-a">${faq.a}</div>
                </div>`).join('')}
            </div>
        </div>
    </section>

    <!-- Nearby Cities -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    Junk Removal Near ${city.name}
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    We also serve these nearby ${city.county} County cities:
                </p>
                <div style="display: flex; flex-wrap: wrap; gap: 0.75rem; justify-content: center;">
                    ${nearbyCities.map(c => `<a href="/junk-removal/${c.slug}-fl" class="city-link">${c.name}, FL</a>`).join('\n                    ')}
                </div>
            </div>
        </div>
    </section>

    <!-- Final CTA -->
    <section style="padding: 4rem 0; background: linear-gradient(135deg, #DC2626, #B91C1C); color: white; text-align: center;">
        <div class="container">
            <h2 style="font-family: Outfit; font-size: 2rem; font-weight: 800; margin-bottom: 1rem;">
                Ready to Get Rid of Your Junk in ${city.name}?
            </h2>
            <p style="font-size: 1.1rem; margin-bottom: 2rem; opacity: 0.95; max-width: 600px; margin-left: auto; margin-right: auto;">
                Join ${city.jobsCompleted.toLocaleString()}+ ${city.name} customers who chose Umuve. Get your free quote in 3 minutes.
            </p>
            <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                <a href="https://app.goumuve.com/book" style="background: white; color: #DC2626; padding: 1rem 2.5rem; font-weight: 700; border-radius: 0.5rem; text-decoration: none; display: inline-block; font-size: 1.1rem;">Book Online Now</a>
                <a href="tel:+15619441636" style="background: rgba(255,255,255,0.15); color: white; padding: 1rem 2.5rem; font-weight: 700; border-radius: 0.5rem; text-decoration: none; display: inline-block; font-size: 1.1rem; border: 2px solid rgba(255,255,255,0.3);">Call (561) 944-1636</a>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer style="background: #111111; color: white; padding: 3rem 0 5rem;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 2rem;">
                <div>
                    <img src="/logo-nav.png" alt="Umuve" style="height: 32px; filter: brightness(10); margin-bottom: 1rem;">
                    <p style="color: #8a8a8a; font-size: 0.9rem; line-height: 1.6;">Hauling made simple. Professional junk removal across South Florida.</p>
                </div>
                <div>
                    <h4 style="font-weight: 700; margin-bottom: 0.75rem; font-size: 0.9rem;">Services</h4>
                    <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                        ${services.slice(0, 5).map(s => `<a href="/services/${s.slug}" style="color: #8a8a8a; text-decoration: none; font-size: 0.85rem;">${s.name}</a>`).join('\n                        ')}
                    </div>
                </div>
                <div>
                    <h4 style="font-weight: 700; margin-bottom: 0.75rem; font-size: 0.9rem;">Top Cities</h4>
                    <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                        ${nearbyCities.slice(0, 5).map(c => `<a href="/junk-removal/${c.slug}-fl" style="color: #8a8a8a; text-decoration: none; font-size: 0.85rem;">${c.name}, FL</a>`).join('\n                        ')}
                    </div>
                </div>
                <div>
                    <h4 style="font-weight: 700; margin-bottom: 0.75rem; font-size: 0.9rem;">Contact</h4>
                    <div style="display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.85rem;">
                        <a href="tel:+15619441636" style="color: #8a8a8a; text-decoration: none;">(561) 944-1636</a>
                        <a href="mailto:support@goumuve.com" style="color: #8a8a8a; text-decoration: none;">support@goumuve.com</a>
                        <a href="/privacy" style="color: #8a8a8a; text-decoration: none;">Privacy Policy</a>
                        <a href="/terms" style="color: #8a8a8a; text-decoration: none;">Terms of Service</a>
                    </div>
                </div>
            </div>
            <div style="text-align: center; margin-top: 2rem; padding-top: 2rem; border-top: 1px solid rgba(255,255,255,0.1);">
                <p style="color: #5c5c5c; font-size: 0.8rem;">&copy; 2026 Umuve Inc. Licensed & Insured. Serving Miami-Dade, Broward & Palm Beach Counties.</p>
            </div>
        </div>
    </footer>

    <!-- Sticky CTA (Mobile) -->
    <div class="sticky-cta">
        <a href="https://app.goumuve.com/book" class="book-btn">Book Online — From $89</a>
        <a href="tel:+15619441636" class="call-btn">Call Now</a>
    </div>

    <script src="/script.js"></script>
</body>
</html>`;

    return html;
}

// Ensure output directories exist
const junkRemovalDir = path.join(__dirname, '../pages/junk-removal');
if (!fs.existsSync(junkRemovalDir)) {
    fs.mkdirSync(junkRemovalDir, { recursive: true });
}

// Generate all location pages
console.log('Generating location pages...');
cities.forEach(city => {
    const html = generateLocationPage(city, cities);
    const filename = `${city.slug}-fl.html`;
    const filepath = path.join(junkRemovalDir, filename);
    fs.writeFileSync(filepath, html);
    console.log(`  ✓ ${filename}`);
});

console.log(`\n✓ Generated ${cities.length} location pages in pages/junk-removal/`);

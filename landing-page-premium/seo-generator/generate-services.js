#!/usr/bin/env node

/**
 * Umuve SEO Service Page Generator v2
 * Generates service pages with FAQ schema, structured data, internal linking
 */

const fs = require('fs');
const path = require('path');

const services = require('./data/services.json');
const cities = require('./data/cities.json');

// Get top cities for internal linking (one from each county)
function getTopCities() {
    const byCounty = {};
    cities.forEach(c => {
        if (!byCounty[c.county]) byCounty[c.county] = [];
        byCounty[c.county].push(c);
    });
    const top = [];
    Object.values(byCounty).forEach(arr => {
        arr.sort((a, b) => b.population - a.population);
        top.push(...arr.slice(0, 3));
    });
    return top.slice(0, 9);
}

function generateServiceFAQSchema(service) {
    const faqs = service.commonQuestions.map((q, i) => {
        const answers = {
            0: `Yes! ${service.process}`,
            1: `Absolutely. Our operators handle all logistics. ${service.disposal}`,
            2: `We've handled thousands of these situations. With ${service.jobsCompleted}+ jobs completed, our team knows how to manage any challenge.`,
            3: `${service.disposal}`
        };
        return {
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": answers[i] || service.process
            }
        };
    });

    return JSON.stringify({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": faqs
    }, null, 8);
}

function generateServicePage(service) {
    const title = `${service.name} in South Florida — Same-Day Pickup from $${service.minCost} | Umuve`;
    const description = `${service.description} Average cost: $${service.avgCost}. ${service.jobsCompleted.toLocaleString()}+ jobs completed. ${service.ecoFriendly}. Book online in 3 minutes.`;
    const topCities = getTopCities();

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="${description}">
    <meta name="robots" content="index, follow">

    <meta property="og:type" content="website">
    <meta property="og:url" content="https://goumuve.com/services/${service.slug}">
    <meta property="og:title" content="${title}">
    <meta property="og:description" content="${description}">
    <meta property="og:image" content="https://goumuve.com/logo-full.png">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="${title}">

    <link rel="canonical" href="https://goumuve.com/services/${service.slug}">
    <title>${title}</title>
    <link rel="stylesheet" href="/styles.css">
    <link rel="icon" type="image/png" href="/logo-icon.png">

    <!-- Google Analytics -->
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

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@700;800;900&display=swap" rel="stylesheet">

    <!-- Service Schema -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Service",
        "serviceType": "${service.name}",
        "provider": {
            "@type": "Organization",
            "name": "Umuve",
            "url": "https://goumuve.com",
            "logo": "https://goumuve.com/logo-full.png",
            "telephone": "+15619441636"
        },
        "areaServed": {
            "@type": "State",
            "name": "Florida"
        },
        "offers": {
            "@type": "AggregateOffer",
            "lowPrice": "${service.minCost}",
            "highPrice": "${service.maxCost}",
            "priceCurrency": "USD"
        },
        "description": "${service.description}"
    }
    </script>

    <!-- FAQ Schema -->
    <script type="application/ld+json">
    ${generateServiceFAQSchema(service)}
    </script>

    <!-- Breadcrumb Schema -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://goumuve.com"},
            {"@type": "ListItem", "position": 2, "name": "Services", "item": "https://goumuve.com/services"},
            {"@type": "ListItem", "position": 3, "name": "${service.name}", "item": "https://goumuve.com/services/${service.slug}"}
        ]
    }
    </script>

    <style>
        .sticky-cta { position: fixed; bottom: 0; left: 0; right: 0; background: white; padding: 0.75rem 1rem; box-shadow: 0 -4px 20px rgba(0,0,0,0.1); z-index: 999; display: flex; gap: 0.75rem; justify-content: center; align-items: center; }
        .sticky-cta a { padding: 0.75rem 1.5rem; border-radius: 0.5rem; font-weight: 700; text-decoration: none; font-size: 0.95rem; }
        .sticky-cta .book-btn { background: #DC2626; color: white; }
        .sticky-cta .call-btn { background: #f3f4f6; color: #1a1a1a; }
        .faq-item { border: 1px solid rgba(0,0,0,0.08); border-radius: 0.75rem; margin-bottom: 1rem; overflow: hidden; }
        .faq-q { padding: 1.25rem 1.5rem; font-weight: 600; display: flex; justify-content: space-between; align-items: center; background: #fafafa; }
        .faq-a { padding: 0 1.5rem 1.25rem; color: #5c5c5c; line-height: 1.7; }
        .city-link { display: inline-block; padding: 0.5rem 1rem; background: #f9fafb; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.5rem; text-decoration: none; color: #1a1a1a; font-weight: 500; transition: all 0.2s; }
        .city-link:hover { background: #DC2626; color: white; border-color: #DC2626; }
        @media (max-width: 640px) { .sticky-cta { flex-direction: column; } .sticky-cta a { width: 100%; text-align: center; } }
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
                <span style="color: #5c5c5c;">Services</span>
                <span style="margin: 0 0.5rem;">›</span>
                <span style="color: #1a1a1a; font-weight: 500;">${service.name}</span>
            </nav>
        </div>
    </div>

    <!-- Hero -->
    <section style="padding: 3.5rem 0 3rem; background: linear-gradient(135deg, #f9fafb 0%, #ffffff 100%);">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto; text-align: center;">
                <h1 style="font-family: Outfit; font-size: clamp(2rem, 5vw, 2.75rem); font-weight: 800; margin-bottom: 1.5rem; line-height: 1.15;">
                    ${service.name} in South Florida<br>
                    <span style="color: #DC2626;">Starting at $${service.minCost}</span>
                </h1>
                <p style="font-size: 1.15rem; color: #5c5c5c; margin-bottom: 2rem; line-height: 1.6;">
                    ${service.description} With ${service.jobsCompleted.toLocaleString()}+ jobs completed and ${service.ecoFriendly}, we're South Florida's most trusted choice for ${service.name.toLowerCase()}.
                </p>
                <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                    <a href="https://app.goumuve.com/book" class="btn btn-primary btn-xl" style="font-size: 1.1rem; padding: 1rem 2rem;">Get Free Quote</a>
                    <a href="tel:+15619441636" class="btn btn-secondary btn-xl" style="font-size: 1.1rem; padding: 1rem 2rem;">Call (561) 944-1636</a>
                </div>
            </div>
        </div>
    </section>

    <!-- Stats -->
    <section style="padding: 3rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <div class="stats-grid">
                    <div class="stat-card"><div class="stat-number">${service.jobsCompleted.toLocaleString()}+</div><div class="stat-label">Jobs Completed</div></div>
                    <div class="stat-card"><div class="stat-number">$${service.avgCost}</div><div class="stat-label">Average Cost</div></div>
                    <div class="stat-card"><div class="stat-number">${service.avgDuration}</div><div class="stat-label">Average Time</div></div>
                    <div class="stat-card"><div class="stat-number">${service.ecoFriendly}</div><div class="stat-label">Eco-Friendly</div></div>
                </div>
            </div>
        </div>
    </section>

    <!-- What We Remove -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">What We Remove</h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                    ${service.items.map(item => `<div style="padding: 1.25rem; background: white; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.75rem; text-align: center;"><strong>${item}</strong></div>`).join('\n                    ')}
                </div>
            </div>
        </div>
    </section>

    <!-- How It Works -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    How ${service.name} Works
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2.5rem;">
                    ${service.process}
                </p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 2rem;">
                    <div style="text-align: center; padding: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626;">01</div>
                        <h3 style="font-size: 1.2rem; font-weight: 700; margin: 0.75rem 0;">Book Online</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">Upload photos of the items you need removed. Get instant pricing — no phone calls, no in-home estimates.</p>
                    </div>
                    <div style="text-align: center; padding: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626;">02</div>
                        <h3 style="font-size: 1.2rem; font-weight: 700; margin: 0.75rem 0;">We Show Up</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">A local operator arrives at your scheduled time. They handle all lifting, loading, and hauling — you don't touch a thing.</p>
                    </div>
                    <div style="text-align: center; padding: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626;">03</div>
                        <h3 style="font-size: 1.2rem; font-weight: 700; margin: 0.75rem 0;">Eco-Friendly Disposal</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">${service.disposal}</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Pricing -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 600px; margin: 0 auto; text-align: center;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; margin-bottom: 2rem;">${service.name} Pricing</h2>
                <div style="background: white; border: 2px solid #DC2626; border-radius: 1rem; padding: 2.5rem; margin-bottom: 1.5rem;">
                    <div style="font-size: 3.5rem; font-weight: 800; color: #DC2626; margin-bottom: 0.5rem;">$${service.avgCost}</div>
                    <div style="font-size: 1.15rem; color: #5c5c5c;">Average Cost</div>
                    <div style="font-size: 0.9rem; color: #8a8a8a; margin-top: 0.5rem;">Range: $${service.minCost} — $${service.maxCost}</div>
                </div>
                <p style="color: #5c5c5c; margin-bottom: 2rem;">All prices include labor, hauling, and eco-friendly disposal. No hidden fees. Get your exact price online.</p>
                <a href="https://app.goumuve.com/book" class="btn btn-primary btn-xl">Get Your Exact Price</a>
            </div>
        </div>
    </section>

    <!-- Why Umuve -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    Why Choose Umuve for ${service.name}
                </h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem;">
                    <div style="background: #f9fafb; padding: 1.5rem; border-radius: 0.75rem;">
                        <h3 style="font-weight: 700; margin-bottom: 0.5rem;">25% Less Than Competitors</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">No franchise fees = lower prices for you. Our $${service.minCost} starting price beats the big names.</p>
                    </div>
                    <div style="background: #f9fafb; padding: 1.5rem; border-radius: 0.75rem;">
                        <h3 style="font-weight: 700; margin-bottom: 0.5rem;">Same-Day Available</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">Book before noon, get pickup today. Average operator match time under 30 minutes across South Florida.</p>
                    </div>
                    <div style="background: #f9fafb; padding: 1.5rem; border-radius: 0.75rem;">
                        <h3 style="font-weight: 700; margin-bottom: 0.5rem;">${service.ecoFriendly}</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">${service.disposal}</p>
                    </div>
                    <div style="background: #f9fafb; padding: 1.5rem; border-radius: 0.75rem;">
                        <h3 style="font-weight: 700; margin-bottom: 0.5rem;">Licensed & Insured</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">All operators are vetted, insured, and experienced. ${service.jobsCompleted.toLocaleString()}+ ${service.name.toLowerCase()} jobs completed.</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- FAQ -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    Frequently Asked Questions — ${service.name}
                </h2>
                ${service.commonQuestions.map((q, i) => {
                    const answers = [
                        service.process,
                        `Absolutely. Our operators handle all logistics, including stairs, tight spaces, and heavy items. ${service.disposal}`,
                        `We've handled thousands of these situations. With ${service.jobsCompleted.toLocaleString()}+ jobs completed, our team knows how to manage any challenge. Book online and include photos so we can prepare.`,
                        service.disposal
                    ];
                    return `
                <div class="faq-item">
                    <div class="faq-q">
                        <span>${q}</span>
                        <span style="color: #DC2626; font-size: 1.25rem;">+</span>
                    </div>
                    <div class="faq-a">${answers[i] || service.process}</div>
                </div>`;
                }).join('')}
            </div>
        </div>
    </section>

    <!-- Service Areas -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    ${service.name} Service Areas
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    We provide ${service.name.toLowerCase()} across Miami-Dade, Broward, and Palm Beach counties.
                </p>
                <div style="display: flex; flex-wrap: wrap; gap: 0.75rem; justify-content: center;">
                    ${topCities.map(c => `<a href="/junk-removal/${c.slug}-fl" class="city-link">${c.name}, FL</a>`).join('\n                    ')}
                </div>
            </div>
        </div>
    </section>

    <!-- Other Services -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-family: Outfit; font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    Other Services
                </h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                    ${services.filter(s => s.slug !== service.slug).map(s => `
                    <a href="/services/${s.slug}" style="display: block; padding: 1.25rem; background: white; border: 1px solid rgba(0,0,0,0.08); border-radius: 0.75rem; text-decoration: none; color: #1a1a1a; transition: all 0.2s;">
                        <strong>${s.name}</strong>
                        <div style="font-size: 0.85rem; color: #8a8a8a; margin-top: 0.25rem;">from $${s.minCost}</div>
                    </a>`).join('')}
                </div>
            </div>
        </div>
    </section>

    <!-- Final CTA -->
    <section style="padding: 4rem 0; background: linear-gradient(135deg, #DC2626, #B91C1C); color: white; text-align: center;">
        <div class="container">
            <h2 style="font-family: Outfit; font-size: 2rem; font-weight: 800; margin-bottom: 1rem;">
                Ready for ${service.name}?
            </h2>
            <p style="font-size: 1.1rem; margin-bottom: 2rem; opacity: 0.95; max-width: 600px; margin-left: auto; margin-right: auto;">
                Join ${service.jobsCompleted.toLocaleString()}+ customers. Book online in 3 minutes, starting at $${service.minCost}.
            </p>
            <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                <a href="https://app.goumuve.com/book" style="background: white; color: #DC2626; padding: 1rem 2.5rem; font-weight: 700; border-radius: 0.5rem; text-decoration: none; font-size: 1.1rem;">Book Online Now</a>
                <a href="tel:+15619441636" style="background: rgba(255,255,255,0.15); color: white; padding: 1rem 2.5rem; font-weight: 700; border-radius: 0.5rem; text-decoration: none; font-size: 1.1rem; border: 2px solid rgba(255,255,255,0.3);">Call (561) 944-1636</a>
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
                        ${topCities.slice(0, 5).map(c => `<a href="/junk-removal/${c.slug}-fl" style="color: #8a8a8a; text-decoration: none; font-size: 0.85rem;">${c.name}, FL</a>`).join('\n                        ')}
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

    <!-- Sticky CTA -->
    <div class="sticky-cta">
        <a href="https://app.goumuve.com/book" class="book-btn">Book Online — From $${service.minCost}</a>
        <a href="tel:+15619441636" class="call-btn">Call Now</a>
    </div>

    <script src="/script.js"></script>
</body>
</html>`;
    return html;
}

// Ensure output directory exists
const servicesDir = path.join(__dirname, '../pages/services');
if (!fs.existsSync(servicesDir)) {
    fs.mkdirSync(servicesDir, { recursive: true });
}

console.log('Generating service pages...');
services.forEach(service => {
    const html = generateServicePage(service);
    const filepath = path.join(servicesDir, `${service.slug}.html`);
    fs.writeFileSync(filepath, html);
    console.log(`  ✓ ${service.slug}.html`);
});

console.log(`\n✓ Generated ${services.length} service pages in pages/services/`);

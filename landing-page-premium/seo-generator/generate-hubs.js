#!/usr/bin/env node
/**
 * Phase 6: Hub/Pillar Pages Generator
 * Generates services/index.html, locations/index.html, guides/index.html, pricing.html
 */

const fs = require('fs');
const path = require('path');

const BASE_DIR = path.join(__dirname, '..');

const HEAD = (title, desc, canonical, extraSchema) => `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="${desc}">
<meta name="robots" content="index, follow">
<meta property="og:type" content="website">
<meta property="og:url" content="https://goumuve.com${canonical}">
<meta property="og:title" content="${title}">
<meta property="og:description" content="${desc}">
<meta property="og:image" content="https://goumuve.com/logo-full.png">
<meta property="og:site_name" content="Umuve">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${title}">
<meta name="twitter:description" content="${desc}">
<link rel="canonical" href="https://goumuve.com${canonical}">
<title>${title}</title>
<link rel="stylesheet" href="/styles.css">
<link rel="icon" type="image/png" href="/logo-icon.png">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-CLGPJ5TS3G"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-CLGPJ5TS3G');</script>
<script>!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init','1432514091446263');fbq('track','PageView');</script>
<noscript><img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id=1432514091446263&ev=PageView&noscript=1" alt="Facebook Pixel"></noscript>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@700;800;900&display=swap" rel="stylesheet">
${extraSchema}
</head>`;

const NAV = () => `<nav class="navbar" style="position:sticky;top:0;background:rgba(255,255,255,0.95);backdrop-filter:blur(10px);z-index:100;border-bottom:1px solid rgba(0,0,0,0.06)">
<div class="container"><div style="display:flex;justify-content:space-between;align-items:center;padding:1rem 0">
<a href="/"><img src="/logo-nav.png" alt="Umuve — Same-Day Junk Removal in South Florida" width="120" height="36" loading="eager"></a>
<div style="display:flex;gap:1rem;align-items:center">
<a href="tel:5619441636" style="color:#374151;font-weight:600;text-decoration:none;font-size:0.9rem;display:none" id="navPhone">(561) 944-1636</a>
<a href="https://app.goumuve.com/book" class="btn btn-primary">Book Now</a>
</div>
</div></div></nav>`;

const FOOTER = () => `<footer style="background:#111827;color:#9ca3af;padding:3rem 0;margin-top:4rem">
<div class="container">
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:2rem;margin-bottom:2rem">
<div>
<img src="/logo-nav.png" alt="Umuve — Hauling Made Simple" width="107" height="32" loading="lazy" style="margin-bottom:1rem;filter:brightness(0) invert(1)">
<p style="font-size:0.8rem;line-height:1.6">South Florida's junk removal platform. 500+ local operators.</p>
</div>
<div>
<p style="font-weight:600;color:#fff;margin-bottom:0.5rem;font-size:0.875rem">Services</p>
<ul style="list-style:none;padding:0;margin:0">
<li><a href="/services" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">All Services</a></li>
<li><a href="/services/furniture-removal" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">Furniture Removal</a></li>
<li><a href="/services/appliance-removal" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">Appliance Removal</a></li>
<li><a href="/services/estate-cleanout" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">Estate Cleanout</a></li>
<li><a href="/commercial" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">Commercial Services</a></li>
</ul>
</div>
<div>
<p style="font-weight:600;color:#fff;margin-bottom:0.5rem;font-size:0.875rem">Cities</p>
<ul style="list-style:none;padding:0;margin:0">
<li><a href="/locations" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">All Locations</a></li>
<li><a href="/junk-removal/west-palm-beach-fl" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">West Palm Beach</a></li>
<li><a href="/junk-removal/fort-lauderdale-fl" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">Fort Lauderdale</a></li>
<li><a href="/junk-removal/miami-fl" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">Miami</a></li>
<li><a href="/junk-removal/boca-raton-fl" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">Boca Raton</a></li>
</ul>
</div>
<div>
<p style="font-weight:600;color:#fff;margin-bottom:0.5rem;font-size:0.875rem">Resources</p>
<ul style="list-style:none;padding:0;margin:0">
<li><a href="/guides" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">Guides</a></li>
<li><a href="/pricing" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">Pricing</a></li>
<li><a href="/vs/umuve-vs-1800-got-junk" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">Comparisons</a></li>
<li><a href="/privacy" style="color:#9ca3af;text-decoration:none;font-size:0.8rem;display:block;margin-bottom:0.3rem">Privacy Policy</a></li>
</ul>
</div>
</div>
<div style="border-top:1px solid #374151;padding-top:1.25rem;font-size:0.8rem;display:flex;flex-wrap:wrap;justify-content:space-between;gap:0.5rem">
<p style="margin:0">&copy; 2026 Umuve. All rights reserved.</p>
<a href="https://app.goumuve.com/book" style="color:#DC2626;text-decoration:none;font-weight:600">Book Now &rarr;</a>
</div>
</div>
</footer>`;

// ---- SERVICES HUB ----
const SERVICES = [
  { slug: 'furniture-removal', name: 'Furniture Removal', desc: 'Couches, dressers, tables, chairs, mattresses, and all household furniture.', price: 'from $89', jobs: '4,820+' },
  { slug: 'appliance-removal', name: 'Appliance Removal', desc: 'Refrigerators, washers, dryers, stoves, dishwashers, and all appliances.', price: 'from $89', jobs: '3,240+' },
  { slug: 'mattress-disposal', name: 'Mattress Disposal', desc: 'Twin, full, queen, and king mattresses. 89% recycled.', price: 'from $89', jobs: '2,180+' },
  { slug: 'estate-cleanout', name: 'Estate Cleanout', desc: 'Full home, apartment, and storage unit cleanouts. Handled with care.', price: 'from $399', jobs: '890+' },
  { slug: 'construction-debris', name: 'Construction Debris', desc: 'Drywall, lumber, tile, concrete, and all renovation waste.', price: 'from $149', jobs: '1,650+' },
  { slug: 'hot-tub-removal', name: 'Hot Tub Removal', desc: 'Above-ground and in-ground hot tubs, spas, and saunas.', price: 'from $299', jobs: '340+' },
  { slug: 'yard-waste-removal', name: 'Yard Waste Removal', desc: 'Tree branches, brush, palm fronds, leaves, and landscaping debris.', price: 'from $89', jobs: '1,870+' },
  { slug: 'electronics-recycling', name: 'Electronics Recycling', desc: 'TVs, computers, monitors, printers, and all e-waste. R2-certified disposal.', price: 'from $89', jobs: '1,420+' },
  { slug: 'garage-cleanout', name: 'Garage Cleanout', desc: 'Single and double car garages cleared completely. Swept clean after.', price: 'from $149', jobs: '1,340+' },
  { slug: 'office-commercial-cleanout', name: 'Office &amp; Commercial', desc: 'Office floors, retail spaces, and warehouses. After-hours available.', price: 'from $299', jobs: '620+' },
];

const COMMERCIAL_SERVICES_HUB = [
  { slug: 'commercial/office-cleanout', name: 'Office Cleanout', desc: 'Desks, cubicles, chairs, filing cabinets, IT equipment.', price: 'from $299' },
  { slug: 'commercial/retail-store-cleanout', name: 'Retail Store Cleanout', desc: 'Display fixtures, shelving, POS systems, inventory.', price: 'from $399' },
  { slug: 'commercial/construction-debris', name: 'Construction Debris (Commercial)', desc: 'Jobsite cleanup, contractor accounts, recurring scheduling.', price: 'from $249' },
  { slug: 'commercial/restaurant-cleanout', name: 'Restaurant Cleanout', desc: 'Commercial kitchen equipment, booths, walk-in coolers.', price: 'from $499' },
  { slug: 'commercial/warehouse-cleanout', name: 'Warehouse Cleanout', desc: 'Pallet racking, industrial equipment, large-scale projects.', price: 'from $599' },
  { slug: 'commercial/property-management', name: 'Property Management', desc: 'Unit turnovers, eviction cleanouts, common area clearing.', price: 'from $199' },
  { slug: 'commercial/hoa-services', name: 'HOA Services', desc: 'Bulk collection programs, common areas, clubhouse cleanouts.', price: 'from $199' },
];

function generateServicesHub() {
  const canonical = '/services';
  const title = 'All Junk Removal Services in South Florida | Umuve';
  const desc = 'Browse all 17 junk removal services offered by Umuve across South Florida. Furniture, appliances, estates, construction debris, commercial cleanouts, and more. Same-day available. Starting at $89.';

  const schema = `<script type="application/ld+json">{"@context":"https://schema.org","@type":"ItemList","name":"Umuve Junk Removal Services","description":"Complete list of junk removal services available across South Florida","url":"https://goumuve.com/services","numberOfItems":17}</script>`;

  const faqSchema = `<script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
{"@type":"Question","name":"What junk removal services does Umuve offer?","acceptedAnswer":{"@type":"Answer","text":"Umuve offers 17 junk removal services including furniture removal, appliance removal, mattress disposal, estate cleanouts, construction debris, hot tub removal, yard waste, electronics recycling, garage cleanouts, and commercial services. All services are available across 42 South Florida cities."}},
{"@type":"Question","name":"What is the minimum price for junk removal with Umuve?","acceptedAnswer":{"@type":"Answer","text":"Umuve starts at $89 for single-item pickup. Most residential jobs run $149-499. Estate cleanouts and commercial jobs start higher based on volume."}},
{"@type":"Question","name":"Do you offer same-day junk removal?","acceptedAnswer":{"@type":"Answer","text":"Yes. Same-day service is available for approximately 67% of bookings across South Florida. Book online and select same-day or next-day availability."}}
]}</script>`;

  return `${HEAD(title, desc, canonical, schema + '\n' + faqSchema)}
<body>
${NAV()}

<!-- Hero -->
<section style="padding:4rem 0 3rem;background:linear-gradient(135deg,#f9fafb 0%,#fff 100%)">
<div class="container">
<nav style="margin-bottom:1.25rem;font-size:0.85rem;color:#6b7280">
<a href="/" style="color:#DC2626;text-decoration:none">Home</a> &rsaquo; <span>All Services</span>
</nav>
<h1 style="font-family:Outfit;font-size:clamp(2rem,4vw,3rem);font-weight:800;margin-bottom:1rem;line-height:1.2">Junk Removal Services in South Florida</h1>
<p style="font-size:1.1rem;color:#5c5c5c;margin-bottom:2rem;max-width:700px;line-height:1.7">17 services. 42 cities. 500+ local operators. Same-day available. All pricing is transparent — see your estimate before you book.</p>
<div style="display:flex;flex-wrap:wrap;gap:1rem">
<a href="https://app.goumuve.com/book" style="background:#DC2626;color:#fff;padding:1rem 2rem;font-weight:700;border-radius:0.5rem;text-decoration:none">Book Now — From $89</a>
<a href="/pricing" style="background:#fff;color:#374151;padding:1rem 2rem;font-weight:600;border-radius:0.5rem;text-decoration:none;border:1px solid rgba(0,0,0,0.15)">View Full Pricing</a>
</div>
</div></section>

<!-- Stats Bar -->
<section style="background:#DC2626;padding:1.5rem 0">
<div class="container"><div style="display:flex;flex-wrap:wrap;gap:2rem;align-items:center;justify-content:center">
${[['17', 'Services offered'],['42', 'South FL cities'],['500+', 'Local operators'],['$89', 'Starting price']].map(([n, l]) => `<div style="text-align:center"><div style="font-size:1.5rem;font-weight:800;color:#fff;font-family:Outfit">${n}</div><div style="font-size:0.8rem;color:rgba(255,255,255,0.85)">${l}</div></div>`).join('<div style="width:1px;height:36px;background:rgba(255,255,255,0.3)"></div>')}
</div></div></section>

<!-- Residential Services -->
<section style="padding:4rem 0">
<div class="container">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.5rem">Residential Services</h2>
<p style="color:#6b7280;margin-bottom:2.5rem">All-inclusive pricing. We handle all loading, hauling, and eco-friendly disposal.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1.5rem">
${SERVICES.map(s => `<a href="/services/${s.slug}" style="text-decoration:none;color:inherit">
<div style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:1rem;padding:1.75rem;transition:box-shadow 0.2s" onmouseover="this.style.boxShadow='0 8px 25px rgba(0,0,0,0.1)'" onmouseout="this.style.boxShadow='none'">
<h3 style="font-family:Outfit;font-size:1.1rem;font-weight:700;margin:0 0 0.6rem;color:#1f2937">${s.name}</h3>
<p style="color:#6b7280;font-size:0.875rem;margin:0 0 1rem;line-height:1.6">${s.desc}</p>
<div style="display:flex;justify-content:space-between;align-items:center">
<span style="color:#DC2626;font-weight:700;font-size:0.875rem">${s.price}</span>
<span style="color:#6b7280;font-size:0.8rem">${s.jobs} jobs done</span>
</div>
</div>
</a>`).join('\n')}
</div>
</div></section>

<!-- Commercial Services -->
<section style="padding:4rem 0;background:#f9fafb">
<div class="container">
<div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;margin-bottom:2.5rem;gap:1rem">
<div>
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.5rem">Commercial Services</h2>
<p style="color:#6b7280;margin:0">Insured. After-hours available. Certificate of removal provided.</p>
</div>
<a href="/commercial" style="background:#1e3a5f;color:#fff;padding:0.75rem 1.5rem;border-radius:0.5rem;text-decoration:none;font-weight:600;font-size:0.875rem;white-space:nowrap">View All Commercial &rarr;</a>
</div>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1.25rem">
${COMMERCIAL_SERVICES_HUB.map(s => `<a href="/${s.slug}" style="text-decoration:none;color:inherit">
<div style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:0.75rem;padding:1.5rem;border-left:3px solid #1e3a5f;transition:box-shadow 0.2s" onmouseover="this.style.boxShadow='0 4px 15px rgba(0,0,0,0.1)'" onmouseout="this.style.boxShadow='none'">
<h3 style="font-family:Outfit;font-size:1rem;font-weight:700;margin:0 0 0.5rem;color:#1e3a5f">${s.name}</h3>
<p style="color:#6b7280;font-size:0.825rem;margin:0 0 0.75rem;line-height:1.5">${s.desc}</p>
<span style="color:#DC2626;font-weight:700;font-size:0.825rem">${s.price}</span>
</div>
</a>`).join('\n')}
</div>
</div></section>

<!-- How It Works -->
<section style="padding:4rem 0">
<div class="container"><div style="max-width:800px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:2rem;text-align:center">How Umuve Works</h2>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1.5rem">
${[['1. Book Online', 'Choose your service, get an instant estimate, and confirm your booking in 3 minutes.'],['2. We Show Up', 'A local operator arrives at your scheduled time — often the same day.'],['3. We Handle Everything', 'All loading, hauling, and disposal included. You do not lift a thing.'],['4. Done', 'Your space is cleared. 87% of what we haul is recycled or donated.']].map(([t, d]) => `<div style="text-align:center;padding:1.5rem">
<div style="font-family:Outfit;font-size:1.1rem;font-weight:700;color:#DC2626;margin-bottom:0.5rem">${t}</div>
<p style="color:#6b7280;font-size:0.9rem;margin:0;line-height:1.6">${d}</p>
</div>`).join('\n')}
</div>
</div></div></section>

<!-- CTA -->
<section style="padding:4rem 0;background:linear-gradient(135deg,#DC2626,#E11D48);color:#fff;text-align:center">
<div class="container">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:1rem">Not Sure Which Service You Need?</h2>
<p style="font-size:1.125rem;margin-bottom:2rem;opacity:0.95">Just tell us what you have and we will quote the right service. No commitment to book.</p>
<a href="https://app.goumuve.com/book" style="background:#fff;color:#DC2626;padding:1rem 2.5rem;font-weight:700;border-radius:0.5rem;text-decoration:none;font-size:1.05rem">Get a Free Estimate</a>
</div></section>

<!-- FAQ -->
<section style="padding:4rem 0">
<div class="container"><div style="max-width:800px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:1.75rem;font-weight:800;margin-bottom:1.5rem">Service FAQs</h2>
<div style="display:grid;gap:1rem">
${[
  {q:'What junk removal services does Umuve offer?', a:'Umuve offers 17 junk removal services including furniture removal, appliance removal, mattress disposal, estate cleanouts, construction debris, hot tub removal, yard waste, electronics recycling, garage cleanouts, and full commercial services. All services are available across 42 South Florida cities.'},
  {q:'What is the minimum price?', a:'Umuve starts at $89 for single-item pickup. Most residential jobs run $149-499. Estate cleanouts and commercial jobs start higher based on volume. See our full pricing page for service-by-service breakdowns.'},
  {q:'Do you offer same-day junk removal?', a:'Yes. Same-day service is available for approximately 67% of bookings across South Florida. Book online and select same-day or next-day availability.'},
  {q:'Are your services eco-friendly?', a:'Yes. Umuve recycles or donates 87% of everything we haul. We partner with Habitat for Humanity, Goodwill, R2-certified e-waste recyclers, and composting facilities across South Florida.'}
].map(f => `<div style="background:#f9fafb;border:1px solid rgba(0,0,0,0.08);border-radius:0.75rem;padding:1.5rem">
<h3 style="font-family:Outfit;font-size:1rem;font-weight:700;margin:0 0 0.5rem">${f.q}</h3>
<p style="color:#6b7280;margin:0;line-height:1.7">${f.a}</p>
</div>`).join('\n')}
</div>
</div></div></section>

${FOOTER()}
</body>
</html>`;
}

// ---- LOCATIONS HUB ----
const CITIES = [
  { slug: 'west-palm-beach-fl', name: 'West Palm Beach', county: 'Palm Beach', operators: 87, jobs: '2,840+' },
  { slug: 'boca-raton-fl', name: 'Boca Raton', county: 'Palm Beach', operators: 72, jobs: '2,100+' },
  { slug: 'delray-beach-fl', name: 'Delray Beach', county: 'Palm Beach', operators: 54, jobs: '1,560+' },
  { slug: 'boynton-beach-fl', name: 'Boynton Beach', county: 'Palm Beach', operators: 49, jobs: '1,340+' },
  { slug: 'palm-beach-gardens-fl', name: 'Palm Beach Gardens', county: 'Palm Beach', operators: 45, jobs: '1,180+' },
  { slug: 'jupiter-fl', name: 'Jupiter', county: 'Palm Beach', operators: 38, jobs: '980+' },
  { slug: 'wellington-fl', name: 'Wellington', county: 'Palm Beach', operators: 34, jobs: '840+' },
  { slug: 'lake-worth-fl', name: 'Lake Worth', county: 'Palm Beach', operators: 31, jobs: '760+' },
  { slug: 'greenacres-fl', name: 'Greenacres', county: 'Palm Beach', operators: 28, jobs: '620+' },
  { slug: 'royal-palm-beach-fl', name: 'Royal Palm Beach', county: 'Palm Beach', operators: 26, jobs: '580+' },
  { slug: 'riviera-beach-fl', name: 'Riviera Beach', county: 'Palm Beach', operators: 24, jobs: '520+' },
  { slug: 'lantana-fl', name: 'Lantana', county: 'Palm Beach', operators: 20, jobs: '420+' },
  { slug: 'fort-lauderdale-fl', name: 'Fort Lauderdale', county: 'Broward', operators: 94, jobs: '3,120+' },
  { slug: 'hollywood-fl', name: 'Hollywood', county: 'Broward', operators: 71, jobs: '2,240+' },
  { slug: 'coral-springs-fl', name: 'Coral Springs', county: 'Broward', operators: 64, jobs: '1,980+' },
  { slug: 'pompano-beach-fl', name: 'Pompano Beach', county: 'Broward', operators: 58, jobs: '1,740+' },
  { slug: 'miramar-fl', name: 'Miramar', county: 'Broward', operators: 55, jobs: '1,640+' },
  { slug: 'pembroke-pines-fl', name: 'Pembroke Pines', county: 'Broward', operators: 52, jobs: '1,560+' },
  { slug: 'davie-fl', name: 'Davie', county: 'Broward', operators: 46, jobs: '1,320+' },
  { slug: 'plantation-fl', name: 'Plantation', county: 'Broward', operators: 43, jobs: '1,240+' },
  { slug: 'sunrise-fl', name: 'Sunrise', county: 'Broward', operators: 40, jobs: '1,100+' },
  { slug: 'weston-fl', name: 'Weston', county: 'Broward', operators: 36, jobs: '960+' },
  { slug: 'deerfield-beach-fl', name: 'Deerfield Beach', county: 'Broward', operators: 34, jobs: '880+' },
  { slug: 'hallandale-beach-fl', name: 'Hallandale Beach', county: 'Broward', operators: 31, jobs: '780+' },
  { slug: 'tamarac-fl', name: 'Tamarac', county: 'Broward', operators: 29, jobs: '720+' },
  { slug: 'cooper-city-fl', name: 'Cooper City', county: 'Broward', operators: 24, jobs: '580+' },
  { slug: 'coconut-creek-fl', name: 'Coconut Creek', county: 'Broward', operators: 22, jobs: '520+' },
  { slug: 'miami-fl', name: 'Miami', county: 'Miami-Dade', operators: 108, jobs: '3,840+' },
  { slug: 'miami-beach-fl', name: 'Miami Beach', county: 'Miami-Dade', operators: 78, jobs: '2,680+' },
  { slug: 'hialeah-fl', name: 'Hialeah', county: 'Miami-Dade', operators: 65, jobs: '2,120+' },
  { slug: 'doral-fl', name: 'Doral', county: 'Miami-Dade', operators: 58, jobs: '1,840+' },
  { slug: 'coral-gables-fl', name: 'Coral Gables', county: 'Miami-Dade', operators: 52, jobs: '1,640+' },
  { slug: 'north-miami-fl', name: 'North Miami', county: 'Miami-Dade', operators: 47, jobs: '1,420+' },
  { slug: 'north-miami-beach-fl', name: 'North Miami Beach', county: 'Miami-Dade', operators: 44, jobs: '1,300+' },
  { slug: 'homestead-fl', name: 'Homestead', county: 'Miami-Dade', operators: 38, jobs: '1,080+' },
  { slug: 'miami-gardens-fl', name: 'Miami Gardens', county: 'Miami-Dade', operators: 36, jobs: '980+' },
  { slug: 'miami-lakes-fl', name: 'Miami Lakes', county: 'Miami-Dade', operators: 31, jobs: '820+' },
  { slug: 'kendall-fl', name: 'Kendall', county: 'Miami-Dade', operators: 34, jobs: '900+' },
  { slug: 'aventura-fl', name: 'Aventura', county: 'Miami-Dade', operators: 29, jobs: '760+' },
  { slug: 'cutler-bay-fl', name: 'Cutler Bay', county: 'Miami-Dade', operators: 26, jobs: '660+' },
  { slug: 'pinecrest-fl', name: 'Pinecrest', county: 'Miami-Dade', operators: 23, jobs: '580+' },
  { slug: 'key-biscayne-fl', name: 'Key Biscayne', county: 'Miami-Dade', operators: 18, jobs: '420+' },
];

function generateLocationsHub() {
  const canonical = '/locations';
  const title = 'Junk Removal Service Areas in South Florida — 42 Cities | Umuve';
  const desc = 'Umuve serves 42 cities across Palm Beach, Broward, and Miami-Dade counties. Find junk removal service in your city. 500+ local operators. Same-day available. Starts at $89.';

  const palmBeach = CITIES.filter(c => c.county === 'Palm Beach');
  const broward = CITIES.filter(c => c.county === 'Broward');
  const miamiDade = CITIES.filter(c => c.county === 'Miami-Dade');

  const schema = `<script type="application/ld+json">{"@context":"https://schema.org","@type":"ItemList","name":"Umuve Service Areas in South Florida","numberOfItems":42,"url":"https://goumuve.com/locations"}</script>`;

  const faqSchema = `<script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
{"@type":"Question","name":"What cities does Umuve serve in South Florida?","acceptedAnswer":{"@type":"Answer","text":"Umuve serves 42 cities across Palm Beach County (12 cities), Broward County (15 cities), and Miami-Dade County (15 cities). Major cities include West Palm Beach, Boca Raton, Fort Lauderdale, Hollywood, Miami, and Miami Beach."}},
{"@type":"Question","name":"Is same-day junk removal available in all cities?","acceptedAnswer":{"@type":"Answer","text":"Same-day service is available in most cities. Availability depends on operator schedules in your specific city. Book online and select same-day availability to see open slots."}}
]}</script>`;

  const countyBlock = (county, cities, color) => `<div>
<h3 style="font-family:Outfit;font-size:1.25rem;font-weight:700;margin-bottom:1rem;color:${color};padding-bottom:0.5rem;border-bottom:2px solid ${color}">${county} County (${cities.length} cities)</h3>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:0.75rem">
${cities.map(c => `<a href="/junk-removal/${c.slug}" style="text-decoration:none;color:inherit">
<div style="padding:1rem 1.25rem;background:#fff;border-radius:0.75rem;border:1px solid rgba(0,0,0,0.08);transition:box-shadow 0.15s" onmouseover="this.style.boxShadow='0 4px 12px rgba(0,0,0,0.1)'" onmouseout="this.style.boxShadow='none'">
<p style="font-weight:600;color:#1f2937;margin:0 0 0.25rem;font-size:0.9rem">${c.name}</p>
<p style="color:#6b7280;font-size:0.75rem;margin:0">${c.operators} operators &middot; ${c.jobs} jobs</p>
</div>
</a>`).join('\n')}
</div>
</div>`;

  return `${HEAD(title, desc, canonical, schema + '\n' + faqSchema)}
<body>
${NAV()}

<!-- Hero -->
<section style="padding:4rem 0 3rem;background:linear-gradient(135deg,#f9fafb 0%,#fff 100%)">
<div class="container">
<nav style="margin-bottom:1.25rem;font-size:0.85rem;color:#6b7280">
<a href="/" style="color:#DC2626;text-decoration:none">Home</a> &rsaquo; <span>Service Areas</span>
</nav>
<h1 style="font-family:Outfit;font-size:clamp(2rem,4vw,3rem);font-weight:800;margin-bottom:1rem;line-height:1.2">Junk Removal Service Areas in South Florida</h1>
<p style="font-size:1.1rem;color:#5c5c5c;margin-bottom:1.5rem;max-width:700px;line-height:1.7">Umuve serves 42 cities across Palm Beach, Broward, and Miami-Dade counties. Over 500 local operators ready for same-day pickup.</p>
<div style="display:flex;flex-wrap:wrap;gap:1rem;margin-bottom:2rem">
<a href="https://app.goumuve.com/book" style="background:#DC2626;color:#fff;padding:1rem 2rem;font-weight:700;border-radius:0.5rem;text-decoration:none">Book in Your City</a>
<a href="/pricing" style="background:#fff;color:#374151;padding:1rem 2rem;font-weight:600;border-radius:0.5rem;text-decoration:none;border:1px solid rgba(0,0,0,0.12)">View Pricing</a>
</div>
<div style="display:flex;flex-wrap:wrap;gap:1.5rem">
${[['42', 'Cities covered'],['500+', 'Local operators'],['3 Counties', 'Palm Beach, Broward, Miami-Dade'],['Same-Day', 'Available most cities']].map(([n, l]) => `<div><span style="font-family:Outfit;font-weight:800;color:#DC2626;font-size:1.25rem">${n}</span> <span style="color:#6b7280;font-size:0.875rem">${l}</span></div>`).join('')}
</div>
</div></section>

<!-- City Lists by County -->
<section style="padding:4rem 0">
<div class="container">
<div style="display:grid;gap:3rem">
${countyBlock('Palm Beach', palmBeach, '#DC2626')}
${countyBlock('Broward', broward, '#1e40af')}
${countyBlock('Miami-Dade', miamiDade, '#059669')}
</div>
</div></section>

<!-- What We Offer In Every City -->
<section style="padding:4rem 0;background:#f9fafb">
<div class="container"><div style="max-width:800px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:1rem;text-align:center">What's Available in Every City</h2>
<p style="color:#6b7280;text-align:center;margin-bottom:2rem">Every Umuve service is available across all 42 cities — subject to same-day operator availability.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:1rem">
${['Furniture Removal', 'Appliance Removal', 'Mattress Disposal', 'Estate Cleanout', 'Construction Debris', 'Garage Cleanout', 'Yard Waste', 'Electronics Recycling', 'Hot Tub Removal', 'Office Cleanout'].map(s => `<div style="padding:0.875rem;background:#fff;border-radius:0.5rem;border:1px solid rgba(0,0,0,0.08);text-align:center;font-size:0.85rem;font-weight:500;color:#374151">${s}</div>`).join('\n')}
</div>
</div></div></section>

<!-- CTA -->
<section style="padding:4rem 0;background:linear-gradient(135deg,#DC2626,#E11D48);color:#fff;text-align:center">
<div class="container">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:1rem">Find Service in Your City</h2>
<p style="font-size:1.125rem;margin-bottom:2rem;opacity:0.95">Book online and get an instant price estimate. Same-day service available in most South Florida cities.</p>
<a href="https://app.goumuve.com/book" style="background:#fff;color:#DC2626;padding:1rem 2.5rem;font-weight:700;border-radius:0.5rem;text-decoration:none;font-size:1.05rem">Book Now — From $89</a>
</div></section>

<!-- FAQ -->
<section style="padding:4rem 0">
<div class="container"><div style="max-width:800px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:1.75rem;font-weight:800;margin-bottom:1.5rem">Location FAQs</h2>
<div style="display:grid;gap:1rem">
${[
  {q:'What cities does Umuve serve?', a:'Umuve serves 42 cities across South Florida: 12 cities in Palm Beach County, 15 cities in Broward County, and 15 cities in Miami-Dade County. See the full list above.'},
  {q:'Is same-day junk removal available everywhere?', a:'Same-day service is available in most of our 42 cities. Availability depends on operator schedules on a given day. Book online and select same-day availability to see open slots in your city.'},
  {q:'Do prices vary by city?', a:'Prices are largely consistent across all South Florida cities, though factors like traffic, access, and distance from disposal facilities can affect the final quote. Get an instant estimate online.'},
  {q:'Do you cover areas outside these 42 cities?', a:'Our primary coverage is the 42 cities listed. If you are in a surrounding area, book online and we will let you know if we can reach you. Many operators extend their service area for larger jobs.'}
].map(f => `<div style="background:#f9fafb;border:1px solid rgba(0,0,0,0.08);border-radius:0.75rem;padding:1.5rem">
<h3 style="font-family:Outfit;font-size:1rem;font-weight:700;margin:0 0 0.5rem">${f.q}</h3>
<p style="color:#6b7280;margin:0;line-height:1.7">${f.a}</p>
</div>`).join('\n')}
</div>
</div></div></section>

${FOOTER()}
</body>
</html>`;
}

// ---- GUIDES HUB ----
const GUIDES = [
  { slug: 'junk-removal-cost-south-florida', name: 'How Much Does Junk Removal Cost in South Florida?', desc: '2026 price guide covering 42 cities and 14 service types. Real data.', category: 'Pricing' },
  { slug: 'garage-cleanout-guide', name: 'Complete Garage Cleanout Guide', desc: 'Step-by-step guide to clearing your garage from top to bottom.', category: 'Cleanout Guides' },
  { slug: 'estate-cleanout-checklist', name: 'Estate Cleanout Checklist', desc: 'Everything you need to handle an estate cleanout with dignity and efficiency.', category: 'Cleanout Guides' },
  { slug: 'hoarder-cleanout-guide', name: 'Hoarding Cleanout Guide', desc: 'Compassionate, practical guide for hoarding cleanouts.', category: 'Cleanout Guides' },
  { slug: 'storage-unit-cleanout-guide', name: 'Storage Unit Cleanout Guide', desc: 'How to clear out a storage unit efficiently and affordably.', category: 'Cleanout Guides' },
  { slug: 'declutter-before-moving', name: 'How to Declutter Before Moving', desc: 'What to keep, donate, sell, or haul before your move.', category: 'Moving' },
  { slug: 'move-out-cleaning-checklist', name: 'Move-Out Cleaning Checklist', desc: 'Full checklist for getting your deposit back.', category: 'Moving' },
  { slug: 'declutter-for-spring-cleaning', name: 'Spring Cleaning Declutter Guide', desc: 'Where to start and how to finish your annual spring cleanout.', category: 'Seasonal' },
  { slug: 'downsizing-tips', name: 'Downsizing Tips for South Florida Homeowners', desc: 'Practical advice for moving into a smaller home.', category: 'Moving' },
  { slug: 'what-to-do-with-old-furniture', name: 'What to Do with Old Furniture', desc: 'Donate, sell, recycle, or haul — complete guide.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-appliances', name: 'How to Dispose of Appliances', desc: 'Legal and eco-friendly appliance disposal in South Florida.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-a-mattress', name: 'How to Dispose of a Mattress', desc: 'Florida mattress disposal rules and your best options.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-a-refrigerator', name: 'How to Dispose of a Refrigerator', desc: 'EPA-compliant refrigerator and Freon disposal guide.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-a-tv', name: 'How to Dispose of a TV', desc: 'Florida e-waste law and TV disposal options explained.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-electronics', name: 'How to Dispose of Electronics', desc: 'E-waste recycling guide for South Florida residents.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-paint', name: 'How to Dispose of Paint', desc: 'Latex vs oil paint disposal rules in Florida.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-tires', name: 'How to Dispose of Tires', desc: 'Legal tire disposal options in Palm Beach and Broward.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-concrete', name: 'How to Dispose of Concrete', desc: 'Construction concrete and masonry disposal in South Florida.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-drywall', name: 'How to Dispose of Drywall', desc: 'Drywall recycling and disposal rules for Florida.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-a-couch', name: 'How to Get Rid of a Couch', desc: 'The fastest and cheapest ways to dispose of a sofa.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-a-hot-tub', name: 'How to Dispose of a Hot Tub', desc: 'Hot tub and spa removal and disposal guide.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-a-dishwasher', name: 'How to Dispose of a Dishwasher', desc: 'Dishwasher disconnection and disposal options.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-a-dehumidifier', name: 'How to Dispose of a Dehumidifier', desc: 'Dehumidifier recycling and disposal requirements.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-a-washer-dryer', name: 'How to Dispose of a Washer or Dryer', desc: 'Washer and dryer recycling options in South Florida.', category: 'Disposal Guides' },
  { slug: 'how-to-dispose-of-a-stove-oven', name: 'How to Dispose of a Stove or Oven', desc: 'Safe and legal stove and oven disposal guide.', category: 'Disposal Guides' },
  { slug: 'renovation-debris-disposal-guide', name: 'Renovation Debris Disposal Guide', desc: 'What to do with all the construction waste from your renovation.', category: 'Construction' },
  { slug: 'how-to-remove-drywall', name: 'How to Remove Drywall', desc: 'Step-by-step drywall removal and disposal.', category: 'Construction' },
  { slug: 'how-to-remove-a-toilet', name: 'How to Remove a Toilet', desc: 'DIY toilet removal steps and disposal options.', category: 'Construction' },
  { slug: 'how-to-remove-a-kitchen-sink', name: 'How to Remove a Kitchen Sink', desc: 'Kitchen sink removal guide and disposal.', category: 'Construction' },
  { slug: 'how-to-take-apart-a-couch', name: 'How to Disassemble a Couch', desc: 'Break down a sofa for easier removal or disposal.', category: 'How-To' },
  { slug: 'how-to-take-apart-a-bed-frame', name: 'How to Take Apart a Bed Frame', desc: 'Disassemble any bed frame for disposal or moving.', category: 'How-To' },
];

function generateGuidesHub() {
  const canonical = '/guides';
  const title = 'Junk Removal Guides for South Florida — How-To, Pricing &amp; Disposal | Umuve';
  const desc = 'Free junk removal guides for South Florida residents. Pricing guides, disposal how-tos, cleanout checklists, and step-by-step instructions. 31 guides covering everything you need to know.';

  const categories = [...new Set(GUIDES.map(g => g.category))];

  const schema = `<script type="application/ld+json">{"@context":"https://schema.org","@type":"ItemList","name":"Umuve Junk Removal Guides","numberOfItems":${GUIDES.length},"url":"https://goumuve.com/guides"}</script>`;

  return `${HEAD(title, desc, canonical, schema)}
<body>
${NAV()}

<!-- Hero -->
<section style="padding:4rem 0 3rem;background:linear-gradient(135deg,#f9fafb 0%,#fff 100%)">
<div class="container">
<nav style="margin-bottom:1.25rem;font-size:0.85rem;color:#6b7280">
<a href="/" style="color:#DC2626;text-decoration:none">Home</a> &rsaquo; <span>Guides</span>
</nav>
<h1 style="font-family:Outfit;font-size:clamp(2rem,4vw,3rem);font-weight:800;margin-bottom:1rem;line-height:1.2">Junk Removal Guides for South Florida</h1>
<p style="font-size:1.1rem;color:#5c5c5c;margin-bottom:2rem;max-width:700px;line-height:1.7">Free guides covering junk removal pricing, disposal how-tos, cleanout checklists, and renovation guides. Written for South Florida residents in Palm Beach, Broward, and Miami-Dade counties.</p>
<div style="display:flex;flex-wrap:wrap;gap:0.75rem">
${categories.map(c => `<a href="#${c.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')}" style="padding:0.5rem 1rem;background:#f3f4f6;color:#374151;text-decoration:none;border-radius:9999px;font-size:0.85rem;font-weight:500">${c}</a>`).join('')}
</div>
</div></section>

<!-- Guides by Category -->
<section style="padding:4rem 0">
<div class="container">
${categories.map(cat => {
  const catGuides = GUIDES.filter(g => g.category === cat);
  const catId = cat.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
  return `<div id="${catId}" style="margin-bottom:3.5rem">
<h2 style="font-family:Outfit;font-size:1.5rem;font-weight:800;margin-bottom:1.5rem;color:#1f2937;padding-bottom:0.75rem;border-bottom:2px solid #DC2626">${cat}</h2>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1.25rem">
${catGuides.map(g => `<a href="/guides/${g.slug}" style="text-decoration:none;color:inherit">
<div style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:0.75rem;padding:1.5rem;transition:box-shadow 0.15s" onmouseover="this.style.boxShadow='0 4px 15px rgba(0,0,0,0.1)'" onmouseout="this.style.boxShadow='none'">
<span style="font-size:0.75rem;font-weight:600;color:#DC2626;background:#FEF2F2;padding:0.2rem 0.6rem;border-radius:9999px">${g.category}</span>
<h3 style="font-family:Outfit;font-size:1rem;font-weight:700;margin:0.75rem 0 0.5rem;color:#1f2937;line-height:1.4">${g.name}</h3>
<p style="color:#6b7280;font-size:0.825rem;margin:0;line-height:1.5">${g.desc}</p>
</div>
</a>`).join('\n')}
</div>
</div>`;
}).join('\n')}
</div></section>

<!-- CTA -->
<section style="padding:4rem 0;background:linear-gradient(135deg,#DC2626,#E11D48);color:#fff;text-align:center">
<div class="container">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:1rem">Ready to Hire Instead?</h2>
<p style="font-size:1.125rem;margin-bottom:2rem;opacity:0.95">Book Umuve online. Instant estimate. We handle all the heavy lifting across South Florida.</p>
<a href="https://app.goumuve.com/book" style="background:#fff;color:#DC2626;padding:1rem 2.5rem;font-weight:700;border-radius:0.5rem;text-decoration:none;font-size:1.05rem">Book Junk Removal — From $89</a>
</div></section>

${FOOTER()}
</body>
</html>`;
}

// ---- PRICING PAGE ----
const ALL_SERVICES_PRICING = [
  { name: 'Single Item Pickup', min: 89, avg: 115, desc: 'One furniture piece, appliance, or bulk item', includes: 'Loading, hauling, disposal' },
  { name: 'Furniture Removal', min: 89, avg: 189, desc: 'Couches, dressers, tables, chairs, bed frames', includes: '92% donated or recycled' },
  { name: 'Mattress Disposal', min: 89, avg: 119, desc: 'All mattress sizes, box springs included', includes: '89% recycled' },
  { name: 'Appliance Removal', min: 89, avg: 145, desc: 'Refrigerators, washers, dryers, stoves, ACs', includes: 'EPA-compliant disposal' },
  { name: 'Couch / Sofa Removal', min: 89, avg: 139, desc: 'Sectionals, loveseats, sleeper sofas, recliners', includes: 'Disassembly if needed' },
  { name: 'TV &amp; Electronics Recycling', min: 89, avg: 125, desc: 'TVs, computers, monitors, printers, e-waste', includes: 'R2-certified recycling' },
  { name: 'Refrigerator Disposal', min: 89, avg: 149, desc: 'All fridge sizes, EPA refrigerant recovery', includes: 'Freon recovery, recycling' },
  { name: 'Yard Waste Removal', min: 89, avg: 165, desc: 'Branches, brush, palm fronds, landscaping debris', includes: '98% composted/mulched' },
  { name: 'Construction Debris (Residential)', min: 149, avg: 325, desc: 'Drywall, lumber, tile, concrete, renovation waste', includes: 'Separated recycling' },
  { name: 'Garage Cleanout', min: 149, avg: 285, desc: 'Single and double car garages cleared', includes: 'Sweep clean after' },
  { name: 'Hot Tub Removal', min: 299, avg: 425, desc: 'Above-ground and in-ground hot tubs and spas', includes: 'Disassembly, full hauling' },
  { name: 'Estate Cleanout', min: 399, avg: 1240, desc: 'Full home, apartment, or storage unit', includes: 'Donation sorting, all labor' },
  { name: 'Office Cleanout (Commercial)', min: 299, avg: 650, desc: 'Desks, chairs, cubicles, filing cabinets, IT', includes: 'Certificate of removal' },
  { name: 'Warehouse Cleanout (Commercial)', min: 599, avg: 1800, desc: 'Pallet racking, equipment, bulk inventory', includes: 'Multi-crew available' },
];

function generatePricingPage() {
  const canonical = '/pricing';
  const title = 'Junk Removal Pricing in South Florida — Transparent Rates | Umuve';
  const desc = 'Transparent junk removal pricing for South Florida. See exact pricing for all 14 services before you book. No on-site estimate games. Starting at $89. Average job $189.';

  const faqSchema = `<script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
{"@type":"Question","name":"How much does junk removal cost in South Florida?","acceptedAnswer":{"@type":"Answer","text":"The average junk removal job in South Florida costs $189 with Umuve. Prices range from $89 for single-item pickup to $3,500+ for full estate cleanouts. Get an instant estimate online before you book."}},
{"@type":"Question","name":"What is the minimum charge for junk removal?","acceptedAnswer":{"@type":"Answer","text":"Umuve's minimum charge is $89, which covers single-item pickups like a single couch, mattress, or appliance."}},
{"@type":"Question","name":"Does the price include loading?","acceptedAnswer":{"@type":"Answer","text":"Yes. All Umuve pricing is all-inclusive — loading, hauling, fuel, and disposal are all included. There are no hidden fees."}},
{"@type":"Question","name":"How does Umuve pricing compare to 1-800-GOT-JUNK?","acceptedAnswer":{"@type":"Answer","text":"Umuve is typically 25-35% lower than 1-800-GOT-JUNK. GOT-JUNK starts at $150+ with a $298 minimum for most jobs. Umuve starts at $89 with transparent online estimates."}}
]}</script>`;

  const serviceSchema = `<script type="application/ld+json">{"@context":"https://schema.org","@type":"Service","serviceType":"Junk Removal","provider":{"@type":"Organization","name":"Umuve","url":"https://goumuve.com","telephone":"+15619441636"},"areaServed":{"@type":"State","name":"Florida"},"offers":{"@type":"AggregateOffer","lowPrice":"89","priceCurrency":"USD"}}</script>`;

  return `${HEAD(title, desc, canonical, faqSchema + '\n' + serviceSchema)}
<body>
${NAV()}

<!-- Hero -->
<section style="padding:4rem 0 3rem;background:linear-gradient(135deg,#f9fafb 0%,#fff 100%)">
<div class="container"><div style="max-width:800px">
<nav style="margin-bottom:1.25rem;font-size:0.85rem;color:#6b7280">
<a href="/" style="color:#DC2626;text-decoration:none">Home</a> &rsaquo; <span>Pricing</span>
</nav>
<h1 style="font-family:Outfit;font-size:clamp(2rem,4vw,3rem);font-weight:800;margin-bottom:1rem;line-height:1.2">Transparent Junk Removal Pricing — No Surprises</h1>
<p style="font-size:1.1rem;color:#5c5c5c;margin-bottom:1.5rem;line-height:1.7">Most junk removal companies make you wait for an on-site estimate. We show you real pricing upfront. Get an instant estimate online before you commit to a single thing.</p>
<div style="display:flex;flex-wrap:wrap;gap:1rem">
<a href="https://app.goumuve.com/book" style="background:#DC2626;color:#fff;padding:1rem 2rem;font-weight:700;border-radius:0.5rem;text-decoration:none">Get Your Instant Estimate</a>
<a href="tel:5619441636" style="background:#fff;color:#374151;padding:1rem 2rem;font-weight:600;border-radius:0.5rem;text-decoration:none;border:1px solid rgba(0,0,0,0.12)">(561) 944-1636</a>
</div>
</div></div></section>

<!-- Price Promise Banner -->
<section style="background:#1e3a5f;padding:1.5rem 0">
<div class="container"><div style="display:flex;flex-wrap:wrap;gap:2rem;justify-content:center;align-items:center">
${[['$89', 'Minimum price'],['$189', 'Average job'],['All-Inclusive', 'Loading + hauling + disposal'],['No Estimate Games', 'Price online, upfront']].map(([n, l]) => `<div style="text-align:center"><div style="font-family:Outfit;font-weight:800;color:#fff;font-size:1.3rem">${n}</div><div style="font-size:0.78rem;color:#93c5fd">${l}</div></div>`).join('<div style="width:1px;height:36px;background:rgba(255,255,255,0.2)"></div>')}
</div></div></section>

<!-- Pricing Table -->
<section style="padding:4rem 0">
<div class="container">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.5rem">Service Pricing Guide</h2>
<p style="color:#6b7280;margin-bottom:2rem">Prices shown are South Florida averages based on 30,000+ completed jobs. Your actual quote may vary based on volume, access, and item types. Get an exact estimate online.</p>
<div style="overflow-x:auto">
<table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:1rem;overflow:hidden">
<thead>
<tr style="background:#1e3a5f;color:#fff">
<th style="padding:1.125rem 1.5rem;text-align:left">Service</th>
<th style="padding:1.125rem 1.5rem;text-align:center">Starting Price</th>
<th style="padding:1.125rem 1.5rem;text-align:center">Average Price</th>
<th style="padding:1.125rem 1.5rem;text-align:left;display:none" class="hideOnMobile">What's Included</th>
</tr>
</thead>
<tbody>
${ALL_SERVICES_PRICING.map((s, i) => `<tr style="${i % 2 === 1 ? 'background:#f9fafb;' : ''}border-bottom:1px solid rgba(0,0,0,0.06)">
<td style="padding:1.125rem 1.5rem">
<p style="font-weight:600;color:#1f2937;margin:0 0 0.25rem">${s.name}</p>
<p style="color:#9ca3af;font-size:0.8rem;margin:0">${s.desc}</p>
</td>
<td style="padding:1.125rem 1.5rem;text-align:center;font-weight:700;color:#DC2626;font-size:1.05rem">$${s.min}</td>
<td style="padding:1.125rem 1.5rem;text-align:center;color:#374151;font-weight:600">$${s.avg}</td>
<td style="padding:1.125rem 1.5rem;color:#6b7280;font-size:0.85rem;display:none" class="hideOnMobile">${s.includes}</td>
</tr>`).join('\n')}
</tbody>
</table>
</div>
<p style="margin-top:1rem;font-size:0.8rem;color:#9ca3af">All prices are all-inclusive (loading, hauling, disposal). No hidden fees. Actual prices vary by volume and access. Get an exact online estimate at app.goumuve.com/book.</p>
</div></section>

<!-- Pricing Philosophy -->
<section style="padding:4rem 0;background:#f9fafb">
<div class="container"><div style="max-width:900px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.75rem">Our Pricing Philosophy</h2>
<p style="color:#6b7280;margin-bottom:2rem">Three things we refuse to do — because our competitors do them constantly.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1.5rem">
${[
  {title:'No On-Site Estimate Requirement', body:'We give you a real price estimate online before you book. You should never have to commit to a visit just to find out what something costs.'},
  {title:'No Hidden Fees', body:'The price includes labor, truck, fuel, and disposal. We do not add a "fuel surcharge" after the fact or charge extra for items that were visible when we quoted.'},
  {title:'No Bait-and-Switch', body:'Some haulers quote low, then raise the price when they arrive claiming "it\'s more than expected." Our online estimate is the price. It changes only if you add items not in the original quote.'}
].map(t => `<div style="padding:1.75rem;background:#fff;border-radius:0.75rem;border:1px solid rgba(0,0,0,0.08)">
<h3 style="font-family:Outfit;font-size:1.1rem;font-weight:700;margin:0 0 0.75rem;color:#1e3a5f">${t.title}</h3>
<p style="color:#6b7280;margin:0;line-height:1.7;font-size:0.9rem">${t.body}</p>
</div>`).join('\n')}
</div>
</div></div></section>

<!-- Volume Pricing -->
<section style="padding:4rem 0">
<div class="container"><div style="max-width:800px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.75rem">How Volume Pricing Works</h2>
<p style="color:#6b7280;margin-bottom:2rem">Junk removal is priced primarily by volume — how much space your items take up in our truck. Here is the general breakdown.</p>
<div style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:1rem;overflow:hidden">
<table style="width:100%;border-collapse:collapse">
<thead style="background:#f9fafb">
<tr><th style="padding:1rem 1.5rem;text-align:left;border-bottom:1px solid rgba(0,0,0,0.08)">Volume</th><th style="padding:1rem 1.5rem;text-align:center;border-bottom:1px solid rgba(0,0,0,0.08)">Typical Items</th><th style="padding:1rem 1.5rem;text-align:center;border-bottom:1px solid rgba(0,0,0,0.08)">Price Range</th></tr>
</thead>
<tbody>
${[
  ['1-2 items (minimum)', '1 couch, 1 mattress, 1 appliance', '$89-$149'],
  ['Quarter truck (3 cu yd)', 'Bedroom furniture set', '$149-$249'],
  ['Half truck (5-6 cu yd)', 'Small room cleanout', '$249-$399'],
  ['Three-quarter truck (8-9 cu yd)', 'Large room or garage', '$399-$549'],
  ['Full truck (12-13 cu yd)', 'Full apartment or basement', '$549-$849'],
  ['Multiple trucks', 'Estate cleanout or commercial', 'Custom quote']
].map(([v, items, price], i) => `<tr style="${i % 2 === 1 ? 'background:#f9fafb' : ''}">
<td style="padding:1rem 1.5rem;font-weight:600;color:#374151">${v}</td>
<td style="padding:1rem 1.5rem;color:#6b7280;text-align:center;font-size:0.875rem">${items}</td>
<td style="padding:1rem 1.5rem;text-align:center;color:#DC2626;font-weight:700">${price}</td>
</tr>`).join('\n')}
</tbody>
</table>
</div>
</div></div></section>

<!-- Competitor Comparison -->
<section style="padding:4rem 0;background:#f9fafb">
<div class="container"><div style="max-width:900px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.75rem">How We Compare</h2>
<p style="color:#6b7280;margin-bottom:2rem">Real pricing data compared to major South Florida competitors.</p>
<div style="overflow-x:auto">
<table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:1rem;overflow:hidden">
<thead>
<tr style="background:#f9fafb;border-bottom:2px solid rgba(0,0,0,0.08)">
<th style="padding:1.125rem 1.5rem;text-align:left">Service</th>
<th style="padding:1.125rem 1.5rem;text-align:center;color:#DC2626">Umuve</th>
<th style="padding:1.125rem 1.5rem;text-align:center">1-800-GOT-JUNK</th>
<th style="padding:1.125rem 1.5rem;text-align:center">Junk King</th>
</tr>
</thead>
<tbody>
${[
  ['Single Item / Minimum', '$89', '$298+', '$249+'],
  ['Quarter Truck', '$149-249', '$298-398', '$249-349'],
  ['Half Truck', '$249-399', '$398-598', '$349-499'],
  ['Full Truck', '$549-849', '$798-1,198', '$699-999'],
  ['Online Price Estimate', 'Yes', 'No (call required)', 'Partial'],
  ['Same-Day Availability', 'Yes, 67% of jobs', 'Yes, varies', 'Yes, varies'],
].map(([service, umuve, gotjunk, junkking], i) => `<tr style="${i % 2 === 1 ? 'background:#f9fafb;' : ''}border-bottom:1px solid rgba(0,0,0,0.06)">
<td style="padding:1rem 1.5rem;font-weight:500;color:#374151">${service}</td>
<td style="padding:1rem 1.5rem;text-align:center;color:#DC2626;font-weight:700">${umuve}</td>
<td style="padding:1rem 1.5rem;text-align:center;color:#6b7280">${gotjunk}</td>
<td style="padding:1rem 1.5rem;text-align:center;color:#6b7280">${junkking}</td>
</tr>`).join('\n')}
</tbody>
</table>
</div>
<p style="font-size:0.8rem;color:#9ca3af;margin-top:1rem">Competitor prices based on market research as of 2026. Actual competitor quotes may vary. <a href="/vs/umuve-vs-1800-got-junk" style="color:#DC2626;text-decoration:none">See full comparison &rarr;</a></p>
</div></div></section>

<!-- Price Guarantee -->
<section style="padding:3rem 0">
<div class="container"><div style="max-width:700px;margin:0 auto;text-align:center">
<div style="background:linear-gradient(135deg,#FEF2F2,#fff);border:2px solid #DC2626;border-radius:1.5rem;padding:3rem">
<h2 style="font-family:Outfit;font-size:1.75rem;font-weight:800;margin-bottom:0.75rem;color:#DC2626">Our Price Guarantee</h2>
<p style="color:#374151;line-height:1.7;margin-bottom:1.5rem">The price we quote online is the price you pay. If we arrive and the job is exactly as described, the price does not change. If you described the job accurately and we try to raise the price on arrival — you do not owe us anything.</p>
<a href="https://app.goumuve.com/book" style="background:#DC2626;color:#fff;padding:1rem 2rem;font-weight:700;border-radius:0.5rem;text-decoration:none;display:inline-block">Get Your Price Now</a>
</div>
</div></div></section>

<!-- FAQ -->
<section style="padding:4rem 0;background:#f9fafb">
<div class="container"><div style="max-width:800px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:1.75rem;font-weight:800;margin-bottom:1.5rem">Pricing FAQs</h2>
<div style="display:grid;gap:1rem">
${[
  {q:'How much does junk removal cost in South Florida?', a:'The average junk removal job in South Florida costs $189 with Umuve. Prices range from $89 for single-item pickup to $3,500+ for full estate cleanouts. Your price depends on volume, item types, and access. Get an instant estimate online before booking.'},
  {q:'Does the price include labor and disposal?', a:'Yes. All Umuve pricing is all-inclusive — loading labor, truck, fuel, and eco-friendly disposal are included. There are no surprise add-ons when we arrive.'},
  {q:'How does Umuve pricing compare to 1-800-GOT-JUNK?', a:'Umuve is typically 25-35% lower than 1-800-GOT-JUNK. GOT-JUNK\'s minimum is $298+ for most jobs. Umuve starts at $89. For a half-truck load, Umuve typically costs $100-200 less than the same job with GOT-JUNK.'},
  {q:'Do prices vary by city in South Florida?', a:'Prices are largely consistent across all 42 South Florida cities we serve. Minor variations can occur based on drive distance to disposal facilities, local demand, and same-day surcharges during peak periods.'},
  {q:'Is there a discount for large jobs?', a:'Volume pricing naturally decreases per cubic yard as load size increases. Commercial accounts and recurring customers receive additional negotiated rates. Ask about our commercial pricing for businesses.'},
  {q:'What is the cheapest way to get junk removed in South Florida?', a:'Book a single-item pickup at $89 for one item. For larger loads, Umuve is typically the lowest-priced fully insured, eco-friendly option in South Florida. Local cash haulers may quote less but typically lack insurance and eco-friendly disposal practices.'}
].map(f => `<div style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:0.75rem;padding:1.5rem">
<h3 style="font-family:Outfit;font-size:1rem;font-weight:700;margin:0 0 0.5rem">${f.q}</h3>
<p style="color:#6b7280;margin:0;line-height:1.7">${f.a}</p>
</div>`).join('\n')}
</div>
</div></div></section>

<!-- CTA -->
<section style="padding:4rem 0;background:linear-gradient(135deg,#DC2626,#E11D48);color:#fff;text-align:center">
<div class="container">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:1rem">Get Your Exact Price in 3 Minutes</h2>
<p style="font-size:1.125rem;margin-bottom:2rem;opacity:0.95">No commitment. No on-site visit required. Just an instant, honest estimate.</p>
<div style="display:flex;flex-wrap:wrap;gap:1rem;justify-content:center">
<a href="https://app.goumuve.com/book" style="background:#fff;color:#DC2626;padding:1rem 2.5rem;font-weight:700;border-radius:0.5rem;text-decoration:none;font-size:1.05rem">Get My Price Now</a>
<a href="tel:5619441636" style="background:rgba(255,255,255,0.15);color:#fff;padding:1rem 2rem;font-weight:600;border-radius:0.5rem;text-decoration:none">(561) 944-1636</a>
</div>
</div></section>

<!-- Internal Links -->
<section style="padding:3rem 0">
<div class="container"><div style="max-width:800px;margin:0 auto">
<p style="font-weight:600;margin-bottom:1rem;color:#374151">Related Pages</p>
<div style="display:flex;flex-wrap:wrap;gap:0.75rem">
<a href="/services" style="padding:0.5rem 1rem;background:#f3f4f6;color:#374151;text-decoration:none;border-radius:0.5rem;font-size:0.875rem;font-weight:500">All Services</a>
<a href="/vs/umuve-vs-1800-got-junk" style="padding:0.5rem 1rem;background:#f3f4f6;color:#374151;text-decoration:none;border-radius:0.5rem;font-size:0.875rem;font-weight:500">Umuve vs 1-800-GOT-JUNK</a>
<a href="/vs/diy-junk-removal" style="padding:0.5rem 1rem;background:#f3f4f6;color:#374151;text-decoration:none;border-radius:0.5rem;font-size:0.875rem;font-weight:500">DIY vs Professional</a>
<a href="/vs/bagster" style="padding:0.5rem 1rem;background:#f3f4f6;color:#374151;text-decoration:none;border-radius:0.5rem;font-size:0.875rem;font-weight:500">Umuve vs Bagster</a>
<a href="/guides/junk-removal-cost-south-florida" style="padding:0.5rem 1rem;background:#f3f4f6;color:#374151;text-decoration:none;border-radius:0.5rem;font-size:0.875rem;font-weight:500">Pricing Guide</a>
<a href="/commercial" style="padding:0.5rem 1rem;background:#f3f4f6;color:#374151;text-decoration:none;border-radius:0.5rem;font-size:0.875rem;font-weight:500">Commercial Pricing</a>
</div>
</div></div></section>

${FOOTER()}
</body>
</html>`;
}

// ---- Write Files ----

// services/index.html
const servicesDir = path.join(BASE_DIR, 'services');
if (!fs.existsSync(servicesDir)) fs.mkdirSync(servicesDir, { recursive: true });
fs.writeFileSync(path.join(servicesDir, 'index.html'), generateServicesHub());
console.log('Generated: services/index.html');

// locations/index.html
const locationsDir = path.join(BASE_DIR, 'locations');
if (!fs.existsSync(locationsDir)) fs.mkdirSync(locationsDir, { recursive: true });
fs.writeFileSync(path.join(locationsDir, 'index.html'), generateLocationsHub());
console.log('Generated: locations/index.html');

// guides/index.html
const guidesDir = path.join(BASE_DIR, 'guides');
fs.writeFileSync(path.join(guidesDir, 'index.html'), generateGuidesHub());
console.log('Generated: guides/index.html');

// pricing.html
fs.writeFileSync(path.join(BASE_DIR, 'pricing.html'), generatePricingPage());
console.log('Generated: pricing.html');

console.log('\nPhase 6 complete: 4 hub/pillar pages generated');

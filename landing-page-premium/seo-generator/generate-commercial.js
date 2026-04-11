#!/usr/bin/env node
/**
 * Phase 4: Commercial Service Pages Generator
 * Generates commercial/index.html and commercial/{slug}.html
 */

const fs = require('fs');
const path = require('path');

const BASE_DIR = path.join(__dirname, '..');
const OUTPUT_DIR = path.join(BASE_DIR, 'commercial');

const HEAD_COMMON = (title, desc, canonical, extraSchema) => `<!DOCTYPE html>
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
<a href="tel:5619441636" style="color:#374151;font-weight:600;text-decoration:none;font-size:0.9rem">(561) 944-1636</a>
<a href="https://app.goumuve.com/book" class="btn btn-primary">Get a Quote</a>
</div>
</div></div></nav>`;

const FOOTER = () => `<footer style="background:#111827;color:#9ca3af;padding:3rem 0;margin-top:4rem">
<div class="container">
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:2rem;margin-bottom:2rem">
<div>
<img src="/logo-nav.png" alt="Umuve — Hauling Made Simple" width="107" height="32" loading="lazy" style="margin-bottom:1rem;filter:brightness(0) invert(1)">
<p style="font-size:0.875rem;line-height:1.6">South Florida's junk removal platform. 500+ local operators. Same-day service.</p>
</div>
<div>
<p style="font-weight:600;color:#fff;margin-bottom:0.75rem">Commercial Services</p>
<ul style="list-style:none;padding:0;margin:0">
<li style="margin-bottom:0.5rem"><a href="/commercial/office-cleanout" style="color:#9ca3af;text-decoration:none;font-size:0.875rem">Office Cleanout</a></li>
<li style="margin-bottom:0.5rem"><a href="/commercial/retail-store-cleanout" style="color:#9ca3af;text-decoration:none;font-size:0.875rem">Retail Store Cleanout</a></li>
<li style="margin-bottom:0.5rem"><a href="/commercial/construction-debris" style="color:#9ca3af;text-decoration:none;font-size:0.875rem">Construction Debris</a></li>
<li style="margin-bottom:0.5rem"><a href="/commercial/restaurant-cleanout" style="color:#9ca3af;text-decoration:none;font-size:0.875rem">Restaurant Cleanout</a></li>
<li style="margin-bottom:0.5rem"><a href="/commercial/warehouse-cleanout" style="color:#9ca3af;text-decoration:none;font-size:0.875rem">Warehouse Cleanout</a></li>
<li style="margin-bottom:0.5rem"><a href="/commercial/property-management" style="color:#9ca3af;text-decoration:none;font-size:0.875rem">Property Management</a></li>
<li style="margin-bottom:0.5rem"><a href="/commercial/hoa-services" style="color:#9ca3af;text-decoration:none;font-size:0.875rem">HOA Services</a></li>
</ul>
</div>
<div>
<p style="font-weight:600;color:#fff;margin-bottom:0.75rem">Residential Services</p>
<ul style="list-style:none;padding:0;margin:0">
<li style="margin-bottom:0.5rem"><a href="/services/furniture-removal" style="color:#9ca3af;text-decoration:none;font-size:0.875rem">Furniture Removal</a></li>
<li style="margin-bottom:0.5rem"><a href="/services/appliance-removal" style="color:#9ca3af;text-decoration:none;font-size:0.875rem">Appliance Removal</a></li>
<li style="margin-bottom:0.5rem"><a href="/services/estate-cleanout" style="color:#9ca3af;text-decoration:none;font-size:0.875rem">Estate Cleanout</a></li>
<li style="margin-bottom:0.5rem"><a href="/services/garage-cleanout" style="color:#9ca3af;text-decoration:none;font-size:0.875rem">Garage Cleanout</a></li>
<li style="margin-bottom:0.5rem"><a href="/services/construction-debris" style="color:#9ca3af;text-decoration:none;font-size:0.875rem">Construction Debris</a></li>
</ul>
</div>
<div>
<p style="font-weight:600;color:#fff;margin-bottom:0.75rem">Contact</p>
<p style="font-size:0.875rem;margin-bottom:0.5rem"><a href="tel:5619441636" style="color:#9ca3af;text-decoration:none">(561) 944-1636</a></p>
<p style="font-size:0.875rem;margin-bottom:0.5rem">Palm Beach, Broward &amp; Miami-Dade</p>
<a href="https://app.goumuve.com/book" style="background:#DC2626;color:#fff;padding:0.75rem 1.5rem;border-radius:0.5rem;text-decoration:none;font-weight:600;font-size:0.875rem;display:inline-block;margin-top:0.5rem">Book Online</a>
</div>
</div>
<div style="border-top:1px solid #374151;padding-top:1.5rem;display:flex;flex-wrap:wrap;gap:1rem;justify-content:space-between;font-size:0.8rem">
<p style="margin:0">&copy; 2026 Umuve. All rights reserved.</p>
<div style="display:flex;gap:1rem">
<a href="/privacy" style="color:#9ca3af;text-decoration:none">Privacy Policy</a>
<a href="/terms" style="color:#9ca3af;text-decoration:none">Terms of Service</a>
</div>
</div>
</div>
</footer>`;

const COMMERCIAL_SERVICES = [
  {
    slug: 'office-cleanout',
    name: 'Office Cleanout',
    tagline: 'Complete Office &amp; Workspace Cleanout Services in South Florida',
    desc: 'Professional office cleanout services in South Florida. We remove desks, chairs, cubicles, filing cabinets, IT equipment, and all office furniture with minimal disruption. After-hours available. From $299.',
    items: ['Office Desks &amp; Chairs', 'Cubicle Systems &amp; Partitions', 'Filing Cabinets &amp; Storage Units', 'Computers, Servers &amp; IT Equipment', 'Conference Tables &amp; Presentation Gear', 'Break Room Appliances &amp; Furniture', 'Phone Systems &amp; Cabling', 'Reception Furniture &amp; Signage'],
    pricing: { min: 299, avg: 650, max: 1995, note: 'Priced per truckload. Most office cleanouts require 1-2 trucks.' },
    industries: ['Law Firms &amp; Professional Services', 'Medical &amp; Dental Offices', 'Financial Services', 'Real Estate Agencies', 'Tech Startups &amp; Co-working Spaces', 'Insurance Companies', 'Accounting Firms', 'Corporate Headquarters'],
    process: [
      { step: 'Assessment', detail: 'We walk through your office space and provide a firm quote — no surprises.' },
      { step: 'Scheduling', detail: 'Choose your preferred time including early morning, evenings, or weekends.' },
      { step: 'Execution', detail: 'Our crew loads everything efficiently, protecting floors and walls throughout.' },
      { step: 'Documentation', detail: 'Certificate of removal provided. We confirm recycling and donation destinations.' }
    ],
    benefits: ['After-hours and weekend availability', 'Fully insured crew and vehicles', 'Certificate of removal for corporate records', 'Electronics handled by R2-certified recyclers', 'Donation receipts for tax deductions', 'Volume discounts for recurring cleanouts'],
    faqs: [
      { q: 'Do you offer after-hours office cleanout service?', a: 'Yes. We schedule around your business hours. Most office cleanouts happen evenings (after 6 PM) or weekends so there is zero disruption to your team or clients.' },
      { q: 'Are you insured for commercial work?', a: 'All Umuve operators carry commercial general liability insurance and workers compensation. Your property is covered from the moment we arrive.' },
      { q: 'Can you clear an entire office floor in one day?', a: 'Typically yes. A 10,000 sq ft office floor takes 6-8 hours with a 3-person crew. We can add a second crew for larger spaces.' },
      { q: 'What happens to the office furniture you remove?', a: 'Desks, chairs, and filing cabinets in good condition are donated to nonprofits and schools. Electronics go to R2-certified recyclers. Only items with no reuse value go to disposal.' },
      { q: 'Do you provide documentation for our corporate records?', a: 'Yes. We provide a certificate of removal with item categories, quantities, and disposal/donation destinations. Most corporate clients require this for compliance.' }
    ]
  },
  {
    slug: 'retail-store-cleanout',
    name: 'Retail Store Cleanout',
    tagline: 'Retail Store &amp; Storefront Cleanout Services in South Florida',
    desc: 'Professional retail store cleanout services in Palm Beach, Broward, and Miami-Dade. We clear display fixtures, shelving, inventory, counters, and all retail equipment. Same-day available. From $399.',
    items: ['Display Cases &amp; Shelving Units', 'Clothing Racks &amp; Mannequins', 'Point-of-Sale Equipment', 'Storage Room Contents', 'Checkout Counters &amp; Kiosks', 'Signage &amp; Display Systems', 'Back-of-House Equipment', 'Inventory &amp; Unsold Merchandise'],
    pricing: { min: 399, avg: 795, max: 2400, note: 'Priced by volume and complexity. Strip malls and multi-unit spaces receive volume discounts.' },
    industries: ['Clothing &amp; Apparel Stores', 'Electronics Retailers', 'Furniture Showrooms', 'Grocery &amp; Convenience Stores', 'Beauty &amp; Salon Spaces', 'Boutique Shops', 'Dollar Stores &amp; Discount Retail', 'Pop-up Shops &amp; Temporary Retail'],
    process: [
      { step: 'Assessment', detail: 'We inspect your storefront and provide a binding quote based on volume and item types.' },
      { step: 'Scheduling', detail: 'Choose a time that minimizes lost business hours — evenings, weekends, or before opening.' },
      { step: 'Execution', detail: 'Crew disassembles fixtures, clears shelving, and loads everything carefully to avoid damage.' },
      { step: 'Documentation', detail: 'Itemized removal certificate provided. Donation receipts available for qualifying items.' }
    ],
    benefits: ['Evening and weekend scheduling available', 'Fixture disassembly included in price', 'Donation of usable merchandise to charities', 'Broom-clean finish included', 'Strip mall and multi-unit discounts', 'Insurance documentation provided to landlords'],
    faqs: [
      { q: 'Can you cleanout a retail store before lease expiration?', a: 'Yes. We work with tight deadlines. If you have a lease end date, tell us and we will prioritize your project. Same-day and next-day slots are often available.' },
      { q: 'Do you disassemble shelving and display fixtures?', a: 'Yes. Fixture disassembly is included in our retail cleanout service. We break down display systems, clothing racks, and shelving so everything fits in our trucks.' },
      { q: 'What happens to unsold merchandise or inventory?', a: 'Sellable inventory can be donated to charities, thrift stores, or community organizations. We provide donation receipts. Non-donatable items go to appropriate disposal facilities.' },
      { q: 'Do you work with property managers to release the space?', a: 'Yes. We communicate directly with property managers when needed. We provide a certificate of removal and leave the space broom-clean for inspection.' },
      { q: 'How fast can you clear a 3,000 sq ft retail space?', a: 'A typical 3,000 sq ft retail store takes 4-6 hours with a 3-person crew. Heavily stocked stores or those with heavy fixtures may take longer.' }
    ]
  },
  {
    slug: 'construction-debris',
    name: 'Construction Debris Removal',
    tagline: 'Commercial Construction Debris &amp; Renovation Waste Removal in South Florida',
    desc: 'Commercial construction debris removal for contractors and developers in Palm Beach, Broward, and Miami-Dade. Drywall, lumber, concrete, tile, and all renovation waste. Contractor accounts available. From $249.',
    items: ['Drywall &amp; Sheetrock Scraps', 'Lumber, Plywood &amp; Wood Framing', 'Concrete, Block &amp; Masonry Debris', 'Tile, Flooring &amp; Carpet Remnants', 'Cabinets &amp; Countertop Tear-outs', 'Plumbing &amp; Electrical Materials', 'Roofing Materials &amp; Shingles', 'Metal Framing &amp; Ductwork'],
    pricing: { min: 249, avg: 650, max: 2500, note: 'Volume pricing for contractors. Ongoing jobsite accounts available with weekly scheduling.' },
    industries: ['General Contractors', 'Residential Developers', 'Commercial Renovation Firms', 'Kitchen &amp; Bath Remodelers', 'Roofing Companies', 'HVAC &amp; Plumbing Contractors', 'Property Owners &amp; Flippers', 'HOA Common Area Renovations'],
    process: [
      { step: 'Assessment', detail: 'Walk your jobsite with us and get a quote within minutes. Flat-rate or volume pricing.' },
      { step: 'Scheduling', detail: 'Schedule recurring weekly pickups or call when your job phase is complete.' },
      { step: 'Execution', detail: 'Crew loads all debris, separates recyclables, and hauls everything off your site.' },
      { step: 'Documentation', detail: 'Weight tickets and disposal manifests provided for permit compliance.' }
    ],
    benefits: ['Contractor accounts with weekly scheduling', 'No hazardous material surcharges on standard debris', 'Separate concrete, metal, and wood recycling streams', 'Disposal manifests for permit compliance', 'Same-day emergency cleanouts for inspections', 'No permit required — we handle it all'],
    faqs: [
      { q: 'Do you accept all types of construction debris?', a: 'We accept drywall, lumber, concrete, tile, carpet, cabinets, metal, roofing materials, and general renovation waste. We do not accept asbestos, lead paint, or hazardous chemicals.' },
      { q: 'Can you set up recurring weekly debris removal for a jobsite?', a: 'Yes. Contractor accounts with weekly or bi-weekly scheduling are available. You get a fixed rate and priority scheduling throughout your project.' },
      { q: 'Do you provide weight tickets for permit compliance?', a: 'Yes. Weight tickets and disposal manifests are available upon request. Many permit pull requires documentation of proper debris disposal.' },
      { q: 'How do you handle concrete and heavy masonry debris?', a: 'We have reinforced trucks rated for heavy debris loads. Concrete is separated and taken to aggregate recycling facilities, keeping it out of landfills.' },
      { q: 'Are you faster than renting a dumpster for a construction site?', a: 'For most mid-size projects, yes. Dumpsters take days to deliver and pick up. We arrive same-day or next-day, load everything ourselves, and your site is clear within hours.' }
    ]
  },
  {
    slug: 'restaurant-cleanout',
    name: 'Restaurant Cleanout',
    tagline: 'Restaurant &amp; Food Service Cleanout Services in South Florida',
    desc: 'Professional restaurant cleanout services in Palm Beach, Broward, and Miami-Dade. We remove commercial kitchen equipment, booths, tables, walk-in coolers, and all food service fixtures. Health code compliant. From $499.',
    items: ['Commercial Kitchen Equipment', 'Walk-in Coolers &amp; Freezers', 'Restaurant Booths &amp; Tables', 'Bar Equipment &amp; Counters', 'Point-of-Sale Systems', 'Hood Systems &amp; Ventilation', 'Storage Racks &amp; Shelving', 'Dining Room Furniture &amp; Decor'],
    pricing: { min: 499, avg: 1100, max: 3500, note: 'Restaurant cleanouts vary widely by kitchen size and equipment. Most full restaurants fall in the $800-1,800 range.' },
    industries: ['Full-Service Restaurants', 'Fast Food &amp; QSR Locations', 'Food Trucks &amp; Ghost Kitchens', 'Catering Companies', 'Cafeterias &amp; Institutional Kitchens', 'Bars &amp; Nightclubs', 'Bakeries &amp; Delis', 'Hotel &amp; Resort Food Service'],
    process: [
      { step: 'Assessment', detail: 'We assess your kitchen, dining room, and storage areas to provide an accurate quote.' },
      { step: 'Scheduling', detail: 'Most restaurant cleanouts happen overnight or early morning to meet health code requirements.' },
      { step: 'Execution', detail: 'Crew handles all equipment disconnection coordination, loading, and hauling.' },
      { step: 'Documentation', detail: 'Removal documentation for health department and landlord records provided.' }
    ],
    benefits: ['Overnight and early morning availability', 'Commercial kitchen equipment handled safely', 'Health department compliance documentation', 'Coordination with equipment disconnection contractors', 'Grease trap equipment handled properly', 'Restaurant equipment donated to culinary schools when possible'],
    faqs: [
      { q: 'Do you remove commercial kitchen equipment like fryers and ovens?', a: 'Yes. We work alongside licensed plumbers and electricians for disconnection, then our crew handles all removal and hauling. We coordinate the full process.' },
      { q: 'Can you cleanout a restaurant overnight before a health inspection?', a: 'Yes. Overnight cleanouts are available with 24-hour notice. Many restaurant clients need fast turnaround for health inspections, lease transitions, or rebranding.' },
      { q: 'What happens to usable restaurant equipment you remove?', a: 'Commercial kitchen equipment in working condition is donated to culinary schools, community kitchens, and nonprofits. We provide donation documentation for tax purposes.' },
      { q: 'How do you handle walk-in cooler removal?', a: 'Walk-in cooler removal requires coordination with refrigerant recovery specialists. We can manage this process end-to-end or work alongside your contractors.' },
      { q: 'Are restaurant cleanouts priced differently than office cleanouts?', a: 'Yes. Restaurant cleanouts involve heavier equipment, more coordination, and often require specialized handling. Prices typically start at $499 and go up based on kitchen size.' }
    ]
  },
  {
    slug: 'warehouse-cleanout',
    name: 'Warehouse Cleanout',
    tagline: 'Industrial Warehouse &amp; Distribution Center Cleanout in South Florida',
    desc: 'Large-scale warehouse cleanout services across South Florida. Pallet racking, industrial shelving, machinery, office buildouts, and bulk inventory removal. Multi-crew available. From $599.',
    items: ['Pallet Racking &amp; Shelving Systems', 'Industrial Machinery &amp; Equipment', 'Conveyor Systems &amp; Forklifts (empty)', 'Bulk Inventory &amp; Overstock', 'Office Buildouts &amp; Mezzanines', 'Loading Dock Equipment', 'Electrical Equipment &amp; Panels', 'Bulk Packaging &amp; Cardboard'],
    pricing: { min: 599, avg: 1800, max: 7500, note: 'Warehouse cleanouts priced by volume and equipment type. Multi-crew deployments available for large facilities.' },
    industries: ['E-Commerce Fulfillment Centers', 'Manufacturing Facilities', 'Distribution &amp; Logistics Companies', 'Cold Storage Operations', 'Automotive Parts Warehouses', 'Building Material Suppliers', 'Industrial Equipment Companies', 'Government &amp; Municipal Facilities'],
    process: [
      { step: 'Assessment', detail: 'On-site walkthrough to assess volume, equipment types, and access constraints.' },
      { step: 'Scheduling', detail: 'Multi-day or multi-crew plans for large facilities. Weekend and overnight available.' },
      { step: 'Execution', detail: 'Multiple crews tackle different zones simultaneously. Safety protocols followed.' },
      { step: 'Documentation', detail: 'Itemized manifest with disposal and recycling documentation for compliance.' }
    ],
    benefits: ['Multi-crew deployment for large facilities', 'Pallet racking disassembly included', 'Metal and industrial equipment recycling', 'Multi-day project management', 'Compliance documentation for industrial waste', 'Coordination with equipment liquidators if needed'],
    faqs: [
      { q: 'Can you cleanout a 50,000 sq ft warehouse?', a: 'Yes. We deploy multiple crews for large-scale projects. A 50,000 sq ft warehouse typically takes 2-3 days with a 4-6 person crew. We will scope your project specifically.' },
      { q: 'Do you disassemble pallet racking systems?', a: 'Yes. Pallet racking disassembly is included in warehouse cleanout pricing. Steel racking is separated for metal recycling, recovering significant material value.' },
      { q: 'Can you coordinate with equipment liquidators?', a: 'Yes. We work alongside equipment liquidators, auctioneers, and resellers. We can sequence our removal after valuable equipment has been sold or transferred.' },
      { q: 'What documentation do you provide for industrial waste?', a: 'We provide itemized removal manifests, weight tickets where available, and disposal facility documentation. This supports compliance with environmental and occupancy regulations.' },
      { q: 'How quickly can you start a warehouse cleanout?', a: 'We can typically start within 2-3 business days of scoping. Emergency starts within 24 hours are possible for time-sensitive lease situations.' }
    ]
  },
  {
    slug: 'property-management',
    name: 'Property Management Cleanout',
    tagline: 'Junk Removal &amp; Cleanout Services for Property Managers in South Florida',
    desc: 'Reliable junk removal services for property managers across South Florida. Unit turnover cleanouts, tenant abandonment, eviction cleanouts, and common area clearing. Recurring accounts available. From $199.',
    items: ['Tenant Abandoned Belongings', 'Unit Turnover Cleanouts', 'Common Area Furniture &amp; Debris', 'Pool Deck &amp; Amenity Area Items', 'Storage Room Cleanouts', 'Garage &amp; Parking Deck Debris', 'Landscaping &amp; Outdoor Furniture', 'Appliances Left by Tenants'],
    pricing: { min: 199, avg: 450, max: 1800, note: 'Volume pricing for property managers with multiple units. Monthly account billing available.' },
    industries: ['Apartment Complex Management', 'Commercial Real Estate', 'HOA Management Companies', 'Single-Family Rental Portfolio Owners', 'Student Housing Operators', 'Senior Living Communities', 'Mixed-Use Property Managers', 'Corporate Housing Providers'],
    process: [
      { step: 'Assessment', detail: 'Unit walkthrough or photo submission for same-day quote on turnover jobs.' },
      { step: 'Scheduling', detail: 'Priority scheduling for property managers. Same-day and next-day turnovers available.' },
      { step: 'Execution', detail: 'Crew clears the unit, handles all sorting, and leaves the space broom-clean.' },
      { step: 'Documentation', detail: 'Photo documentation before and after. Inventory of removed items for tenant records.' }
    ],
    benefits: ['Property manager accounts with priority scheduling', 'Photo documentation before and after every job', 'Monthly billing available for volume clients', 'Same-day unit turnovers available', 'Abandoned property documentation for legal records', 'No minimum commitment — use us when needed'],
    faqs: [
      { q: 'Do you handle eviction cleanouts?', a: 'Yes. We handle eviction cleanouts sensitively and efficiently. We document all removed items with photos, which can be important for legal proceedings. We do not enter units without proper authorization.' },
      { q: 'How fast can you turn over a unit?', a: 'Most one-bedroom apartments can be cleared in 1-2 hours. We offer same-day service for property managers and can often accommodate morning requests the same day.' },
      { q: 'Do you offer monthly billing for multiple properties?', a: 'Yes. Property management companies with regular volume can set up monthly billing accounts with discounted rates. Contact us to discuss your portfolio size.' },
      { q: 'What documentation do you provide for abandoned property?', a: 'We provide photo documentation before removal, an itemized list of removed items, and a completion certificate. This supports tenant dispute resolution and legal compliance.' },
      { q: 'Can you handle emergency same-day cleanouts?', a: 'Yes. Property managers with urgent turnover needs can call (561) 944-1636 for priority dispatch. We keep same-day slots reserved for commercial accounts.' }
    ]
  },
  {
    slug: 'hoa-services',
    name: 'HOA Junk Removal Services',
    tagline: 'Junk Removal &amp; Bulk Waste Services for HOAs in South Florida',
    desc: 'Reliable junk removal and bulk waste services for homeowners associations across Palm Beach, Broward, and Miami-Dade. Bulk item collection, common area cleanouts, community event cleanups, and recurring schedules. From $199.',
    items: ['Bulk Furniture Left at Curb', 'Common Area Furniture &amp; Fixtures', 'Pool Deck Equipment &amp; Furniture', 'Clubhouse Cleanouts', 'Community Event Cleanup', 'Landscape &amp; Yard Waste', 'Construction Debris from Common Areas', 'Storage Room Cleanouts'],
    pricing: { min: 199, avg: 550, max: 2500, note: 'Monthly HOA contracts available. Bulk item collection programs priced per community size.' },
    industries: ['Gated Residential Communities', 'Condo Associations', 'Townhome Communities', 'Active Adult Communities (55+)', 'Master-Planned Communities', 'Urban Loft &amp; Condo Buildings', 'Student Housing Associations', 'Mixed-Use Community Associations'],
    process: [
      { step: 'Assessment', detail: 'We meet with your HOA manager and assess bulk waste volumes and frequency.' },
      { step: 'Scheduling', detail: 'Set up recurring monthly or quarterly bulk removal dates. Emergency pickups available.' },
      { step: 'Execution', detail: 'Crew handles all loading, sorting, and hauling. No debris left behind.' },
      { step: 'Documentation', detail: 'Monthly reports with volumes removed, recycling rates, and cost summaries for board meetings.' }
    ],
    benefits: ['Monthly HOA contracts with fixed pricing', 'Bulk item collection program setup', 'Recycling and donation reporting for sustainability goals', 'Emergency same-day pickups for violations', 'Coordinate with landscaping and maintenance vendors', 'Quarterly bulk waste events for residents'],
    faqs: [
      { q: 'Can you set up a recurring bulk item collection program for our HOA?', a: 'Yes. We set up monthly or quarterly scheduled pickups for HOAs. Residents are notified of the schedule and bulk items are collected from designated areas on pickup day.' },
      { q: 'How do you handle HOA bulk item violations?', a: 'For urgent violations where a resident has left items that violate HOA rules, we offer same-day or next-day emergency pickups. We document before and after with photos.' },
      { q: 'Do you provide sustainability reporting for our HOA?', a: 'Yes. Monthly recycling and donation reports are available. Many HOAs use these for their sustainability initiatives and board meeting disclosures.' },
      { q: 'Can you handle a full clubhouse or amenity area cleanout?', a: 'Yes. Clubhouse furniture, pool deck equipment, fitness center equipment, and common area contents are all within our scope. We schedule around peak amenity hours.' },
      { q: 'What are typical HOA contract pricing ranges?', a: 'Small HOAs (under 100 units) typically spend $199-399/month. Mid-size communities (100-500 units) average $399-799/month. Large master-planned communities receive custom pricing based on volume.' }
    ]
  }
];

function buildFAQSchema(faqs) {
  const entities = faqs.map(f => `{"@type":"Question","name":"${f.q.replace(/"/g, '&quot;')}","acceptedAnswer":{"@type":"Answer","text":"${f.a.replace(/"/g, '&quot;')}"}}`);
  return `<script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[${entities.join(',')}]}</script>`;
}

function buildServiceSchema(service) {
  return `<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Service","serviceType":"${service.name}","provider":{"@type":"Organization","name":"Umuve","url":"https://goumuve.com","logo":"https://goumuve.com/logo-full.png","telephone":"+15619441636"},"areaServed":{"@type":"State","name":"Florida"},"offers":{"@type":"AggregateOffer","lowPrice":"${service.pricing.min}","highPrice":"${service.pricing.max}","priceCurrency":"USD"},"description":"${service.desc.replace(/"/g,'&quot;')}"}
</script>`;
}

function generateServicePage(service) {
  const canonical = `/commercial/${service.slug}`;
  const schema = buildServiceSchema(service) + '\n' + buildFAQSchema(service.faqs);

  return `${HEAD_COMMON(service.name + ' in South Florida — Commercial Service | Umuve', service.desc, canonical, schema)}
<body>
${NAV()}

<!-- Hero -->
<section style="padding:4rem 0 3rem;background:linear-gradient(135deg,#1e3a5f 0%,#1e40af 100%);color:#fff">
<div class="container"><div style="max-width:800px">
<nav style="margin-bottom:1rem;font-size:0.85rem;opacity:0.8">
<a href="/" style="color:#93c5fd;text-decoration:none">Home</a> &rsaquo;
<a href="/commercial" style="color:#93c5fd;text-decoration:none">Commercial</a> &rsaquo;
<span>${service.name}</span>
</nav>
<div style="display:inline-block;background:rgba(255,255,255,0.15);padding:0.35rem 1rem;border-radius:9999px;font-size:0.85rem;font-weight:600;margin-bottom:1rem">Commercial Service</div>
<h1 style="font-family:Outfit;font-size:clamp(1.75rem,4vw,3rem);font-weight:800;margin-bottom:1.25rem;line-height:1.2">${service.tagline}</h1>
<p style="font-size:1.1rem;opacity:0.92;margin-bottom:2rem;line-height:1.7">${service.desc}</p>
<div style="display:flex;flex-wrap:wrap;gap:1rem;align-items:center">
<a href="https://app.goumuve.com/book" style="background:#DC2626;color:#fff;padding:1rem 2rem;font-weight:700;border-radius:0.5rem;text-decoration:none;font-size:1.05rem">Get a Commercial Quote</a>
<a href="tel:5619441636" style="background:rgba(255,255,255,0.15);color:#fff;padding:1rem 2rem;font-weight:600;border-radius:0.5rem;text-decoration:none">(561) 944-1636</a>
</div>
</div></div></section>

<!-- Pricing Banner -->
<section style="background:#f9fafb;border-bottom:1px solid rgba(0,0,0,0.06);padding:1.5rem 0">
<div class="container"><div style="display:flex;flex-wrap:wrap;gap:2rem;align-items:center;justify-content:center">
<div style="text-align:center"><div style="font-size:1.5rem;font-weight:800;color:#DC2626;font-family:Outfit">$${service.pricing.min}+</div><div style="font-size:0.8rem;color:#6b7280">Starting price</div></div>
<div style="width:1px;height:40px;background:#e5e7eb"></div>
<div style="text-align:center"><div style="font-size:1.5rem;font-weight:800;color:#1e40af;font-family:Outfit">$${service.pricing.avg}</div><div style="font-size:0.8rem;color:#6b7280">Average job</div></div>
<div style="width:1px;height:40px;background:#e5e7eb"></div>
<div style="text-align:center"><div style="font-size:1.5rem;font-weight:800;color:#374151;font-family:Outfit">Same-Day</div><div style="font-size:0.8rem;color:#6b7280">Available</div></div>
<div style="width:1px;height:40px;background:#e5e7eb"></div>
<div style="text-align:center"><div style="font-size:1.5rem;font-weight:800;color:#374151;font-family:Outfit">Insured</div><div style="font-size:0.8rem;color:#6b7280">Commercial grade</div></div>
</div></div></section>

<!-- What's Included -->
<section style="padding:4rem 0">
<div class="container"><div style="max-width:900px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.75rem">What We Remove</h2>
<p style="color:#6b7280;margin-bottom:2rem">All-inclusive pricing. No hidden fees. We handle all loading, hauling, and disposal.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:1rem">
${service.items.map(item => `<div style="display:flex;align-items:center;gap:0.75rem;padding:1rem;background:#f9fafb;border-radius:0.75rem;border:1px solid rgba(0,0,0,0.06)"><span style="color:#DC2626;font-weight:700;font-size:1.1rem">&#10003;</span><span style="font-weight:500;color:#374151">${item}</span></div>`).join('\n')}
</div>
</div></div></section>

<!-- Pricing -->
<section style="padding:4rem 0;background:#f9fafb">
<div class="container"><div style="max-width:700px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.75rem;text-align:center">Transparent Commercial Pricing</h2>
<p style="color:#6b7280;text-align:center;margin-bottom:2rem">${service.pricing.note}</p>
<div style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:1rem;overflow:hidden">
<table style="width:100%;border-collapse:collapse">
<thead style="background:#1e3a5f;color:#fff">
<tr><th style="padding:1rem 1.5rem;text-align:left">Job Size</th><th style="padding:1rem 1.5rem;text-align:center">Typical Price Range</th><th style="padding:1rem 1.5rem;text-align:center">Crew Size</th></tr>
</thead>
<tbody>
<tr style="border-bottom:1px solid rgba(0,0,0,0.06)"><td style="padding:1rem 1.5rem;font-weight:500">Small (1-2 rooms)</td><td style="padding:1rem 1.5rem;text-align:center;color:#DC2626;font-weight:600">$${service.pricing.min}–${Math.round(service.pricing.avg * 0.7)}</td><td style="padding:1rem 1.5rem;text-align:center">2 crew</td></tr>
<tr style="border-bottom:1px solid rgba(0,0,0,0.06);background:#f9fafb"><td style="padding:1rem 1.5rem;font-weight:500">Medium (full floor)</td><td style="padding:1rem 1.5rem;text-align:center;color:#DC2626;font-weight:600">$${Math.round(service.pricing.avg * 0.7)}–${service.pricing.avg}</td><td style="padding:1rem 1.5rem;text-align:center">3 crew</td></tr>
<tr style="border-bottom:1px solid rgba(0,0,0,0.06)"><td style="padding:1rem 1.5rem;font-weight:500">Large (multiple floors)</td><td style="padding:1rem 1.5rem;text-align:center;color:#DC2626;font-weight:600">$${service.pricing.avg}–${service.pricing.max}</td><td style="padding:1rem 1.5rem;text-align:center">4-6 crew</td></tr>
<tr><td style="padding:1rem 1.5rem;font-weight:500">Custom / Multi-day</td><td style="padding:1rem 1.5rem;text-align:center;color:#1e40af;font-weight:600">Custom quote</td><td style="padding:1rem 1.5rem;text-align:center">Multiple crews</td></tr>
</tbody>
</table>
</div>
<p style="text-align:center;margin-top:1.5rem;color:#6b7280;font-size:0.875rem">All prices include labor, truck, fuel, and disposal. No surprises.</p>
</div></div></section>

<!-- Why Umuve for Commercial -->
<section style="padding:4rem 0">
<div class="container"><div style="max-width:900px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.75rem">Why Businesses Choose Umuve</h2>
<p style="color:#6b7280;margin-bottom:2rem">We operate differently than residential junk haulers. Here is what commercial clients get.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1.5rem">
${service.benefits.map(b => `<div style="padding:1.5rem;background:#f9fafb;border-radius:0.75rem;border-left:4px solid #1e40af">
<p style="font-weight:600;color:#374151;margin:0">${b}</p>
</div>`).join('\n')}
</div>
</div></div></section>

<!-- Industries We Serve -->
<section style="padding:4rem 0;background:#f9fafb">
<div class="container"><div style="max-width:900px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.75rem">Industries We Serve</h2>
<p style="color:#6b7280;margin-bottom:2rem">Specialized handling for every commercial sector.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem">
${service.industries.map(ind => `<div style="padding:1rem 1.25rem;background:#fff;border-radius:0.75rem;border:1px solid rgba(0,0,0,0.08);font-weight:500;color:#374151;font-size:0.9rem">${ind}</div>`).join('\n')}
</div>
</div></div></section>

<!-- Process -->
<section style="padding:4rem 0">
<div class="container"><div style="max-width:800px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.75rem">How It Works</h2>
<p style="color:#6b7280;margin-bottom:2rem">Simple 4-step process designed for commercial clients.</p>
<div style="display:grid;gap:1.5rem">
${service.process.map((p, i) => `<div style="display:flex;gap:1.5rem;align-items:flex-start;padding:1.5rem;background:#f9fafb;border-radius:0.75rem">
<div style="min-width:2.5rem;height:2.5rem;background:#1e3a5f;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-family:Outfit">${i + 1}</div>
<div><h3 style="font-family:Outfit;font-size:1.125rem;font-weight:700;margin:0 0 0.5rem">${p.step}</h3><p style="color:#6b7280;margin:0;line-height:1.6">${p.detail}</p></div>
</div>`).join('\n')}
</div>
</div></div></section>

<!-- FAQ -->
<section style="padding:4rem 0;background:#f9fafb">
<div class="container"><div style="max-width:800px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:2rem">Frequently Asked Questions</h2>
<div style="display:grid;gap:1rem">
${service.faqs.map(f => `<div style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:0.75rem;padding:1.5rem">
<h3 style="font-family:Outfit;font-size:1rem;font-weight:700;margin:0 0 0.75rem;color:#1e3a5f">${f.q}</h3>
<p style="color:#6b7280;margin:0;line-height:1.7">${f.a}</p>
</div>`).join('\n')}
</div>
</div></div></section>

<!-- CTA -->
<section style="padding:4rem 0;background:linear-gradient(135deg,#1e3a5f,#1e40af);color:#fff;text-align:center">
<div class="container">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:1rem">Ready to Get a Commercial Quote?</h2>
<p style="font-size:1.125rem;margin-bottom:2rem;opacity:0.92">We respond within 30 minutes. After-hours and weekend jobs available.</p>
<div style="display:flex;flex-wrap:wrap;gap:1rem;justify-content:center">
<a href="https://app.goumuve.com/book" style="background:#DC2626;color:#fff;padding:1rem 2.5rem;font-weight:700;border-radius:0.5rem;text-decoration:none;font-size:1.05rem">Get a Quote Online</a>
<a href="tel:5619441636" style="background:rgba(255,255,255,0.15);color:#fff;padding:1rem 2.5rem;font-weight:600;border-radius:0.5rem;text-decoration:none">Call (561) 944-1636</a>
</div>
</div></section>

<!-- Internal Links -->
<section style="padding:3rem 0">
<div class="container"><div style="max-width:900px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:1.5rem;font-weight:700;margin-bottom:1.5rem">Explore More Commercial Services</h2>
<div style="display:flex;flex-wrap:wrap;gap:0.75rem">
${COMMERCIAL_SERVICES.filter(s => s.slug !== service.slug).map(s => `<a href="/commercial/${s.slug}" style="padding:0.5rem 1rem;background:#f3f4f6;color:#374151;text-decoration:none;border-radius:0.5rem;font-size:0.875rem;font-weight:500">${s.name}</a>`).join('\n')}
<a href="/services/furniture-removal" style="padding:0.5rem 1rem;background:#f3f4f6;color:#374151;text-decoration:none;border-radius:0.5rem;font-size:0.875rem;font-weight:500">Furniture Removal</a>
<a href="/services/estate-cleanout" style="padding:0.5rem 1rem;background:#f3f4f6;color:#374151;text-decoration:none;border-radius:0.5rem;font-size:0.875rem;font-weight:500">Estate Cleanout</a>
<a href="/pricing" style="padding:0.5rem 1rem;background:#f3f4f6;color:#374151;text-decoration:none;border-radius:0.5rem;font-size:0.875rem;font-weight:500">Full Pricing Guide</a>
</div>
</div></div></section>

${FOOTER()}
</body>
</html>`;
}

function generateHubPage() {
  const canonical = '/commercial';
  const title = 'Commercial Junk Removal Services in South Florida | Umuve';
  const desc = 'Professional commercial junk removal services across Palm Beach, Broward, and Miami-Dade. Office cleanouts, retail, construction debris, restaurant cleanouts, warehouse cleanouts, property management, and HOA services. Insured. After-hours available.';

  const breadcrumbSchema = `<script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://goumuve.com"},{"@type":"ListItem","position":2,"name":"Commercial Services","item":"https://goumuve.com/commercial"}]}</script>`;

  const faqSchema = `<script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
{"@type":"Question","name":"Do you offer commercial junk removal services?","acceptedAnswer":{"@type":"Answer","text":"Yes. Umuve specializes in commercial junk removal across Palm Beach, Broward, and Miami-Dade counties. Services include office cleanouts, retail store cleanouts, restaurant cleanouts, warehouse cleanouts, construction debris removal, property management cleanouts, and HOA bulk waste services."}},
{"@type":"Question","name":"Are your commercial services insured?","acceptedAnswer":{"@type":"Answer","text":"Yes. All Umuve operators carry commercial general liability insurance and workers compensation. We provide insurance documentation upon request for corporate and property management clients."}},
{"@type":"Question","name":"Can you schedule after-hours or weekend commercial cleanouts?","acceptedAnswer":{"@type":"Answer","text":"Yes. After-hours (evenings after 6 PM) and weekend scheduling is available for all commercial services. Most office and retail cleanouts are scheduled after business hours to minimize disruption."}},
{"@type":"Question","name":"Do you offer recurring commercial contracts?","acceptedAnswer":{"@type":"Answer","text":"Yes. Monthly and quarterly contracts are available for property managers, HOAs, contractors, and businesses with ongoing junk removal needs. Volume discounts apply."}}
]}</script>`;

  return `${HEAD_COMMON(title, desc, canonical, breadcrumbSchema + '\n' + faqSchema)}
<body>
${NAV()}

<!-- Hero -->
<section style="padding:4rem 0 3rem;background:linear-gradient(135deg,#1e3a5f 0%,#1e40af 100%);color:#fff">
<div class="container"><div style="max-width:800px">
<nav style="margin-bottom:1rem;font-size:0.85rem;opacity:0.8">
<a href="/" style="color:#93c5fd;text-decoration:none">Home</a> &rsaquo;
<span>Commercial Services</span>
</nav>
<div style="display:inline-block;background:rgba(255,255,255,0.15);padding:0.35rem 1rem;border-radius:9999px;font-size:0.85rem;font-weight:600;margin-bottom:1rem">South Florida Commercial Junk Removal</div>
<h1 style="font-family:Outfit;font-size:clamp(1.75rem,4vw,3rem);font-weight:800;margin-bottom:1.25rem;line-height:1.2">Commercial Junk Removal Services</h1>
<p style="font-size:1.1rem;opacity:0.92;margin-bottom:2rem;line-height:1.7">Professional, insured commercial cleanout services across Palm Beach, Broward, and Miami-Dade. Office cleanouts, retail, restaurants, warehouses, property management, and HOA services. After-hours available.</p>
<div style="display:flex;flex-wrap:wrap;gap:1rem;align-items:center">
<a href="https://app.goumuve.com/book" style="background:#DC2626;color:#fff;padding:1rem 2rem;font-weight:700;border-radius:0.5rem;text-decoration:none;font-size:1.05rem">Get a Commercial Quote</a>
<a href="tel:5619441636" style="background:rgba(255,255,255,0.15);color:#fff;padding:1rem 2rem;font-weight:600;border-radius:0.5rem;text-decoration:none">(561) 944-1636</a>
</div>
</div></div></section>

<!-- Trust Bar -->
<section style="background:#f9fafb;border-bottom:1px solid rgba(0,0,0,0.06);padding:1.5rem 0">
<div class="container"><div style="display:flex;flex-wrap:wrap;gap:2rem;align-items:center;justify-content:center">
<div style="text-align:center"><div style="font-size:1.3rem;font-weight:800;color:#1e3a5f;font-family:Outfit">500+</div><div style="font-size:0.8rem;color:#6b7280">Local Operators</div></div>
<div style="width:1px;height:40px;background:#e5e7eb"></div>
<div style="text-align:center"><div style="font-size:1.3rem;font-weight:800;color:#1e3a5f;font-family:Outfit">Fully Insured</div><div style="font-size:0.8rem;color:#6b7280">Commercial GL + WC</div></div>
<div style="width:1px;height:40px;background:#e5e7eb"></div>
<div style="text-align:center"><div style="font-size:1.3rem;font-weight:800;color:#1e3a5f;font-family:Outfit">After-Hours</div><div style="font-size:0.8rem;color:#6b7280">Evenings &amp; weekends</div></div>
<div style="width:1px;height:40px;background:#e5e7eb"></div>
<div style="text-align:center"><div style="font-size:1.3rem;font-weight:800;color:#1e3a5f;font-family:Outfit">Same-Day</div><div style="font-size:0.8rem;color:#6b7280">Slots available</div></div>
</div></div></section>

<!-- Services Grid -->
<section style="padding:4rem 0">
<div class="container">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.75rem;text-align:center">Commercial Services</h2>
<p style="color:#6b7280;text-align:center;margin-bottom:3rem;max-width:600px;margin-left:auto;margin-right:auto">From single-room office cleanouts to multi-day warehouse projects. All fully insured and commercially priced.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1.5rem">
${COMMERCIAL_SERVICES.map(s => `<a href="/commercial/${s.slug}" style="text-decoration:none;color:inherit">
<div style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:1rem;padding:2rem;transition:box-shadow 0.2s;cursor:pointer" onmouseover="this.style.boxShadow='0 8px 25px rgba(0,0,0,0.12)'" onmouseout="this.style.boxShadow='none'">
<div style="width:3rem;height:3rem;background:linear-gradient(135deg,#1e3a5f,#1e40af);border-radius:0.75rem;display:flex;align-items:center;justify-content:center;margin-bottom:1.25rem">
<span style="color:#fff;font-weight:800;font-size:1rem;font-family:Outfit">${s.name.charAt(0)}</span>
</div>
<h3 style="font-family:Outfit;font-size:1.125rem;font-weight:700;margin:0 0 0.75rem">${s.name}</h3>
<p style="color:#6b7280;font-size:0.9rem;margin:0 0 1rem;line-height:1.6">${s.desc.substring(0, 120)}...</p>
<div style="display:flex;justify-content:space-between;align-items:center">
<span style="color:#DC2626;font-weight:700;font-size:0.9rem">From $${s.pricing.min}</span>
<span style="color:#1e40af;font-size:0.875rem;font-weight:600">Learn more &rarr;</span>
</div>
</div>
</a>`).join('\n')}
</div>
</div></section>

<!-- Industries -->
<section style="padding:4rem 0;background:#f9fafb">
<div class="container">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:0.75rem;text-align:center">Industries We Serve</h2>
<p style="color:#6b7280;text-align:center;margin-bottom:2.5rem">We have specialized experience across every major commercial sector in South Florida.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem;max-width:1000px;margin:0 auto">
${['Law Firms &amp; Professional Services', 'Medical &amp; Dental Offices', 'Restaurants &amp; Food Service', 'Retail &amp; Storefront Spaces', 'Warehouses &amp; Distribution', 'Property Management Companies', 'HOA &amp; Community Associations', 'Hotels &amp; Hospitality', 'Construction &amp; Contracting', 'Tech Companies &amp; Startups', 'Government &amp; Municipal', 'Financial &amp; Insurance Services'].map(i => `<div style="padding:0.875rem 1rem;background:#fff;border-radius:0.75rem;border:1px solid rgba(0,0,0,0.08);font-weight:500;color:#374151;font-size:0.875rem;text-align:center">${i}</div>`).join('\n')}
</div>
</div></section>

<!-- Trust Section -->
<section style="padding:4rem 0">
<div class="container"><div style="max-width:900px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:2rem;text-align:center">What Sets Our Commercial Service Apart</h2>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1.5rem">
${[
  {title:'Commercially Insured', body:'Every operator carries commercial GL and workers comp. We provide certificates of insurance on request for corporate procurement requirements.'},
  {title:'After-Hours Scheduling', body:'Evenings, weekends, and early morning slots available. Your business stays open. We work around your hours, not the other way around.'},
  {title:'Documentation Standard', body:'Certificates of removal, recycling reports, and donation receipts for every job. Meets corporate compliance and property management requirements.'},
  {title:'Volume Pricing', body:'Monthly accounts, recurring schedules, and contractor packages available. The more you use us, the better the rate. No minimums to start.'}
].map(t => `<div style="padding:1.75rem;background:#f9fafb;border-radius:0.75rem">
<h3 style="font-family:Outfit;font-size:1.125rem;font-weight:700;margin:0 0 0.75rem;color:#1e3a5f">${t.title}</h3>
<p style="color:#6b7280;margin:0;line-height:1.7;font-size:0.95rem">${t.body}</p>
</div>`).join('\n')}
</div>
</div></div></section>

<!-- FAQ -->
<section style="padding:4rem 0;background:#f9fafb">
<div class="container"><div style="max-width:800px;margin:0 auto">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:2rem">Commercial Service FAQs</h2>
<div style="display:grid;gap:1rem">
${[
  {q:'Do you offer commercial junk removal services?', a:'Yes. Umuve specializes in commercial junk removal across Palm Beach, Broward, and Miami-Dade counties. Services include office cleanouts, retail store cleanouts, restaurant cleanouts, warehouse cleanouts, construction debris removal, property management cleanouts, and HOA bulk waste services.'},
  {q:'Are your commercial services insured?', a:'Yes. All Umuve operators carry commercial general liability insurance and workers compensation. We provide insurance documentation upon request for corporate and property management clients.'},
  {q:'Can you schedule after-hours or weekend commercial cleanouts?', a:'Yes. After-hours (evenings after 6 PM) and weekend scheduling is available for all commercial services. Most office and retail cleanouts are scheduled after business hours to minimize disruption.'},
  {q:'Do you offer recurring commercial contracts?', a:'Yes. Monthly and quarterly contracts are available for property managers, HOAs, contractors, and businesses with ongoing junk removal needs. Volume discounts apply.'},
  {q:'How do commercial prices compare to residential?', a:'Commercial services are priced differently due to volume, scheduling complexity, insurance requirements, and documentation standards. Commercial jobs typically start at $299 and scale with the size of the project. Call for a custom quote.'}
].map(f => `<div style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:0.75rem;padding:1.5rem">
<h3 style="font-family:Outfit;font-size:1rem;font-weight:700;margin:0 0 0.75rem;color:#1e3a5f">${f.q}</h3>
<p style="color:#6b7280;margin:0;line-height:1.7">${f.a}</p>
</div>`).join('\n')}
</div>
</div></div></section>

<!-- CTA -->
<section style="padding:4rem 0;background:linear-gradient(135deg,#1e3a5f,#1e40af);color:#fff;text-align:center">
<div class="container">
<h2 style="font-family:Outfit;font-size:2rem;font-weight:800;margin-bottom:1rem">Get a Commercial Quote Today</h2>
<p style="font-size:1.125rem;margin-bottom:2rem;opacity:0.92">We respond within 30 minutes. After-hours and weekend jobs available across all of South Florida.</p>
<div style="display:flex;flex-wrap:wrap;gap:1rem;justify-content:center">
<a href="https://app.goumuve.com/book" style="background:#DC2626;color:#fff;padding:1rem 2.5rem;font-weight:700;border-radius:0.5rem;text-decoration:none;font-size:1.05rem">Request a Quote</a>
<a href="tel:5619441636" style="background:rgba(255,255,255,0.15);color:#fff;padding:1rem 2.5rem;font-weight:600;border-radius:0.5rem;text-decoration:none">Call (561) 944-1636</a>
</div>
</div></section>

${FOOTER()}
</body>
</html>`;
}

// Create output directory
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// Generate hub
fs.writeFileSync(path.join(OUTPUT_DIR, 'index.html'), generateHubPage());
console.log('Generated: commercial/index.html');

// Generate service pages
for (const service of COMMERCIAL_SERVICES) {
  const html = generateServicePage(service);
  fs.writeFileSync(path.join(OUTPUT_DIR, `${service.slug}.html`), html);
  console.log(`Generated: commercial/${service.slug}.html`);
}

console.log(`\nPhase 4 complete: ${COMMERCIAL_SERVICES.length + 1} pages generated in /commercial/`);

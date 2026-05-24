#!/usr/bin/env node

/**
 * Umuve How-To Disposal Guide Generator
 * Generates 30 informational guide pages to /guides/{slug}.html
 */

const fs = require('fs');
const path = require('path');

const PHONE = '(561) 944-1636';
const SMS = '(844) 435-6005';
const BOOK_URL = 'https://app.goumuve.com/book';
const SITE = 'https://goumuve.com';
const GA4 = 'G-CLGPJ5TS3G';
const PIXEL = '1785795592383973';
const DATE = 'April 2026';
const DATE_ISO = '2026-04-06';

// ─── Guide Data ────────────────────────────────────────────────────────────────

const guides = [
  {
    slug: 'how-to-dispose-of-a-mattress',
    title: 'How to Dispose of a Mattress in South Florida (2026)',
    metaDescription: 'Learn how to dispose of a mattress in South Florida. Compare professional pickup, county curbside, donation, and DIY options. Costs, county rules, and eco tips.',
    h1: 'How to Dispose of a Mattress in South Florida',
    subtitle: 'Your complete 2026 guide to mattress disposal across Palm Beach, Broward, and Miami-Dade counties.',
    quickAnswer: 'The fastest way to dispose of a mattress in South Florida is professional pickup — Umuve hauls it same-day starting at $89, handles all transport, and recycles 89% of materials. Free curbside pickup is available in all three counties but requires advance scheduling and specific placement rules. Donation is possible if the mattress is stain-free and structurally sound.',
    serviceSlug: 'mattress-disposal',
    serviceName: 'Mattress Disposal',
    relatedGuides: [
      { slug: 'how-to-dispose-of-a-couch', title: 'How to Dispose of a Couch' },
      { slug: 'how-to-take-apart-a-bed-frame', title: 'How to Take Apart a Bed Frame' },
      { slug: 'declutter-before-moving', title: 'Declutter Before Moving' },
      { slug: 'estate-cleanout-checklist', title: 'Estate Cleanout Checklist' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
    toc: [
      { id: 'professional', label: 'Option 1: Professional Removal' },
      { id: 'curbside', label: 'Option 2: Municipal Curbside' },
      { id: 'donation', label: 'Option 3: Donation' },
      { id: 'diy', label: 'Option 4: DIY Disposal' },
      { id: 'cost-comparison', label: 'Cost Comparison' },
      { id: 'environmental', label: 'Environmental Impact' },
      { id: 'mistakes', label: 'Common Mistakes' },
      { id: 'faq', label: 'FAQ' },
    ],
    professional: {
      price: '$89 – $199',
      description: 'Umuve picks up your mattress same-day from anywhere in your home — bedroom, upstairs, storage unit. No prep needed. Two-person crews handle king-sized mattresses, bunk beds, and adjustable bases without damage to walls or floors. The mattress is wrapped, loaded, and taken to a certified mattress recycling facility where steel springs, foam, and fabric are separated for recovery.',
      includes: ['Full labor and carrying', 'Same-day service available', 'Recycling or donation of usable mattresses', 'No prep or disassembly needed', 'All hauling and disposal fees'],
    },
    curbside: {
      palmBeach: 'Palm Beach County Solid Waste Authority (SWA) allows up to 2 bulk items per scheduled pickup. Schedule at pbcswa.com or call (561) 697-2700. Mattresses must be placed at the curb by 6 AM on pickup day. Bed bugs or visible infestation may result in rejection — bag the mattress in plastic if there is any concern.',
      broward: 'Broward County Municipal Services requires you to schedule bulk pickup through your specific city (not the county). Most cities allow 4-6 bulk items. Fort Lauderdale residents call (954) 828-5150. Typical wait is 5-10 business days. Mattresses exceeding 60 inches wide may be refused — check with your city.',
      miamiDade: 'Miami-Dade County solid waste allows 2 bulk items per week curbside without scheduling for most unincorporated areas. City of Miami residents call 311. Miami Beach has specific bulk pickup days by neighborhood — check miamigov.com/solidwaste. Mattresses must be set out no earlier than the night before pickup.',
    },
    donation: 'Mattresses can be donated if they are stain-free, bed bug-free, and structurally intact (no broken springs or torn fabric). Habitat for Humanity ReStores in South Florida accept mattresses in good condition — call your local ReStore to confirm. Goodwill locations in Miami-Dade accept twin and full mattresses but rarely queen or king due to storage constraints. The Salvation Army accepts queen and king mattresses with advance arrangement. St. Vincent de Paul thrift stores in Broward County are worth calling if other options are full.',
    diy: 'DIY mattress disposal means either hauling it yourself to a county transfer station or breaking it down for easier transport. Renting a pickup truck from U-Haul or Home Depot costs $19-$40 for a few hours. Transfer station fees in South Florida run $30-$75 per mattress depending on county. Breaking down a mattress: cut the fabric cover off with a utility knife, remove and separate the foam (can go in regular trash in small bags), and take the steel spring coil to a scrap metal recycler — they often pay $5-$15 per unit. Memory foam mattresses have no spring coil and must go to a foam recycler or the landfill.',
    costTable: [
      { method: 'Umuve Professional Pickup', cost: '$89 – $199', time: 'Same day', effort: 'Zero', eco: '89% recycled' },
      { method: 'County Curbside', cost: 'Free', time: '5–14 days wait', effort: 'Move to curb', eco: 'Landfill likely' },
      { method: 'Donation (Habitat/Goodwill)', cost: 'Free', time: '2–7 days', effort: 'Transport required', eco: 'Best if accepted' },
      { method: 'DIY Haul to Transfer Station', cost: '$50 – $120', time: 'Half-day', effort: 'High', eco: 'Mostly landfill' },
    ],
    environmental: 'Mattresses are one of the most problematic landfill items — a single queen mattress takes up 40+ cubic feet of space and contains materials that take centuries to break down. South Florida sends roughly 400,000 mattresses to landfill each year. When recycled properly, a queen mattress yields approximately 25 lbs of steel (melted for rebar and new steel products), 15 lbs of foam (repurposed as carpet padding), and 3 lbs of fabric fiber (used in industrial rags or insulation). Umuve recycles 89% of every mattress it collects, diverting an average of 43 lbs of material per unit from South Florida landfills.',
    mistakes: [
      { title: 'Leaving it on the curb without scheduling', body: 'Unscheduled bulk items left at the curb can earn you a code enforcement citation in most South Florida cities. HOA violations typically run $50-$200 per day. Always call your city or schedule online before putting anything on the curb.' },
      { title: 'Donating a mattress that will be rejected', body: 'Most charities inspect mattresses on arrival. Any visible stain, odor, or structural damage results in rejection. You will then need to haul it somewhere else. When in doubt, book professional pickup.' },
      { title: 'Assuming a hotel will take your old mattress', body: 'Hotels and furnished rental operators will not accept used residential mattresses due to liability and health code requirements. This is a common misconception.' },
      { title: 'Illegally dumping', body: 'South Florida counties issue $500–$10,000 fines for illegal dumping of mattresses. Cameras at popular dump sites result in hundreds of citations per year. The fine is never worth it when free curbside or $89 professional pickup exist.' },
    ],
    faqs: [
      { q: 'How much does it cost to dispose of a mattress in South Florida?', a: 'Professional pickup starts at $89 for a twin or full and runs up to $199 for a king or adjustable base. County curbside is free with 5-14 day scheduling. DIY haul to a transfer station costs $50-$120 including truck rental and dump fees.' },
      { q: 'Can I leave a mattress on the curb in South Florida?', a: 'Only after scheduling with your municipality. Unscheduled bulk items can result in code enforcement citations of $50-$200 per day. Palm Beach SWA, Broward cities, and Miami-Dade all require advance scheduling for bulk pickup.' },
      { q: 'Does Habitat for Humanity take mattresses?', a: 'Habitat for Humanity ReStores accept mattresses in excellent condition — no stains, no odor, no structural damage. Call your local ReStore before transporting, as acceptance varies by location and current inventory.' },
      { q: 'How long does same-day mattress pickup take with Umuve?', a: 'Most pickups take 15-30 minutes from arrival. You book online, we give you a 2-hour arrival window, and two crew members carry the mattress from anywhere in your home and load it. No prep needed.' },
      { q: 'What happens to a recycled mattress?', a: 'At certified mattress recycling facilities, the mattress is disassembled by machine. Steel spring coils are separated and sent to scrap metal processors. Foam is compressed and sold to carpet pad manufacturers. Fabric cover is processed into industrial fiber. About 89% of materials are recovered.' },
      { q: 'Can Umuve remove a mattress that has bed bugs?', a: 'Yes. Inform us when booking. We use sealed mattress bags for transport to contain any infestation, and all crew members follow bed bug protocols. The mattress goes directly to a disposal facility, not recycling.' },
    ],
  },

  {
    slug: 'how-to-dispose-of-a-refrigerator',
    title: 'How to Dispose of a Refrigerator in South Florida (2026)',
    metaDescription: 'How to dispose of a refrigerator in South Florida legally. EPA refrigerant rules, county pickup options, utility rebates, and professional removal starting at $89.',
    h1: 'How to Dispose of a Refrigerator in South Florida',
    subtitle: 'EPA-compliant refrigerator disposal for Palm Beach, Broward, and Miami-Dade residents in 2026.',
    quickAnswer: 'Refrigerator disposal in South Florida requires EPA-compliant refrigerant recovery before the unit can be scrapped or landfilled. Professional removal by Umuve starts at $89 and includes all refrigerant handling and certified recycling. FPL and other utilities offer appliance rebates of $25-$50 for qualifying units. Free municipal pickup takes 5-14 days.',
    serviceSlug: 'refrigerator-disposal',
    serviceName: 'Refrigerator Disposal',
    relatedGuides: [
      { slug: 'how-to-dispose-of-appliances', title: 'How to Dispose of Appliances' },
      { slug: 'how-to-dispose-of-a-washer-dryer', title: 'How to Dispose of a Washer and Dryer' },
      { slug: 'how-to-dispose-of-a-dishwasher', title: 'How to Dispose of a Dishwasher' },
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'coral-springs-fl', name: 'Coral Springs' },
    ],
    toc: [
      { id: 'professional', label: 'Option 1: Professional Removal' },
      { id: 'curbside', label: 'Option 2: Municipal Curbside' },
      { id: 'donation', label: 'Option 3: Donation & Rebates' },
      { id: 'diy', label: 'Option 4: DIY Disposal' },
      { id: 'cost-comparison', label: 'Cost Comparison' },
      { id: 'environmental', label: 'Environmental Impact' },
      { id: 'mistakes', label: 'Common Mistakes' },
      { id: 'faq', label: 'FAQ' },
    ],
    professional: {
      price: '$89 – $249',
      description: 'Umuve handles the full refrigerator removal process — disconnection from water line and power, safe removal from your kitchen without floor or cabinet damage, transport to an EPA-certified recycling facility where refrigerants are properly recovered per Clean Air Act Section 608, and full materials recycling. No extra charges for refrigerant handling. Steel, copper, aluminum, and plastics are all separated for recovery.',
      includes: ['Water line and power disconnection', 'EPA-compliant refrigerant recovery at certified facility', 'Full labor and hauling', 'Same-day service', '95% materials recycled'],
    },
    curbside: {
      palmBeach: 'Palm Beach County SWA accepts refrigerators as bulk pickup items. Schedule at pbcswa.com. Important: the SWA requires refrigerant to be removed by a certified technician BEFORE placing the unit curbside. A licensed HVAC tech charges $50-$150 for this. Without certification, the unit may not be collected.',
      broward: 'Broward County cities accept refrigerators curbside with advance scheduling. However, most require proof that refrigerant has been evacuated or the unit must be tagged by the homeowner certifying it has been emptied. Contact your city solid waste department for specifics.',
      miamiDade: 'Miami-Dade County Solid Waste Management accepts refrigerators at their household hazardous waste drop-off events (free, held monthly). For curbside pickup, the unit must have its doors removed per federal law to prevent child entrapment hazards. Call 305-514-6830 to schedule.',
    },
    donation: 'Working refrigerators under 10 years old can often be donated. Habitat for Humanity ReStores in Broward and Palm Beach counties accept working refrigerators. The Salvation Army in Miami-Dade picks up working appliances. Check if your utility company — FPL, TECO, or Florida City Gas — has an appliance rebate program. FPL\'s Energy Efficiency program offers $25-$50 for qualifying refrigerators and freezers through their appliance recycling program. Call 800-226-3545 to schedule an FPL pickup.',
    diy: 'DIY disposal requires you to first have refrigerant evacuated by a licensed EPA Section 608 technician — illegal to release Freon into the atmosphere, with fines up to $44,539 per day. Once evacuated, you can haul the unit to a metal scrap yard (they pay $5-$20 per refrigerator), a county transfer station, or schedule free utility recycling. Renting an appliance dolly ($15-$25) is essential — modern refrigerators weigh 180-350 lbs. A friend is also necessary; never attempt to move a refrigerator solo.',
    costTable: [
      { method: 'Umuve Professional Pickup', cost: '$89 – $249', time: 'Same day', effort: 'Zero', eco: '95% recycled' },
      { method: 'FPL Appliance Recycling', cost: 'Free + $25-$50 rebate', time: '1–2 weeks', effort: 'Minimal', eco: 'Good' },
      { method: 'County Curbside (after Freon removal)', cost: '$50–$150 for tech + free pickup', time: '1–3 weeks', effort: 'Medium', eco: 'Partial recycling' },
      { method: 'Scrap Metal Yard', cost: 'Free (may pay $5–$20)', time: 'Same day if you haul', effort: 'High', eco: 'Good for metals' },
    ],
    environmental: 'Refrigerators contain chlorofluorocarbons (CFCs) or hydrofluorocarbons (HFCs) — ozone-depleting and greenhouse gases 1,000-3,000 times more potent than CO2. A single refrigerator contains enough refrigerant to damage the ozone layer if released. Proper recovery and destruction is mandatory. Beyond refrigerant, a full-size refrigerator contains 100-150 lbs of recyclable steel, 10-20 lbs of aluminum, 3-5 lbs of copper wiring, and 15-30 lbs of recyclable plastics. When you book with Umuve, 95% of these materials are recovered and recycled.',
    mistakes: [
      { title: 'Releasing refrigerant by opening Freon lines', body: 'Intentionally venting refrigerants violates the Clean Air Act. EPA fines start at $44,539 per violation per day. Never cut refrigerant lines yourself.' },
      { title: 'Leaving the doors on a discarded refrigerator', body: 'Federal law requires refrigerator doors to be removed before disposal to prevent child entrapment. Miami-Dade County enforces this strictly and will not collect units with doors attached unless a special tag is affixed.' },
      { title: 'Assuming your utility will pick it up for free without qualification', body: 'FPL\'s rebate program has age and condition requirements. Units over 15 years old may still qualify for recycling but not the cash rebate. Verify before scheduling.' },
      { title: 'Trying to move it alone', body: 'Refrigerators are top-heavy and weigh 180-350 lbs. Attempting to move one solo on tile or hardwood floors typically results in floor damage, cabinet dents, or personal injury. Use an appliance dolly and a second person.' },
    ],
    faqs: [
      { q: 'Is it legal to throw away a refrigerator in South Florida?', a: 'You cannot legally throw a refrigerator in the regular trash. Refrigerants must be properly recovered by an EPA-certified technician before disposal. All three South Florida counties have regulations requiring proper appliance disposal.' },
      { q: 'Does FPL pay me to take my old refrigerator?', a: 'Yes, in many cases. FPL\'s appliance recycling program offers $25-$50 for qualifying refrigerators and freezers. Call 800-226-3545. The unit must be operational and within their service territory.' },
      { q: 'How much does refrigerator removal cost in South Florida?', a: 'Professional removal by Umuve starts at $89 and includes all labor, hauling, and certified recycling. Adding a second unit reduces per-unit cost. DIY approaches cost $50-$150 after mandatory refrigerant evacuation fees.' },
      { q: 'Can Umuve disconnect my refrigerator\'s water line?', a: 'Yes. Our crews are trained to disconnect standard water line connections. If your refrigerator has a complex built-in water filtration system or unusual plumbing, we recommend having a plumber disconnect it before booking, though standard ice maker lines are no problem.' },
      { q: 'What recycling rate do refrigerators achieve?', a: 'At EPA-certified facilities, refrigerators achieve 95%+ recycling rates. Steel and aluminum are the primary recovered materials. Compressor oil, refrigerant, and insulating foam are also recovered. Only small amounts of mixed plastics and seals go to landfill.' },
      { q: 'How long does refrigerator pickup take with Umuve?', a: 'Most refrigerator removals take 20-30 minutes from arrival. We disconnect, remove, and load. You get a 2-hour arrival window and real-time tracking.' },
    ],
  },

  {
    slug: 'how-to-dispose-of-electronics',
    title: 'How to Dispose of Electronics in South Florida (2026)',
    metaDescription: 'How to dispose of electronics and e-waste in South Florida legally. Free drop-off locations, certified recyclers, data destruction, and pickup starting at $89.',
    h1: 'How to Dispose of Electronics (E-Waste) in South Florida',
    subtitle: 'Safe, legal, and eco-friendly electronics disposal across Palm Beach, Broward, and Miami-Dade in 2026.',
    quickAnswer: 'Florida law prohibits televisions, computers, and monitors from entering the regular trash. South Florida residents can use free county e-waste drop-off events, retail take-back programs (Best Buy, Staples), or professional pickup by Umuve starting at $89 with certified data destruction. Never place electronics at the curb as unscheduled e-waste.',
    serviceSlug: 'electronics-recycling',
    serviceName: 'Electronics Recycling',
    relatedGuides: [
      { slug: 'how-to-dispose-of-a-tv', title: 'How to Dispose of a TV' },
      { slug: 'how-to-dispose-of-appliances', title: 'How to Dispose of Appliances' },
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
      { slug: 'storage-unit-cleanout-guide', title: 'Storage Unit Cleanout Guide' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'pompano-beach-fl', name: 'Pompano Beach' },
    ],
    toc: [
      { id: 'professional', label: 'Option 1: Professional Removal' },
      { id: 'curbside', label: 'Option 2: Free Drop-Off & County Events' },
      { id: 'donation', label: 'Option 3: Donation & Trade-In' },
      { id: 'diy', label: 'Option 4: Retail Take-Back' },
      { id: 'cost-comparison', label: 'Cost Comparison' },
      { id: 'environmental', label: 'Environmental Impact' },
      { id: 'mistakes', label: 'Common Mistakes' },
      { id: 'faq', label: 'FAQ' },
    ],
    professional: {
      price: '$89 – $299',
      description: 'Umuve picks up all your old electronics in one visit — computers, monitors, printers, TVs, stereos, gaming systems, cables, and accessories. Everything goes to R2-certified recycling facilities. Hard drives and storage devices are physically destroyed or certified-wiped to NIST 800-88 standards. A certificate of destruction is available for business clients. Ideal when you have more than a few items or need data security.',
      includes: ['All e-waste types accepted', 'Certified data destruction for hard drives', 'R2-certified recycling facility', 'Certificate of destruction available', 'Same-day service'],
    },
    curbside: {
      palmBeach: 'Palm Beach County hosts free Household Hazardous Waste (HHW) and electronics drop-off events monthly. Check pbcswa.com/events for current schedule. Locations rotate between the North County, Central, and South County facilities. Accepted items include computers, TVs, printers, cell phones, and batteries. No appointment needed during open hours.',
      broward: 'Broward County Environmental Engineering and Facilities Management operates the Household Hazardous Waste Center at 5600 Reese Road in Davie. Open Saturdays 8 AM - 2 PM. Accepts all electronics at no charge. Fort Lauderdale also partners with Best Buy for ongoing drop-off at 2600 N Federal Hwy.',
      miamiDade: 'Miami-Dade County\'s DERM (Department of Environmental Resources Management) holds monthly hazardous waste and e-waste events. Check miamidade.gov/solidwaste for the calendar. The county also maintains permanent drop-off at the South Dade Landfill. All common electronics accepted free of charge.',
    },
    donation: 'Working electronics in good condition can often be donated. PCs for People in South Florida accepts computers less than 8 years old. Goodwill accepts working TVs, computers, and accessories. World Computer Exchange accepts functional equipment for international distribution to developing countries. For smartphones and tablets, many carriers and manufacturers have trade-in programs that give you credit toward new purchases — Apple, Samsung, and Google all run ongoing programs. Best Buy has a trade-in program and takes non-working devices for recycling.',
    diy: 'Best Buy accepts virtually all consumer electronics for recycling in-store — up to 3 items per household per day, free for most items (TVs and monitors: $25 fee, waived with $35+ purchase). Staples accepts electronics and ink cartridges for recycling. The EPA\'s eCycler locator at epa.gov/recycle finds R2-certified recyclers near you. For data security before drop-off: use DBAN (free tool) to wipe hard drives, or physically remove and destroy the hard drive before taking the rest of the computer for recycling.',
    costTable: [
      { method: 'Umuve Professional Pickup', cost: '$89 – $299', time: 'Same day', effort: 'Zero', eco: '96% recycled' },
      { method: 'County HHW Drop-Off Events', cost: 'Free', time: 'Next event date', effort: 'You transport', eco: 'Excellent' },
      { method: 'Best Buy In-Store Recycling', cost: 'Free (TVs $25)', time: 'Same day', effort: 'You transport', eco: 'Good (R2 certified)' },
      { method: 'Retail Trade-In Programs', cost: 'Free + credit', time: 'Varies', effort: 'Low', eco: 'Good' },
    ],
    environmental: 'E-waste is the fastest-growing solid waste stream globally, and South Florida generates millions of pounds annually. A single computer monitor contains 4-8 lbs of lead in its CRT glass. Laptop batteries contain lithium, cobalt, and nickel that can contaminate groundwater. A single cell phone contains gold, silver, palladium, and platinum recoverable at higher concentrations than most mines. At R2-certified facilities, 96% of materials from consumer electronics are recovered — precious metals are refined, glass is processed, plastics are pelletized, and circuit board components are smelted for metal recovery.',
    mistakes: [
      { title: 'Putting electronics in the regular trash', body: 'Florida Statute 403.7192 prohibits televisions and computers from entering regular trash or landfills. First-time violations result in warnings; repeat violations can result in fines.' },
      { title: 'Not wiping personal data before recycling', body: 'Simply deleting files is not sufficient. Hard drives retain data that can be recovered with common tools. Use DBAN for full-wipe or choose a service like Umuve that offers certified destruction.' },
      { title: 'Leaving electronics at the curb', body: 'Curbside electronics collection in South Florida is not standard in most cities. Items left at the curb are often picked through by scrappers who discard the rest. This creates illegal dumping and is not environmentally responsible.' },
      { title: 'Assuming donation centers accept everything', body: 'Most donation centers do not accept CRT monitors or televisions, printers over 3 years old, or any non-working devices. Call ahead before loading up your car.' },
    ],
    faqs: [
      { q: 'Is it illegal to throw away a TV or computer in Florida?', a: 'Yes. Florida Statute 403.7192 bans televisions and computers (desktops, laptops, and monitors) from residential trash and landfills. Violations can result in warnings and fines.' },
      { q: 'Where can I drop off old electronics for free in South Florida?', a: 'All three South Florida counties hold free monthly HHW and e-waste events. Best Buy accepts most electronics in-store for free recycling. Staples accepts computers and accessories. Check pbcswa.com, broward.org/solidwaste, or miamidade.gov/solidwaste for schedules.' },
      { q: 'Does Umuve destroy hard drives?', a: 'Yes. Umuve offers certified hard drive destruction. All storage media is either physically shredded or degaussed at our R2-certified partner facilities. Certificates of destruction are available for business clients.' },
      { q: 'How much does electronics pickup cost?', a: 'Umuve charges $89 for a small pickup (a few items) up to $299 for a large collection. Volume is the main factor. County drop-off events are free if you transport the items yourself.' },
      { q: 'What electronics does Umuve accept?', a: 'We accept all consumer electronics: computers, laptops, monitors, TVs (all types), printers, scanners, copiers, fax machines, phones, tablets, gaming consoles, stereos, cables, and accessories. We do not accept devices containing radioactive materials.' },
      { q: 'Can old electronics be donated instead of recycled?', a: 'If the device is functional and less than 5-7 years old, donation is often the best option. Goodwill, PCs for People, and World Computer Exchange accept qualifying devices. Non-working or outdated electronics should go to certified recycling.' },
    ],
  },

  {
    slug: 'how-to-dispose-of-paint',
    title: 'How to Dispose of Old Paint in South Florida (2026)',
    metaDescription: 'How to dispose of old paint in South Florida legally. Latex vs oil paint rules, free PaintCare drop-off locations, HHW events, and what not to do.',
    h1: 'How to Dispose of Old Paint in South Florida',
    subtitle: 'Legal paint disposal options for Palm Beach, Broward, and Miami-Dade residents — latex, oil, and spray paints.',
    quickAnswer: 'Latex paint can be solidified and placed in regular trash once fully hardened. Oil-based paint is hazardous waste and must go to a PaintCare drop-off location or county HHW event — it cannot be trashed or poured down drains. All three South Florida counties offer free paint disposal at regular events. PaintCare drop-off sites include Home Depot, Lowe\'s, and Ace Hardware locations throughout the region.',
    serviceSlug: 'garage-cleanout',
    serviceName: 'Garage Cleanout',
    relatedGuides: [
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
      { slug: 'declutter-for-spring-cleaning', title: 'Declutter for Spring Cleaning' },
      { slug: 'renovation-debris-disposal-guide', title: 'Renovation Debris Disposal Guide' },
      { slug: 'how-to-dispose-of-appliances', title: 'How to Dispose of Appliances' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
    toc: [
      { id: 'professional', label: 'Option 1: Professional Junk Removal' },
      { id: 'curbside', label: 'Option 2: PaintCare & County Drop-Off' },
      { id: 'donation', label: 'Option 3: Donation' },
      { id: 'diy', label: 'Option 4: DIY Latex Solidification' },
      { id: 'cost-comparison', label: 'Cost Comparison' },
      { id: 'environmental', label: 'Environmental Impact' },
      { id: 'mistakes', label: 'Common Mistakes' },
      { id: 'faq', label: 'FAQ' },
    ],
    professional: {
      price: '$149 – $285 (garage cleanout including paint)',
      description: 'Umuve handles garage cleanouts that include old paint, chemicals, and household hazardous materials. We sort paint cans on-site, identify latex vs. oil-based products, and route each appropriately. Latex paint cans we can solidify and handle as regular disposal; oil-based and aerosol paints are transported to licensed HHW facilities. This is the most efficient option if you have a full garage to clear — old paint is just part of the job.',
      includes: ['Garage sorting and cleanout', 'Latex paint solidification and disposal', 'Oil-based paint routed to HHW facility', 'All hauling included', 'Same-day service'],
    },
    curbside: {
      palmBeach: 'Palm Beach County SWA hosts free HHW events monthly where paint drop-off is accepted. Additionally, PaintCare operates 15+ drop-off sites in Palm Beach County at Home Depot, Lowe\'s, and Ace Hardware locations. Visit paintcare.org/drop-off-site-locator to find the nearest site — it is free, open during store hours, and accepts up to 5 gallons per visit.',
      broward: 'Broward County\'s HHW Center in Davie (5600 Reese Road) accepts paint every Saturday 8 AM - 2 PM. PaintCare has 20+ Broward County locations. The Broward County Construction & Demolition site in Southwest Ranches also accepts commercial paint disposal for contractors.',
      miamiDade: 'Miami-Dade DERM events accept all paint types. PaintCare has 25+ Miami-Dade locations including Home Depots across the county. For large volumes (contractor disposal), the South Dade Landfill HHW area is open weekdays and Saturdays.',
    },
    donation: 'Usable leftover paint can be donated. Habitat for Humanity ReStores accept unopened or lightly-used paint cans in good condition for resale to fund building projects. PaintCare partner locations often have a take-back program where donated paint is reprocessed into new recycled paint. Some community organizations and theater groups also accept mixed paint for set painting and community projects — check local Facebook groups.',
    diy: 'Latex (water-based) paint can be made safe for regular trash by drying it out completely. Options: leave the lid off in a well-ventilated area and let it air-dry (works for small amounts), add cat litter or commercial paint hardener (Homax Paint Hardener at Home Depot, $4-$6 per box), or pour thin layers onto cardboard in a well-ventilated garage. Once fully hardened — solid with no wet center — latex paint cans can go in the regular trash in Florida with the lid off to show hardness. Oil-based paint, stains, varnishes, and aerosol cans CANNOT be handled this way. They must go to HHW.',
    costTable: [
      { method: 'PaintCare Drop-Off (any volume up to 5 gal)', cost: 'Free', time: 'During store hours', effort: 'You transport', eco: 'Excellent' },
      { method: 'County HHW Event', cost: 'Free', time: 'Next event date', effort: 'You transport', eco: 'Excellent' },
      { method: 'Latex Hardening (DIY) + Trash', cost: '$4–$10 hardener', time: '24–72 hrs drying', effort: 'Low', eco: 'Landfill' },
      { method: 'Umuve Garage Cleanout (paint included)', cost: '$149 – $285', time: 'Same day', effort: 'Zero', eco: 'Routed appropriately' },
    ],
    environmental: 'Paint is the most common household hazardous waste item in South Florida. Oil-based paints contain volatile organic compounds (VOCs), heavy metals (lead, chromium), and solvents that contaminate groundwater when landfilled. A single gallon of oil-based paint can contaminate up to 250,000 gallons of drinking water if improperly disposed. PaintCare, funded by a $0.35 - $1.60 fee on each paint can sold in Florida, has diverted over 10 million gallons of paint from Florida landfills since the program launched. Donated and recycled paint is reprocessed into recycled-content paint sold at a fraction of normal retail price.',
    mistakes: [
      { title: 'Pouring paint down the drain or on the ground', body: 'Pouring paint — latex or oil-based — down drains or on the ground is illegal under Florida environmental law. Even "water-based" latex paint contains pigments and binding agents that harm aquatic life and contaminate stormwater systems.' },
      { title: 'Putting oil-based paint in the regular trash', body: 'Oil-based paint, stains, varnishes, lacquers, and aerosol paint cans are classified as household hazardous waste in Florida. They cannot be placed in regular trash or recycling bins — even empty aerosol cans should be recycled as metal, not trashed.' },
      { title: 'Assuming latex and oil-based paint are handled the same way', body: 'They are not. Latex (water-based) paint can be hardened and trashed legally in Florida. Oil-based paint must go to HHW. Check the label: "Clean up with water" means latex; "Clean up with mineral spirits or turpentine" means oil-based.' },
      { title: 'Leaving old paint in a sealed garage for years', body: 'Paint stored improperly in South Florida\'s heat and humidity can become hazardous even faster. Cans swell, burst, or corrode. Dispose of paint you have not used in 2+ years at the next HHW event.' },
    ],
    faqs: [
      { q: 'Can I put dried latex paint in the trash in Florida?', a: 'Yes. Once latex paint is completely solidified — no wet areas — it can be placed in regular trash in Florida. Leave the lid off when you put it at the curb so collectors can verify it is dry. Oil-based paint must go to HHW regardless of dry state.' },
      { q: 'Where are PaintCare drop-off locations near me?', a: 'Visit paintcare.org/drop-off-site-locator and enter your zip code. South Florida has 60+ locations at Home Depot, Lowe\'s, and Ace Hardware stores. It is free, no appointment needed, and accepts up to 5 gallons per visit.' },
      { q: 'Does Umuve take old paint cans?', a: 'Umuve handles paint as part of full garage cleanouts. We sort latex from oil-based on site and route each appropriately. We do not accept paint-only pickups but include it in any garage or home cleanout job.' },
      { q: 'How do I know if my paint is latex or oil-based?', a: 'Check the cleanup instructions on the label. "Clean up with soap and water" means latex. "Clean up with mineral spirits" or "turpentine" means oil-based. Most paint sold after 2000 is latex. Primers, stains, varnishes, and older paints are often oil-based.' },
      { q: 'What do I do with half-empty paint cans I want to keep?', a: 'Store latex paint in a temperature-controlled space (not an outdoor shed in South Florida heat). Pour a thin layer of water on top before sealing to prevent skinning. Properly sealed latex paint lasts 2-5 years after opening.' },
      { q: 'Can I donate leftover paint in South Florida?', a: 'Yes. Habitat for Humanity ReStores accept interior latex paint in sealed cans. Community organizations and theater groups sometimes accept mixed paint. PaintCare partner stores also accept paint for reprocessing into recycled-content products.' },
    ],
  },

  {
    slug: 'how-to-dispose-of-a-couch',
    title: 'How to Dispose of a Couch in South Florida (2026)',
    metaDescription: 'How to dispose of a couch or sofa in South Florida. Pickup options, donation centers, curbside rules, and professional removal starting at $89.',
    h1: 'How to Dispose of a Couch in South Florida',
    subtitle: 'Get rid of your old sofa, sectional, or loveseat the right way in Palm Beach, Broward, and Miami-Dade.',
    quickAnswer: 'Couch removal in South Florida starts at $89 for professional pickup with Umuve — same-day service, all labor included, 90% donated or recycled. County curbside pickup is free but requires advance scheduling and typically a 5-14 day wait. Couches in good condition can be donated to Habitat for Humanity, Salvation Army, or Goodwill.',
    serviceSlug: 'couch-removal',
    serviceName: 'Couch Removal',
    relatedGuides: [
      { slug: 'how-to-take-apart-a-couch', title: 'How to Take Apart a Couch' },
      { slug: 'how-to-dispose-of-a-mattress', title: 'How to Dispose of a Mattress' },
      { slug: 'what-to-do-with-old-furniture', title: 'What to Do with Old Furniture' },
      { slug: 'declutter-before-moving', title: 'Declutter Before Moving' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'coral-springs-fl', name: 'Coral Springs' },
    ],
    toc: [
      { id: 'professional', label: 'Option 1: Professional Removal' },
      { id: 'curbside', label: 'Option 2: Municipal Curbside' },
      { id: 'donation', label: 'Option 3: Donation' },
      { id: 'diy', label: 'Option 4: DIY Disposal' },
      { id: 'cost-comparison', label: 'Cost Comparison' },
      { id: 'environmental', label: 'Environmental Impact' },
      { id: 'mistakes', label: 'Common Mistakes' },
      { id: 'faq', label: 'FAQ' },
    ],
    professional: {
      price: '$89 – $299',
      description: 'Umuve removes couches and sofas of any size — standard two-seater sofas, oversized sectionals, sleeper sofas, recliners, and outdoor patio sectionals. Two-person crews navigate your furniture through doors, hallways, and staircases. If your sectional does not fit through the door, we disassemble it on-site. Couches in good condition are donated to Habitat for Humanity, Salvation Army, or local shelters. Damaged pieces are broken down — wood frames recycled, foam repurposed, fabric processed.',
      includes: ['Any couch or sofa type accepted', 'Disassembly if needed to fit through doors', 'Same-day service', 'Donation for usable couches', '90% donated or recycled'],
    },
    curbside: {
      palmBeach: 'Palm Beach County SWA bulk pickup accepts couches with advance scheduling. Call (561) 697-2700 or schedule at pbcswa.com. Place at curb by 6 AM on pickup day. Sofas must not exceed 6 feet in any dimension to be accepted. Sectionals must be separated into individual pieces.',
      broward: 'Broward County curbside bulk is managed city-by-city. Hollywood allows 4 items per scheduled pickup. Pompano Beach residents call (954) 786-4000. Fort Lauderdale: (954) 828-5150. Most cities have a 5-10 business day lead time. Sectionals count as multiple items.',
      miamiDade: 'Miami-Dade unincorporated areas allow up to 2 bulk items curbside per week without scheduling. City of Miami residents schedule at 311. Couches in Hialeah must be called in at (305) 883-5800. Items must not block sidewalk or street.',
    },
    donation: 'Habitat for Humanity ReStores in Boca Raton, Deerfield Beach, and Fort Lauderdale accept couches in excellent condition — no stains, tears, pet damage, or odor. The Salvation Army Family Stores in Miami-Dade and Broward offer free furniture pickup for qualifying donations (call your local store to schedule). Goodwill in Palm Beach County accepts couches in very good condition. Local Facebook Marketplace and the Buy Nothing groups are excellent for free rehoming — post your couch with clear photos and it often disappears within hours, especially for quality pieces.',
    diy: 'If donation is not an option and you want to avoid pickup fees, renting a truck is the primary DIY route. A 10-foot U-Haul runs $19.95 + mileage. Broward County Solid Waste transfer stations accept furniture for $50-$80 per load. Palm Beach County SWA South County transfer station charges by weight. You will need a helper — couches are bulky and awkward even when light. Alternatively, breaking down the couch: remove cushions (bag for trash), cut fabric with a utility knife to remove upholstery (trash), separate foam (compress into bags), and haul the wood/metal frame to a scrap yard or schedule a metal pickup.',
    costTable: [
      { method: 'Umuve Professional Pickup', cost: '$89 – $299', time: 'Same day', effort: 'Zero', eco: '90% donated or recycled' },
      { method: 'County Curbside', cost: 'Free', time: '5–14 days', effort: 'Move to curb', eco: 'Partial' },
      { method: 'Donation (Salvation Army pickup)', cost: 'Free', time: '1–7 days', effort: 'Schedule pickup', eco: 'Best' },
      { method: 'DIY Haul (truck + transfer station)', cost: '$70 – $120', time: 'Half-day', effort: 'High', eco: 'Partial' },
    ],
    environmental: 'A standard sofa contains 30-50 lbs of foam, 20-40 lbs of hardwood or engineered wood framing, 15-25 lbs of steel springs and hardware, and 10-20 lbs of fabric and padding. When landfilled, the foam (polyurethane) takes 500+ years to break down and off-gasses toxic compounds as it degrades. Foam from recycled sofas is processed into carpet underlay, saving virgin polyurethane production. Wood frames are chipped into mulch or recycled as engineered lumber components. Umuve donates 90% of collected couches or recovers materials.',
    mistakes: [
      { title: 'Putting a couch curbside without scheduling', body: 'Unscheduled bulk items are a code violation in virtually every South Florida city. HOA fines run $50-$200/day. A neighbor\'s complaint is often all it takes for a citation. Always schedule with your city first.' },
      { title: 'Assuming a couch too large for the door cannot be removed', body: 'Many people give up and leave a sectional or oversized sofa because it seems impossible to move. Experienced movers and junk removal crews deal with this daily — disassembly, vertical tilting, and door-frame removal are all standard techniques.' },
      { title: 'Listing a donation on Facebook and not following through', body: 'Posting a couch as "free" and then canceling on people who commit to picking it up wastes their time and forces you to repeat the process. If you list it, keep the time slot.' },
      { title: 'Treating all sofas as trash when many have value', body: 'A sectional sofa in good condition can sell for $150-$600 on Facebook Marketplace or Craigslist in South Florida. Before booking removal, take 5 minutes to photograph it and post. If it sells, you get paid instead of paying.' },
    ],
    faqs: [
      { q: 'How much does couch removal cost in South Florida?', a: 'Professional removal by Umuve starts at $89 for a standard sofa or loveseat. Sectional sofas average $139-$189. Sleeper sofas or unusually heavy pieces may be $199-$299. County curbside is free with advance scheduling.' },
      { q: 'Will Habitat for Humanity pick up a couch?', a: 'Habitat for Humanity ReStore locations in South Florida vary on pickup availability. Some locations offer free pickup of large donations including couches; others require you to bring the item. Call your local ReStore directly. The couch must be in excellent condition — no stains, no odor, no pet damage.' },
      { q: 'Can Umuve remove a couch from upstairs?', a: 'Yes. Umuve crews carry furniture from any floor of any building. Two-person teams handle second-floor bedroom couches, high-rise condo removals (with elevator), and multi-story homes routinely. Stairs are included in standard pricing.' },
      { q: 'What if my sectional does not fit through the door?', a: 'Not a problem. We disassemble sectionals on-site if needed — removing legs, separating chaise sections, and using door removal when necessary. Disassembly is included in our standard service.' },
      { q: 'Can I sell my old couch instead of paying for removal?', a: 'In many cases, yes. Couches less than 5 years old in good condition often sell for $100-$400 on Facebook Marketplace in South Florida. Post clear photos in natural light and price competitively. If it does not sell within a week, book a pickup.' },
      { q: 'Is there a fee for same-day couch pickup?', a: 'No. Umuve\'s same-day service carries no surcharge. You book online or by phone, and we dispatch based on availability. Early morning and mid-week slots have the highest same-day availability.' },
    ],
  },

  {
    slug: 'how-to-dispose-of-appliances',
    title: 'How to Dispose of Appliances in South Florida (2026)',
    metaDescription: 'How to dispose of old appliances in South Florida. Legal disposal for refrigerators, washers, dryers, dishwashers, and stoves. Costs, county rules, and recycling info.',
    h1: 'How to Dispose of Appliances in South Florida',
    subtitle: 'Legal and eco-friendly appliance disposal across Palm Beach, Broward, and Miami-Dade — refrigerators, washers, dryers, and more.',
    quickAnswer: 'Most major appliances in South Florida require special handling before disposal. Refrigerators and AC units need EPA-compliant refrigerant recovery. All appliances should go to certified metal recyclers rather than landfills. Umuve handles same-day appliance removal starting at $89. Utility rebates of $25-$75 are available for certain units through FPL.',
    serviceSlug: 'appliance-removal',
    serviceName: 'Appliance Removal',
    relatedGuides: [
      { slug: 'how-to-dispose-of-a-refrigerator', title: 'How to Dispose of a Refrigerator' },
      { slug: 'how-to-dispose-of-a-washer-dryer', title: 'How to Dispose of a Washer and Dryer' },
      { slug: 'how-to-dispose-of-a-stove-oven', title: 'How to Dispose of a Stove and Oven' },
      { slug: 'how-to-dispose-of-a-dishwasher', title: 'How to Dispose of a Dishwasher' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'pembroke-pines-fl', name: 'Pembroke Pines' },
    ],
    toc: [
      { id: 'professional', label: 'Option 1: Professional Removal' },
      { id: 'curbside', label: 'Option 2: Municipal Curbside' },
      { id: 'donation', label: 'Option 3: Utility Rebates & Donation' },
      { id: 'diy', label: 'Option 4: DIY Haul & Scrap' },
      { id: 'cost-comparison', label: 'Cost Comparison' },
      { id: 'environmental', label: 'Environmental Impact' },
      { id: 'mistakes', label: 'Common Mistakes' },
      { id: 'faq', label: 'FAQ' },
    ],
    professional: {
      price: '$89 – $299',
      description: 'Umuve removes all major household appliances — refrigerators, freezers, washing machines, dryers, dishwashers, stoves, ovens, water heaters, dehumidifiers, and air conditioners. We handle EPA-required refrigerant recovery for units that contain Freon or HFCs. All appliances go to certified metal recycling facilities where 95% of materials are recovered. Same-day service available throughout South Florida.',
      includes: ['All major appliances accepted', 'EPA-compliant refrigerant handling for qualified units', 'Disconnection from standard connections', 'Full labor and hauling', '95% recycled at certified facilities'],
    },
    curbside: {
      palmBeach: 'Palm Beach County SWA accepts large appliances curbside with advance scheduling. Refrigerators and AC units require a tag certifying Freon removal by a certified technician, or they will be rejected. Non-refrigerant appliances (washers, dryers, stoves) are accepted without special prep. Call (561) 697-2700 to schedule.',
      broward: 'Broward County municipal pickup handles appliances city by city. Washing machines and dryers are typically accepted without special prep. Refrigerators require the Freon evacuation certification. Most cities allow 2-4 large appliances per bulk pickup. Call your city\'s solid waste department.',
      miamiDade: 'Miami-Dade Solid Waste accepts appliances through scheduled bulk pickup. Refrigerators and freezers require doors to be removed per federal child safety law before curbside placement. The county also operates appliance drop-off at transfer stations on weekdays.',
    },
    donation: 'Working appliances less than 10 years old in good condition can often be donated. Habitat for Humanity ReStores accept working washers, dryers, refrigerators, and stoves. The Salvation Army picks up working appliances with advance scheduling in many South Florida areas. FPL\'s appliance recycling program offers $25-$75 rebates for qualifying units — visit fpl.com/save/residential/appliance-recycling.html. Contact FPL at (800) 226-3545 for eligible models and scheduling.',
    diy: 'Scrap metal yards pay $5-$25 per appliance depending on metal content and market prices. A washer or dryer is mostly steel and fetches the best prices. Refrigerators and AC units must have refrigerant removed first — HVAC techs charge $50-$150 for this service. Without a truck, you are paying $20-$40/hour for a rental. Transfer station fees in South Florida run $30-$80 per load. For single appliances, DIY rarely saves money over professional removal.',
    costTable: [
      { method: 'Umuve Professional Pickup', cost: '$89 – $299', time: 'Same day', effort: 'Zero', eco: '95% recycled' },
      { method: 'County Curbside', cost: 'Free', time: '5–14 days', effort: 'Move to curb', eco: 'Partial' },
      { method: 'FPL Appliance Recycling (refrigerators)', cost: 'Free + $25–$75 rebate', time: '1–2 weeks', effort: 'Minimal', eco: 'Good' },
      { method: 'Scrap Metal Yard (with truck)', cost: 'Free–$20 income', time: 'Same day', effort: 'High', eco: 'Good' },
    ],
    environmental: 'Major appliances are among the most recyclable items in the waste stream. A standard washing machine contains 100-120 lbs of steel, 5-10 lbs of copper wiring and motors, and 10-20 lbs of plastics. At certified recycling facilities, these materials are shredded and magnetically separated into steel, aluminum, and copper streams — all of which are sold directly to manufacturers for new production. Refrigerant recovery from climate-controlled appliances prevents potent greenhouse gases from entering the atmosphere. Every appliance properly recycled avoids the mining and smelting required to produce equivalent virgin metals.',
    mistakes: [
      { title: 'Placing a refrigerator curbside with Freon still inside', body: 'Refrigerant-containing appliances are rejected by municipal collectors unless certified Freon removal is documented. This results in the item sitting at the curb, potential code violations, and you still having to deal with it.' },
      { title: 'Paying a new appliance store to remove the old one without asking about alternatives', body: 'Many big-box retailers charge $25-$50 for old appliance removal during delivery. This is often cheaper than separate junk removal, but the retailer may send it to landfill. Umuve guarantees certified recycling.' },
      { title: 'Assuming a neighbor or Craigslist buyer will handle disposal', body: 'Listing a broken appliance as "free for parts" often results in it being picked up but then abandoned somewhere else. If the item is not functional, go directly to a recycling solution.' },
      { title: 'Trying to move a heavy appliance without proper equipment', body: 'Washers weigh 150-200 lbs; refrigerators 180-350 lbs. Without an appliance dolly and proper technique, floor damage and back injuries are the most common outcomes.' },
    ],
    faqs: [
      { q: 'Does my city pick up old appliances for free in South Florida?', a: 'Most South Florida cities include large appliance pickup in their bulk waste program with advance scheduling. Refrigerators and AC units require documented refrigerant removal first. Call your city\'s solid waste department or check their website.' },
      { q: 'Can Home Depot or Lowe\'s take my old appliance when delivering a new one?', a: 'Yes, most retailers offer haul-away for $25-$50 when delivering new appliances. Ask at purchase. They typically take the same type of item they delivered. This is convenient but confirm the appliance goes to a recycler, not a landfill.' },
      { q: 'What appliances require special disposal in Florida?', a: 'Refrigerators, freezers, air conditioners, and dehumidifiers contain refrigerants that require EPA-certified recovery. Electronics (built into smart appliances) should go to certified e-waste recyclers. All other appliances can go to standard metal recyclers.' },
      { q: 'Does Umuve disconnect appliances before removal?', a: 'We disconnect standard connections — water supply lines, dryer vents, 120V power cords. Gas disconnection and hardwired 240V appliances should be handled by a licensed technician before our arrival. We can coordinate in most cases.' },
      { q: 'What is the best appliance recycling program in South Florida?', a: 'FPL\'s appliance recycling program offers the best value — free pickup and $25-$75 cash back for qualifying refrigerators and freezers. For other appliances, Umuve\'s certified recycling is the most convenient at $89+ for same-day service.' },
      { q: 'Can I get paid for an old appliance?', a: 'FPL pays $25-$75 rebates for qualifying refrigerators. Scrap metal yards pay $5-$25 per appliance if you transport it. Working appliances in good condition can sell for $50-$300 on Facebook Marketplace or Craigslist. In most cases, the FPL rebate is the easiest cash option.' },
    ],
  },

  // Guide 7: TV
  {
    slug: 'how-to-dispose-of-a-tv',
    title: 'How to Dispose of a TV in South Florida (2026)',
    metaDescription: 'How to dispose of a TV legally in South Florida. Free drop-off, county e-waste events, Best Buy recycling, and professional TV pickup starting at $89.',
    h1: 'How to Dispose of a TV in South Florida',
    subtitle: 'Legal TV disposal options for all types — flat screens, CRTs, and smart TVs — across South Florida.',
    quickAnswer: 'Throwing a TV in the regular trash is illegal in Florida. Options include free drop-off at Best Buy (most TV types, free with any in-store purchase), county e-waste events (free, monthly), or professional pickup by Umuve starting at $89 including wall-mount removal. CRT televisions require R2-certified recycling due to lead content.',
    serviceSlug: 'tv-recycling',
    serviceName: 'TV Recycling',
    relatedGuides: [
      { slug: 'how-to-dispose-of-electronics', title: 'How to Dispose of Electronics' },
      { slug: 'how-to-dispose-of-appliances', title: 'How to Dispose of Appliances' },
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
      { slug: 'declutter-before-moving', title: 'Declutter Before Moving' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
    toc: [
      { id: 'professional', label: 'Option 1: Professional Removal' },
      { id: 'curbside', label: 'Option 2: Free Recycling Drop-Off' },
      { id: 'donation', label: 'Option 3: Donation' },
      { id: 'diy', label: 'Option 4: Retail Recycling' },
      { id: 'cost-comparison', label: 'Cost Comparison' },
      { id: 'environmental', label: 'Environmental Impact' },
      { id: 'mistakes', label: 'Common Mistakes' },
      { id: 'faq', label: 'FAQ' },
    ],
    professional: {
      price: '$89 – $199',
      description: 'Umuve picks up TVs of any type and size — 80-inch flat screens, wall-mounted displays, CRT televisions, projection TVs, and computer monitors. We remove wall mounts without wall damage when requested. All TVs go to R2-certified e-waste recyclers where glass, metals, and plastics are recovered. Florida law compliance guaranteed — no TV goes to landfill.',
      includes: ['All TV types and sizes', 'Wall-mount removal included', 'R2-certified recycling facility', 'Same-day service', 'Florida law compliant disposal'],
    },
    curbside: {
      palmBeach: 'Palm Beach County SWA HHW events accept TVs free monthly. Additionally, Best Buy locations throughout Palm Beach County accept flat screen TVs for free recycling. CRT TVs are accepted at HHW events but not typically at retail take-back programs. Visit pbcswa.com for event dates.',
      broward: 'Broward County\'s HHW Center in Davie accepts TVs every Saturday. Best Buy in Plantation (800 S Pine Island Rd) and other county locations accept flat screens. Fort Lauderdale residents can also use the Pratt & Whitney Road recycling center for electronics.',
      miamiDade: 'Miami-Dade DERM monthly events accept all TV types. Several Miami Best Buy locations accept flat screens for free. Check miamidade.gov/solidwaste for e-waste event schedules. Coral Gables and Miami Beach have their own electronics collection programs — check city websites.',
    },
    donation: 'Working TVs less than 5 years old in good condition can be donated to Goodwill, Salvation Army, or local thrift stores. Goodwill accepts flat screen TVs in working condition at most South Florida locations. Community centers, schools, and churches sometimes accept donated TVs for classrooms or common areas. Facebook Marketplace and Nextdoor are effective for rehoming working televisions quickly. CRT televisions are almost universally unaccepted for donation — recycle these through HHW or certified e-waste programs.',
    diy: 'Best Buy is the most accessible TV recycling option in South Florida. They accept flat screen TVs up to 32 inches for free; larger TVs carry a $25 fee (waived with a $35+ in-store purchase). CRT TVs have a $25-$35 fee regardless. Staples accepts TVs at some locations — call ahead. The EPA eCycler locator at epa.gov/recycle lists certified recyclers near you. Never place a TV at the curb as unauthorized e-waste — it is illegal and results in citations.',
    costTable: [
      { method: 'Umuve Professional Pickup', cost: '$89 – $199', time: 'Same day', effort: 'Zero', eco: '97% recycled' },
      { method: 'Best Buy In-Store (flat screens ≤32")', cost: 'Free', time: 'Same day', effort: 'You transport', eco: 'Good' },
      { method: 'Best Buy In-Store (>32" or CRT)', cost: '$25 fee (waived with purchase)', time: 'Same day', effort: 'You transport', eco: 'Good' },
      { method: 'County HHW Event', cost: 'Free', time: 'Next event date', effort: 'You transport', eco: 'Excellent' },
    ],
    environmental: 'A CRT television contains 4-8 lbs of lead in its glass — a single unit contains enough lead to contaminate an entire landfill cell if not properly managed. Modern flat screen TVs contain mercury in fluorescent backlights (older models), arsenic in LED layers, and rare earth elements throughout. At R2-certified recyclers, 97% of TV materials are recovered. Glass panels are processed for lead recovery; precious metals are extracted from circuit boards; plastic housings are pelletized for remanufacture. By law, all TVs sold in Florida are subject to a manufacturer take-back requirement, funded by the state\'s e-waste program.',
    mistakes: [
      { title: 'Leaving a TV at the curb', body: 'This is illegal in Florida. Unscheduled electronics at the curb result in code violations. Even if someone picks it up for parts, the remainder often gets abandoned nearby.' },
      { title: 'Assuming all donation centers accept TVs', body: 'Most charity thrift stores do not accept CRT TVs under any circumstances. Even for flat screens, many stores have stopped accepting them due to storage and sales challenges. Always call before transporting.' },
      { title: 'Not removing the wall mount bracket before disposal', body: 'If you want the bracket removed, specify that when booking. If you are hauling the TV yourself, the bracket stays on the wall unless you remove it. Umuve can remove brackets upon request.' },
      { title: 'Paying full Best Buy recycling fee when a purchase waives it', body: 'If you are already buying something at Best Buy — even a $35 accessory — your TV recycling fee is waived. This is worth knowing if you are heading to the store anyway.' },
    ],
    faqs: [
      { q: 'Is it illegal to throw away a TV in Florida?', a: 'Yes. Florida Statute 403.7192 prohibits televisions from entering regular household trash or landfills. First-time violations result in warnings; subsequent violations carry fines. Use certified e-waste recycling, county drop-off events, or Best Buy.' },
      { q: 'Does Best Buy recycle TVs for free in South Florida?', a: 'Best Buy accepts flat screen TVs up to 32 inches for free. TVs over 32 inches or CRT televisions have a $25 fee, which is waived with any $35+ in-store purchase. Most South Florida Best Buy locations participate.' },
      { q: 'Can I donate my old flat screen TV?', a: 'If it is working and less than 5 years old, yes. Goodwill accepts flat screens at most South Florida locations. Salvation Army and community organizations also accept working TVs. CRTs are not accepted for donation anywhere in South Florida.' },
      { q: 'How much does TV pickup cost with Umuve?', a: 'TV pickup starts at $89 for a single standard flat screen. Multiple TVs or large projector TVs may run $119-$199. Wall-mount removal is included. Pricing covers all labor, transport, and certified recycling.' },
      { q: 'Does Umuve remove wall-mounted TVs?', a: 'Yes. Our crews unmount wall-mounted TVs carefully to avoid wall damage. The bracket hardware and mount are included in the removal. We patch any anchor holes if requested (additional fee).' },
      { q: 'What happens to recycled TVs?', a: 'At R2-certified facilities, TVs are disassembled. Glass panels are processed for lead or rare earth recovery. Circuit boards go to precious metal smelters. Plastic housings are shredded and pelletized. Backlights with mercury are handled under strict environmental controls.' },
    ],
  },

  // Guide 8: Tires
  {
    slug: 'how-to-dispose-of-tires',
    title: 'How to Dispose of Old Tires in South Florida (2026)',
    metaDescription: 'How to legally dispose of tires in South Florida. Free county drop-off, tire retailer take-back, DIY recycling options, and costs. Tire dumping fines explained.',
    h1: 'How to Dispose of Old Tires in South Florida',
    subtitle: 'Legal, free, and paid tire disposal options across Palm Beach, Broward, and Miami-Dade counties.',
    quickAnswer: 'Tires cannot go in regular trash or landfills in Florida. Free disposal options include county HHW events (usually limited to 4-8 tires), tire retailer take-back (typically $1-$4 per tire when purchasing new ones), and some auto parts stores. Umuve handles tire disposal as part of garage cleanouts. Illegal tire dumping carries fines of $500-$5,000 per incident in South Florida.',
    serviceSlug: 'garage-cleanout',
    serviceName: 'Garage Cleanout',
    relatedGuides: [
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
      { slug: 'how-to-dispose-of-appliances', title: 'How to Dispose of Appliances' },
      { slug: 'declutter-for-spring-cleaning', title: 'Declutter for Spring Cleaning' },
      { slug: 'renovation-debris-disposal-guide', title: 'Renovation Debris Disposal Guide' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'homestead-fl', name: 'Homestead' },
    ],
    toc: [
      { id: 'professional', label: 'Option 1: Tire Retailer Take-Back' },
      { id: 'curbside', label: 'Option 2: County Drop-Off Events' },
      { id: 'donation', label: 'Option 3: Tire Recycling Programs' },
      { id: 'diy', label: 'Option 4: Creative Reuse & Drop-Off' },
      { id: 'cost-comparison', label: 'Cost Comparison' },
      { id: 'environmental', label: 'Environmental Impact' },
      { id: 'mistakes', label: 'Common Mistakes' },
      { id: 'faq', label: 'FAQ' },
    ],
    professional: {
      price: '$149 – $285 (as part of garage cleanout)',
      description: 'Umuve accepts tires as part of full garage cleanouts and property cleanups. We transport tires to licensed recycling facilities where they are shredded into crumb rubber for playground surfaces, track surfacing, and rubberized asphalt. Individual tire-only pickups are not our primary service, but if you have a garage full of old tires along with other junk, we handle it all in one trip.',
      includes: ['Tires included in garage cleanout pricing', 'Transport to licensed tire recycler', 'Crumb rubber or retreading program', 'All hauling included'],
    },
    curbside: {
      palmBeach: 'Palm Beach County SWA hosts free tire disposal events throughout the year. Residents can drop off up to 8 passenger tires per event (no commercial truck tires). Check pbcswa.com for event dates. Some events require registration — sign up early as slots fill quickly, especially in spring cleaning season.',
      broward: 'Broward County holds periodic free tire disposal events at various locations. Check broward.org/solidwaste for the schedule. Tire events typically accept 4-8 tires per household. Some Broward cities (Hollywood, Coral Springs) have partnerships with local tire shops for ongoing drop-off.',
      miamiDade: 'Miami-Dade County DERM holds tire collection events several times per year. The county also operates year-round tire drop-off at the South Dade Landfill HHW area for a nominal fee ($1-$2 per tire). Commercial tire quantities require a special permit.',
    },
    donation: 'Salvageable tires in good condition (50%+ tread, no cracks, sidewall damage, or bulges) can be sold or donated. Tire shops sometimes accept usable tires for resale. Some retreading operations in South Florida accept quality passenger tires. Community garden projects use whole tires as planters. Local farming operations occasionally use tires as garden borders. Post on Facebook Marketplace — working tires sell quickly for $10-$40 each.',
    diy: 'For small quantities (1-4 tires), the easiest DIY option is bringing them to a local tire shop when you get new tires installed — most shops charge $1-$4 per tire for disposal, and it is the most convenient option available. Auto Zone and O\'Reilly Auto Parts accept tires for recycling at most South Florida locations (fee varies by location). Certified tire recyclers will also accept drop-offs directly — call ahead for current pricing and hours. For larger quantities from a property cleanout, contact a tire recycler directly for scheduled pickup.',
    costTable: [
      { method: 'Tire Retailer Drop-Off (when buying tires)', cost: '$1–$4 per tire', time: 'Same day', effort: 'Minimal', eco: 'Good' },
      { method: 'County Tire Event', cost: 'Free', time: 'Event date', effort: 'You transport', eco: 'Good' },
      { method: 'Auto Parts Store Drop-Off', cost: '$2–$5 per tire', time: 'Same day', effort: 'You transport', eco: 'Good' },
      { method: 'Umuve (as part of garage cleanout)', cost: '$149+ (full cleanout)', time: 'Same day', effort: 'Zero', eco: 'Good' },
    ],
    environmental: 'Florida generates approximately 30 million scrap tires per year. Tires present unique environmental risks when illegally dumped — they collect water and become prolific mosquito breeding grounds, a serious concern in South Florida where Zika and Dengue are active threats. When tires burn (common at illegal dump sites), they release benzene, toluene, and polycyclic aromatic hydrocarbons. Properly recycled tires become crumb rubber for playground surfaces, rubberized asphalt (which reduces road noise and improves traction), and new tire retreads. Florida\'s Waste Tire Manifest Program tracks all tire shipments from generator to recycler.',
    mistakes: [
      { title: 'Dumping tires illegally', body: 'Florida\'s illegal tire dumping fines range from $500 to $5,000 per incident for first-time violators. Repeat offenses can result in criminal charges. South Florida counties actively investigate tire dumping — roadside cameras have led to hundreds of prosecutions.' },
      { title: 'Leaving tires in areas that collect rainwater', body: 'Even one tire left outdoors in South Florida\'s rain can breed hundreds of mosquitoes within days. This is a public health issue, especially during summer. Store tires flat or standing under a covered area until disposal day.' },
      { title: 'Assuming any junk removal company accepts tires', body: 'Many junk removal companies do not accept tires due to recycling surcharges. Always confirm before booking. Umuve accepts tires as part of full cleanouts and routes them to licensed facilities.' },
      { title: 'Not checking if your tires have resale value', body: 'Tires with 50%+ tread can sell for $10-$40 each on Facebook Marketplace or Craigslist. Before paying to dispose of 4 tires with good tread, take 10 minutes to photograph and list them.' },
    ],
    faqs: [
      { q: 'Where can I drop off old tires for free in South Florida?', a: 'County HHW and tire events are free for residents (check pbcswa.com, broward.org/solidwaste, or miamidade.gov/solidwaste for dates). Many tire retailers accept tires for $1-$4 per tire regardless of purchase. Auto parts stores like AutoZone accept them at most locations.' },
      { q: 'Is it illegal to throw tires in the trash in Florida?', a: 'Yes. Florida Statute 403.718 prohibits whole or shredded tires from being placed in regular trash or landfills. All tires must go through licensed recyclers, retreaders, or permitted disposal facilities.' },
      { q: 'What are old tires recycled into?', a: 'Crumb rubber from shredded tires is used in playground safety surfaces, running tracks, artificial turf infill, and rubberized asphalt. Some tires are retreaded for reuse as vehicle tires. Tire-derived fuel is used in some cement kilns and paper mills as an alternative to coal.' },
      { q: 'How much does tire disposal cost in South Florida?', a: 'Free at county events (limited to 4-8 tires). Tire retailers charge $1-$4 per tire. Auto parts stores charge $2-$5. Licensed tire recyclers charge $3-$10 per tire for drop-off. Large quantities (commercial or fleet) are priced by the pound.' },
      { q: 'Can tires be recycled into something useful?', a: 'Yes. Shredded tire crumb rubber makes excellent playground surfaces that reduce fall injuries. Rubberized asphalt extends road life and reduces traffic noise. Retreaded tires are indistinguishable from new in many applications. Tire-derived fuel burns hotter and cleaner than coal.' },
      { q: 'Does Umuve pick up tires?', a: 'Umuve includes tires in full garage cleanouts and property cleanups at no extra charge. We do not offer tire-only pickups as a standalone service. If you have a full garage to clear and tires are part of it, we handle everything.' },
    ],
  },

  // Guide 9: Hot Tub
  {
    slug: 'how-to-dispose-of-a-hot-tub',
    title: 'How to Dispose of a Hot Tub in South Florida (2026)',
    metaDescription: 'How to dispose of or remove a hot tub in South Florida. Costs, demolition process, utility disconnection, and professional removal starting at $299.',
    h1: 'How to Dispose of a Hot Tub in South Florida',
    subtitle: 'Everything you need to know about hot tub removal, demolition, and disposal in Palm Beach, Broward, and Miami-Dade.',
    quickAnswer: 'Hot tub removal in South Florida typically costs $299-$799 for professional service. The process requires draining, electrical disconnection (by a licensed electrician or our coordinated service), cutting the shell into sections for removal, and hauling debris. DIY removal is possible but requires a reciprocating saw, two or more helpers, and a truck or dumpster. Acrylic shells, wood, and metal components are partially recyclable.',
    serviceSlug: 'hot-tub-removal',
    serviceName: 'Hot Tub Removal',
    relatedGuides: [
      { slug: 'how-to-dispose-of-concrete', title: 'How to Dispose of Concrete' },
      { slug: 'renovation-debris-disposal-guide', title: 'Renovation Debris Disposal Guide' },
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
      { slug: 'junk-removal-cost-south-florida', title: 'Junk Removal Cost Guide' },
    ],
    cityLinks: [
      { city: 'boca-raton-fl', name: 'Boca Raton' },
      { city: 'jupiter-fl', name: 'Jupiter' },
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'weston-fl', name: 'Weston' },
    ],
    toc: [
      { id: 'professional', label: 'Option 1: Professional Removal' },
      { id: 'curbside', label: 'Option 2: Dumpster + DIY Demo' },
      { id: 'donation', label: 'Option 3: Sell or Repurpose' },
      { id: 'diy', label: 'Option 4: Full DIY Breakdown' },
      { id: 'cost-comparison', label: 'Cost Comparison' },
      { id: 'environmental', label: 'Environmental Impact' },
      { id: 'mistakes', label: 'Common Mistakes' },
      { id: 'faq', label: 'FAQ' },
    ],
    professional: {
      price: '$299 – $799',
      description: 'Umuve handles the complete hot tub removal process — draining if needed, coordinating electrical disconnection, cutting the shell into manageable sections with reciprocating saws, removing all debris including insulation foam, and hauling everything to recycling or disposal. We work around backyard gates, fences, and landscaping. Acrylic shell material, wood framing, copper wiring, and metal hardware are all separated for maximum recycling.',
      includes: ['Full demolition and removal', 'Coordination of electrical disconnection', 'Cutting into sections for gate-width removal', 'Debris hauling', '73% materials recycled'],
    },
    curbside: {
      palmBeach: 'Hot tubs are too large for standard curbside bulk pickup. Palm Beach County SWA requires hot tubs to go to transfer stations. You can haul the disassembled sections yourself, or hire a roll-off dumpster (7-yard minimum for a hot tub job) for $300-$450 for 3-5 days.',
      broward: 'Broward County does not accept whole hot tubs as bulk pickup. Disassembled sections broken to 4 feet or less may be accepted as construction debris in some cities. Contact your city solid waste department. Most homeowners use a combination of contractor bags for insulation and a dumpster for the shell.',
      miamiDade: 'Miami-Dade requires hot tubs to be dismantled before disposal. The county transfer stations accept hot tub debris by weight. A fully dismantled hot tub typically weighs 400-800 lbs and costs $50-$120 to dispose of at county facilities.',
    },
    donation: 'Working hot tubs in good condition (functional jets, no major cracks, working heater) have real resale value in South Florida. Post on Facebook Marketplace — working above-ground hot tubs sell for $200-$1,500 depending on brand, age, and condition. If the buyer can arrange their own removal, you might get paid instead of paying. Non-working hot tubs occasionally find takers for parts or as water features. Fully cracked or beyond-repair units have no donation value.',
    diy: 'DIY hot tub demolition is doable in a weekend with the right tools and help. You will need: a reciprocating saw with demolition blades ($15-$40/day rental from Home Depot), safety goggles and gloves, 2-3 helpers, contractor bags for insulation foam, a pickup truck or trailer for debris. Process: (1) drain completely, (2) have electrician disconnect power, (3) cut the shell into 3-foot sections, (4) remove and bag insulation foam, (5) detach wood framing, (6) sort acrylic, wood, and metal separately. Haul to transfer station or fill a rental dumpster. Expect 4-8 hours of work.',
    costTable: [
      { method: 'Umuve Professional Removal', cost: '$299 – $799', time: 'Same day', effort: 'Zero', eco: '73% recycled' },
      { method: 'Roll-Off Dumpster + DIY Demo', cost: '$350 – $550', time: 'Weekend', effort: 'Very high', eco: 'Partial' },
      { method: 'Transfer Station (self-haul after demo)', cost: '$50 – $120 disposal + labor', time: '1–2 days', effort: 'High', eco: 'Partial' },
      { method: 'Sell Working Unit (Facebook Marketplace)', cost: 'Free (earn $200–$1,500)', time: '1–14 days', effort: 'Low', eco: 'Best' },
    ],
    environmental: 'A standard hot tub contains 200-400 lbs of fiberglass-reinforced acrylic (not easily recyclable), 100-200 lbs of polyurethane foam insulation, 50-100 lbs of framing lumber, and 30-60 lbs of PVC plumbing, copper wiring, and steel hardware. The acrylic shell is the most challenging component — acrylic is technically recyclable but few South Florida facilities accept it, so most shell material goes to landfill. The metal hardware, wiring, and some wood framing can be recycled. Umuve achieves 73% recovery rate primarily through the metal and wood streams.',
    mistakes: [
      { title: 'Attempting electrical disconnection without a licensed electrician', body: 'Hot tubs run on 240V GFCI circuits. Incorrect disconnection can result in electrocution or electrical fires. Always have a licensed electrician disconnect the circuit before any demolition work begins.' },
      { title: 'Underestimating the weight and complexity', body: 'A 6-person hot tub can weigh 600-900 lbs empty. The insulation foam, while light, is extremely bulky. Most homeowners who start DIY demolition call for professional help by hour two.' },
      { title: 'Not checking if the unit is functional before demolition', body: 'A working hot tub is worth $300-$1,500 on Facebook Marketplace. Spending $300-$800 to demolish something you could sell for $500 is a common and avoidable mistake.' },
      { title: 'Forgetting that hot tub permits may have been filed', body: 'Some hot tubs in South Florida were installed under permit. When you remove the unit, you may need to close out the permit with the county or city building department. Check your property records before removal.' },
    ],
    faqs: [
      { q: 'How much does hot tub removal cost in South Florida?', a: 'Professional hot tub removal in South Florida ranges from $299 for a small above-ground unit to $799 for a large in-ground spa. Average cost is $425. This includes demolition, cutting, removal, and hauling. DIY approaches cost $150-$350 in materials and dumpster fees, plus significant labor.' },
      { q: 'Do I need an electrician before hot tub removal?', a: 'Yes. Hot tubs are connected to 240V GFCI circuits. The circuit must be disconnected and capped by a licensed electrician before any demolition work begins. Some junk removal companies (including Umuve) can coordinate this in advance.' },
      { q: 'Can a hot tub be removed through a gate?', a: 'After cutting into sections, yes. Most residential backyard gates are 36-48 inches wide. A hot tub shell cut into 3-foot sections fits through standard gates. We assess access during booking to plan the removal strategy.' },
      { q: 'Can I sell my hot tub instead of paying for removal?', a: 'If the jets and heater work and the shell has no major cracks, yes. Working hot tubs sell for $300-$1,500 on Facebook Marketplace in South Florida — this is a strong market. Non-working units with parts value may get $50-$200.' },
      { q: 'What is hot tub demolition and when is it necessary?', a: 'Demolition is cutting the hot tub shell into sections to allow removal through gates, fences, and narrow pathways. It is necessary whenever the unit cannot be removed whole — which is virtually every residential hot tub situation since they are installed before fences are built.' },
      { q: 'How long does hot tub removal take?', a: 'Professional removal typically takes 2-3 hours from start to finish. DIY demolition takes 4-8 hours for a standard unit. Same-day service is available from Umuve — we provide a 2-hour arrival window after booking.' },
    ],
  },

  // Guide 10: Washer Dryer
  {
    slug: 'how-to-dispose-of-a-washer-dryer',
    title: 'How to Dispose of a Washer and Dryer in South Florida (2026)',
    metaDescription: 'How to dispose of a washer and dryer in South Florida. Free utility rebates, county pickup, scrap metal options, and professional removal from $89.',
    h1: 'How to Dispose of a Washer and Dryer in South Florida',
    subtitle: 'Remove and recycle your old washer and dryer the right way in Palm Beach, Broward, and Miami-Dade.',
    quickAnswer: 'Washers and dryers are among the most recyclable appliances — primarily steel with copper motors and wiring. Professional removal starts at $89 per unit with Umuve, same-day. Scrap metal yards pay $5-$20 per unit. FPL does not offer rebates for washers and dryers (refrigerators only), but county curbside pickup handles them with advance scheduling, no special prep required.',
    serviceSlug: 'appliance-removal',
    serviceName: 'Appliance Removal',
    relatedGuides: [
      { slug: 'how-to-dispose-of-appliances', title: 'How to Dispose of Appliances' },
      { slug: 'how-to-dispose-of-a-refrigerator', title: 'How to Dispose of a Refrigerator' },
      { slug: 'how-to-dispose-of-a-dishwasher', title: 'How to Dispose of a Dishwasher' },
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'davie-fl', name: 'Davie' },
    ],
    toc: [
      { id: 'professional', label: 'Option 1: Professional Removal' },
      { id: 'curbside', label: 'Option 2: County Curbside' },
      { id: 'donation', label: 'Option 3: Donation & Selling' },
      { id: 'diy', label: 'Option 4: Scrap Metal & DIY Haul' },
      { id: 'cost-comparison', label: 'Cost Comparison' },
      { id: 'environmental', label: 'Environmental Impact' },
      { id: 'mistakes', label: 'Common Mistakes' },
      { id: 'faq', label: 'FAQ' },
    ],
    professional: {
      price: '$89 – $199 per unit, or $149 for both',
      description: 'Umuve removes washers and dryers from any location — laundry room, garage, second-floor closet. We disconnect water supply hoses and dryer vents. Both units are transported to certified metal recycling facilities. Booking both units together saves money. Most pickups take 20-30 minutes.',
      includes: ['Water hose and vent disconnection', 'Any floor or location', 'Same-day service', 'Certified metal recycling', 'Pricing discount for both units'],
    },
    curbside: {
      palmBeach: 'Palm Beach County SWA accepts washers and dryers as standard bulk items — no refrigerant concerns, no special prep. Schedule online at pbcswa.com or call (561) 697-2700. Set at curb by 6 AM on pickup day. 5-10 business day lead time typical.',
      broward: 'Broward County cities handle washers and dryers as part of standard bulk pickup. They are straightforward to collect because they contain no hazardous materials. Call your city solid waste department — most cities schedule within 5-7 business days.',
      miamiDade: 'Miami-Dade Solid Waste accepts washers and dryers through standard bulk pickup programs. Most municipalities allow 2 large appliances per week curbside. City of Miami residents call 311. Miami Beach has separate bulk pickup scheduling at miamibeachfl.gov/sanitation.',
    },
    donation: 'Working washers and dryers are highly sought after for donation. Habitat for Humanity ReStores accept working laundry appliances. The Salvation Army offers free furniture and appliance pickup for qualifying donations in South Florida — call your local store to confirm washer/dryer pickup availability. Community assistance organizations like Catholic Charities and United Way affiliates in South Florida sometimes coordinate appliance donations for families in need. Working units also sell well: $75-$250 each on Facebook Marketplace or Craigslist for name brands in good condition.',
    diy: 'Washers and dryers are the most DIY-friendly appliances for disposal. They contain no hazardous materials requiring special handling. A standard washer is 150-200 lbs; a dryer is 100-140 lbs. With an appliance dolly ($15-$25/day rental), one or two people can handle them. Scrap metal yards pay $5-$20 per unit. The copper motor inside a washing machine makes it more valuable at scrap — do not disassemble before the yard as they account for the copper when weighing. Transfer station disposal runs $30-$60 per unit.',
    costTable: [
      { method: 'Umuve Professional Removal', cost: '$89–$149 per unit', time: 'Same day', effort: 'Zero', eco: 'Certified recycling' },
      { method: 'County Curbside', cost: 'Free', time: '5–14 days', effort: 'Move to curb', eco: 'Partial recycling' },
      { method: 'Scrap Metal Yard (self-haul)', cost: 'Free + $5–$20 income', time: 'Same day', effort: 'Medium', eco: 'Good recycling' },
      { method: 'Donation (working units)', cost: 'Free', time: '1–7 days', effort: 'Low', eco: 'Best' },
    ],
    environmental: 'A washing machine contains approximately 100-120 lbs of steel, 10-15 lbs of copper (motor windings and wiring), 15-25 lbs of stainless steel drum material, and 10-20 lbs of plastic tubs and components. The copper content makes washing machines particularly valuable for metal recyclers — copper trades at $3-$4/lb. Dryers are primarily steel with aluminum drum components. Both appliances achieve near-100% material recovery at certified metal recyclers through magnetic separation, shredding, and non-ferrous sorting.',
    mistakes: [
      { title: 'Not checking if the appliance has resale value', body: 'A working LG, Samsung, or Whirlpool washer less than 8 years old sells for $150-$350 on Facebook Marketplace in South Florida. Spending $89 to remove something worth $200 is worth a 10-minute listing first.' },
      { title: 'Forgetting to disconnect water supply hoses', body: 'Leaving supply hoses connected when moving a washer usually results in a flooded laundry room. Turn off the water supply valves and disconnect hoses before any washer move. Umuve handles this during professional pickup.' },
      { title: 'Moving heavy appliances without an appliance dolly', body: 'Washing machines weigh 150-200 lbs. Without a dolly, you will scratch floors and risk injury. Appliance dollies are $15-$25/day at Home Depot or U-Haul.' },
      { title: 'Stacking units before confirming the receiving facility accepts them', body: 'Some charity donation centers refuse older or front-load washers due to mold issues. Call before transporting.' },
    ],
    faqs: [
      { q: 'How much does washer and dryer removal cost in South Florida?', a: 'Umuve charges $89-$149 per unit, or $149 for both units together. County curbside is free with 5-14 day scheduling. Scrap metal yards accept them free and may pay you $5-$20 per unit.' },
      { q: 'Does FPL offer rebates for old washers and dryers?', a: 'No. FPL\'s appliance rebate program covers refrigerators and freezers only. ENERGY STAR appliance rebates for new purchases are sometimes available from FPL but do not apply to old unit disposal.' },
      { q: 'Can I donate a working washer and dryer in South Florida?', a: 'Yes. Habitat for Humanity ReStores, Salvation Army, and community assistance organizations accept working laundry appliances. Salvation Army offers free pickup in many South Florida areas — call (800) 728-7825.' },
      { q: 'How do scrap metal yards handle washers and dryers?', a: 'They weigh the unit and pay by pound at current scrap steel rates ($0.04-$0.07/lb for steel, more for copper). A 200-lb washer earns $8-$14 at current market rates. The copper motor increases value. Bring ID and the unit in any condition.' },
      { q: 'Does Umuve disconnect the washer before removal?', a: 'Yes. We disconnect water supply lines and the drain hose. Dryer vent disconnection is also included. For gas dryers, we recommend having a gas technician disconnect the gas line before our arrival.' },
      { q: 'Can Umuve remove a stacked washer and dryer from a closet?', a: 'Yes. Stacked laundry units in tight closets are common in South Florida apartments and condos. We unstacked, remove, and carry both units out. High-rise buildings with service elevator rules are also accommodated.' },
    ],
  },

  // Guide 11: Concrete
  {
    slug: 'how-to-dispose-of-concrete',
    title: 'How to Dispose of Concrete in South Florida (2026)',
    metaDescription: 'How to dispose of concrete, pavers, and masonry debris in South Florida. Free crusher run programs, construction debris hauling, and costs per yard.',
    h1: 'How to Dispose of Concrete in South Florida',
    subtitle: 'Concrete removal, disposal, and recycling options for homeowners and contractors in South Florida.',
    quickAnswer: 'Concrete cannot go in regular household trash in South Florida. Options include: hiring professional construction debris removal starting at $149, renting a dumpster ($300-$500 for a 10-yard roll-off), hauling to a concrete recycler (some are free), or calling Umuve for same-day concrete removal. Crushed concrete is recycled into road base, fill material, and new aggregate — reducing mining demand.',
    serviceSlug: 'construction-debris',
    serviceName: 'Construction Debris',
    relatedGuides: [
      { slug: 'how-to-dispose-of-drywall', title: 'How to Dispose of Drywall' },
      { slug: 'renovation-debris-disposal-guide', title: 'Renovation Debris Disposal Guide' },
      { slug: 'how-to-remove-a-toilet', title: 'How to Remove a Toilet' },
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'davie-fl', name: 'Davie' },
    ],
    toc: [
      { id: 'professional', label: 'Option 1: Professional Hauling' },
      { id: 'curbside', label: 'Option 2: Concrete Recyclers' },
      { id: 'donation', label: 'Option 3: Reuse & Repurpose' },
      { id: 'diy', label: 'Option 4: DIY Haul or Dumpster' },
      { id: 'cost-comparison', label: 'Cost Comparison' },
      { id: 'environmental', label: 'Environmental Impact' },
      { id: 'mistakes', label: 'Common Mistakes' },
      { id: 'faq', label: 'FAQ' },
    ],
    professional: {
      price: '$149 – $899',
      description: 'Umuve removes concrete debris from patios, driveways, sidewalks, steps, pavers, and demolition projects. Broken concrete slabs, rebar, and block are all accepted. We transport to certified concrete recyclers where material is crushed into recycled aggregate. Pricing is volume-based — a small pile of broken patio concrete may be $149-$249; a full driveway removal is $399-$899. Same-day availability for most jobs.',
      includes: ['Broken concrete, pavers, and block accepted', 'Rebar and mixed masonry included', 'Transport to certified concrete recycler', 'Same-day service', 'Volume-based pricing'],
    },
    curbside: {
      palmBeach: 'Palm Beach County SWA does not accept concrete, bricks, or masonry as curbside bulk items. These are classified as construction and demolition (C&D) debris and must go to licensed C&D facilities. The SWA operates a C&D transfer station — call for current pricing and hours.',
      broward: 'Broward County classifies concrete as C&D debris excluded from standard curbside pickup. The county operates C&D recycling facilities at several locations. Contractors and homeowners can drop off at licensed C&D processors like Republic Services C&D facilities in the county.',
      miamiDade: 'Miami-Dade County requires concrete to go to approved C&D disposal or recycling facilities. The county has licensed C&D processors in several locations. Some concrete recyclers in the area accept clean concrete (no rebar, no asphalt) for free as they can sell the processed aggregate.',
    },
    donation: 'Clean, broken concrete can be repurposed on-site or given away. In South Florida\'s gardening community, broken concrete chunks (urbanite) are used to build retaining walls, raised beds, and decorative borders without mortar. Post on Facebook Marketplace or Nextdoor — "free broken concrete, you haul" often gets takers. Landscapers sometimes take free concrete for fill. Large pavers in good condition can be sold for $0.50-$3 each depending on type and condition.',
    diy: 'For small quantities, renting a truck and hauling to a concrete recycler is cost-effective. Many South Florida concrete recyclers accept clean concrete (no wood, no drywall mixed in) for free or low cost ($10-$30/ton) because they resell the crushed product. Home Depot and Lowe\'s rent trucks by the hour for DIY hauls. For larger volumes, a 10-yard roll-off dumpster ($300-$500 for 3-5 days) from Republic Services or WM is the standard contractor option. Note: concrete is heavy — a 10-yard dumpster filled with concrete can exceed weight limits. Most haulers charge $60-$80 per ton over the included weight.',
    costTable: [
      { method: 'Umuve Professional Removal', cost: '$149 – $899', time: 'Same day', effort: 'Zero', eco: 'Recycled into aggregate' },
      { method: 'Concrete Recycler Drop-Off (clean concrete)', cost: 'Free – $30/ton', time: 'Same day', effort: 'You haul', eco: 'Excellent' },
      { method: 'Roll-Off Dumpster (10 yd)', cost: '$300 – $500', time: '3–5 day rental', effort: 'You load', eco: 'C&D recycler' },
      { method: 'Repurpose On-Site (urbanite)', cost: 'Free', time: 'Variable', effort: 'Medium', eco: 'Best' },
    ],
    environmental: 'Concrete production accounts for approximately 8% of global CO2 emissions. Recycling existing concrete into crusher run, road base, and aggregate prevents the mining of virgin limestone and sand — important in South Florida where mining has significant environmental impacts on aquifer recharge zones. Recycled concrete aggregate performs comparably to virgin aggregate in most road base and fill applications. South Florida\'s construction industry is a large consumer of recycled concrete. Every ton of concrete recycled prevents approximately 900 kg of quarrying from impacting South Florida\'s sensitive aquifer recharge areas.',
    mistakes: [
      { title: 'Mixing concrete with other trash', body: 'Concrete mixed with wood, drywall, or other debris cannot go to concrete-only recyclers. Mixed C&D debris is more expensive to dispose of. Keep concrete separate to access the cheapest and most eco-friendly disposal options.' },
      { title: 'Underestimating concrete weight', body: 'Concrete weighs approximately 150 lbs per cubic foot. A 10x10 foot patio slab 4 inches thick weighs roughly 5,000 lbs. Most pickup trucks are rated for 1,500-2,000 lbs of payload. Overloading a truck is dangerous and illegal.' },
      { title: 'Renting a dumpster and filling it entirely with concrete', body: 'Standard dumpsters have weight limits (usually 4-6 tons) but capacity for much more concrete. Overage fees are steep. For pure concrete jobs, hire a company that specializes in heavy C&D debris with appropriate equipment.' },
      { title: 'Disposing of concrete with rebar mixed into a "clean concrete only" facility', body: 'Rebar-reinforced concrete requires a grinder or crusher that can handle the steel. Not all concrete recyclers accept reinforced concrete. Confirm the facility\'s requirements before hauling.' },
    ],
    faqs: [
      { q: 'Can I put concrete in a dumpster in South Florida?', a: 'Yes, in most C&D roll-off dumpsters. However, concrete is very heavy and most dumpster companies have weight limits. A 10-yard dumpster filled with concrete will exceed most standard limits. Discuss weight limits and overage fees before renting.' },
      { q: 'Where can I take concrete for free in South Florida?', a: 'Some concrete recyclers accept clean broken concrete (no mixed debris) for free because they resell the crushed material. Search for "concrete recycler" near your area and call to confirm free acceptance. Always confirm it must be clean concrete only.' },
      { q: 'How much does concrete removal cost in South Florida?', a: 'Professional concrete removal starts at $149 for a small pile (under 1/2 yard) and runs up to $899 for a full driveway or large patio. Cost depends on volume and weight. DIY haul to a recycler costs $0-$60 if you have a capable truck.' },
      { q: 'Is broken concrete recyclable?', a: 'Yes. Crushed concrete is used as road base, drainage fill, and aggregate in new concrete mixes. South Florida\'s construction industry uses large quantities of recycled concrete aggregate as a sustainable alternative to mined limestone.' },
      { q: 'Can Umuve remove a concrete patio?', a: 'Umuve removes the broken concrete debris after demolition. If you need the patio actually broken up (demolition), we can coordinate that service as well. Contact us for a custom quote on combined demolition and removal.' },
      { q: 'Does concrete removal require a permit in South Florida?', a: 'Hauling broken concrete typically does not require a permit. However, demolishing a concrete structure (patio, driveway, pool deck) may require a demolition permit from your city or county building department. Check before starting demo work.' },
    ],
  },

  // Guide 12: Drywall
  {
    slug: 'how-to-dispose-of-drywall',
    title: 'How to Dispose of Drywall in South Florida (2026)',
    metaDescription: 'How to dispose of drywall and sheetrock in South Florida. C&D debris rules, drywall recycling, professional hauling costs, and what you need to know about old drywall.',
    h1: 'How to Dispose of Drywall in South Florida',
    subtitle: 'Proper drywall disposal and recycling for homeowners and contractors in Palm Beach, Broward, and Miami-Dade.',
    quickAnswer: 'Drywall (sheetrock) is classified as construction and demolition debris in South Florida and cannot go in regular trash. New, clean drywall can often be recycled for free at specialized facilities. Old drywall (pre-1980) may contain asbestos and requires testing before disposal. Professional C&D hauling starts at $149. Umuve handles drywall removal as part of renovation cleanouts.',
    serviceSlug: 'construction-debris',
    serviceName: 'Construction Debris',
    relatedGuides: [
      { slug: 'how-to-remove-drywall', title: 'How to Remove Drywall' },
      { slug: 'how-to-dispose-of-concrete', title: 'How to Dispose of Concrete' },
      { slug: 'renovation-debris-disposal-guide', title: 'Renovation Debris Disposal Guide' },
      { slug: 'how-to-remove-a-kitchen-sink', title: 'How to Remove a Kitchen Sink' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'doral-fl', name: 'Doral' },
    ],
    toc: [
      { id: 'professional', label: 'Option 1: Professional Hauling' },
      { id: 'curbside', label: 'Option 2: C&D Facilities' },
      { id: 'donation', label: 'Option 3: Drywall Recycling' },
      { id: 'diy', label: 'Option 4: DIY C&D Disposal' },
      { id: 'cost-comparison', label: 'Cost Comparison' },
      { id: 'environmental', label: 'Environmental Impact' },
      { id: 'mistakes', label: 'Common Mistakes' },
      { id: 'faq', label: 'FAQ' },
    ],
    professional: {
      price: '$149 – $899',
      description: 'Umuve removes drywall debris from renovation projects, demolitions, and water damage repairs. We handle broken sheetrock, drywall dust, joint compound waste, and mixed renovation debris. All material is transported to licensed C&D facilities. We do NOT accept asbestos-containing drywall — if your home was built before 1980, test for asbestos before booking.',
      includes: ['Broken drywall and sheetrock accepted', 'Mixed renovation debris included', 'Licensed C&D facility disposal', 'Volume-based pricing', 'Same-day service'],
    },
    curbside: {
      palmBeach: 'Drywall is excluded from Palm Beach County curbside bulk pickup. It must go to C&D debris processors. The SWA\'s C&D facility at 7501 N Jog Road in West Palm Beach accepts drywall by weight for homeowners. Call (561) 697-2700 for current rates.',
      broward: 'Broward County classifies drywall as C&D debris. The county operates C&D processing at the North Broward County Solid Waste Facility. Clean drywall (unpainted, no joint compound) may qualify for free recycling at some Broward gypsum recyclers.',
      miamiDade: 'Miami-Dade C&D processors accept drywall. Clean, new drywall scraps can go to gypsum recyclers. Painted or water-damaged drywall goes to general C&D disposal at county transfer stations. Fees vary by volume.',
    },
    donation: 'Leftover new, unopened drywall can be donated to Habitat for Humanity ReStore construction material departments. Full or partial sheets in undamaged condition are accepted. Demolition drywall cannot be donated. Some contractors and handymen will take partial sheets of good drywall for free from Nextdoor or Facebook Marketplace for small repairs.',
    diy: 'Small quantities of drywall can be managed with contractor bags (60-gallon, heavy-duty) for transport. A pickup truck can carry 10-15 full 4x8 sheets, but broken drywall is bulky and dusty. Wear a dust mask — gypsum dust is an irritant. Haul to the county C&D facility or hire a roll-off dumpster for larger renovation quantities. Dedicated drywall recyclers in South Florida sometimes take clean, unpainted drywall for free because gypsum is reclaimed as agricultural soil amendment and new drywall manufacturing feedstock.',
    costTable: [
      { method: 'Umuve Professional Removal', cost: '$149 – $899', time: 'Same day', effort: 'Zero', eco: 'C&D facility' },
      { method: 'County C&D Drop-Off', cost: '$30–$80 per load', time: 'Same day', effort: 'You transport', eco: 'Some recycling' },
      { method: 'Gypsum Recycler (clean drywall only)', cost: 'Free', time: 'Same day', effort: 'You transport', eco: 'Excellent' },
      { method: 'Roll-Off Dumpster (C&D)', cost: '$250 – $450', time: '3–5 day rental', effort: 'You load', eco: 'Partial' },
    ],
    environmental: 'Drywall is made primarily of gypsum (calcium sulfate), a natural mineral. When clean drywall is recycled, the gypsum is reclaimed and used as: soil amendment in agriculture (neutralizes acidic soil), feedstock for new drywall manufacturing, and filler in Portland cement. When drywall goes to landfill and gets wet, it breaks down into hydrogen sulfide gas — a toxic gas responsible for the "rotten egg" smell at some landfills and a known respiratory hazard. South Florida\'s humid climate accelerates this process, making drywall recycling especially valuable here.',
    mistakes: [
      { title: 'Not testing pre-1980 drywall for asbestos', body: 'Drywall manufactured before 1980 and joint compound from the same era may contain asbestos. Disturbing this material without testing is a serious health hazard. Hire a certified asbestos inspector ($200-$400) before any demolition in older homes.' },
      { title: 'Mixing drywall with other C&D debris unnecessarily', body: 'Clean, unpainted drywall can often be recycled for free. Once mixed with concrete, wood, or painted material, it becomes mixed C&D debris that costs more to dispose of. Keep clean drywall separate during demolition.' },
      { title: 'Assuming drywall can go in a regular residential dumpster', body: 'Residential "junk" dumpsters often specifically exclude construction debris, including drywall. Using the wrong dumpster type can result in overage fees or rejection. Always confirm C&D acceptance before renting.' },
      { title: 'Disposing of drywall dust improperly', body: 'Gypsum dust from cutting and sanding should be collected in sealed bags. Do not blow or wash drywall dust into storm drains — it affects water quality in South Florida\'s canals and coastal waterways.' },
    ],
    faqs: [
      { q: 'Can drywall go in the regular trash in South Florida?', a: 'No. Drywall is classified as C&D debris and is excluded from residential curbside trash in all three South Florida counties. It must go to licensed C&D facilities or certified recyclers.' },
      { q: 'Does old drywall contain asbestos?', a: 'Drywall manufactured before 1980 — and joint compound from the same era — may contain asbestos. If your home was built before 1980 and you are doing renovation work, have a certified asbestos inspector test the material before disturbing it.' },
      { q: 'Where can I recycle clean drywall for free in South Florida?', a: 'Several gypsum recyclers in South Florida accept clean, unpainted drywall at no charge. Search for "gypsum recycler" or "drywall recycler" in your area. Clean means no paint, no joint compound, no tape, no paper backing — this varies by facility. Call ahead.' },
      { q: 'How much does drywall removal cost?', a: 'Professional C&D hauling by Umuve starts at $149 for a small quantity and runs to $899 for a large renovation. County C&D drop-off typically costs $30-$80 per truckload. Clean drywall recycling is free at qualifying facilities.' },
      { q: 'Can I put drywall in a dumpster?', a: 'Yes, in a C&D roll-off dumpster. Confirm with the rental company that drywall is accepted. Standard residential junk dumpsters may exclude construction materials. C&D dumpsters from Republic Services or WM in South Florida explicitly accept drywall.' },
      { q: 'What is gypsum recycling used for?', a: 'Recycled gypsum is used as agricultural soil amendment to improve drainage and reduce soil acidity. It is also used as feedstock for new drywall production, reducing the need to mine natural gypsum. South Florida\'s extensive agriculture industry is a large consumer of recycled gypsum.' },
    ],
  },
];

// ─── Additional guides (lifestyle + how-to removal) ────────────────────────

const lifestyleGuides = [
  {
    slug: 'how-to-dispose-of-a-dishwasher',
    title: 'How to Dispose of a Dishwasher in South Florida (2026)',
    metaDescription: 'How to dispose of an old dishwasher in South Florida. Disconnection steps, county pickup options, scrap metal value, and professional removal from $89.',
    h1: 'How to Dispose of a Dishwasher in South Florida',
    subtitle: 'Dishwasher removal and disposal options across Palm Beach, Broward, and Miami-Dade.',
    quickAnswer: 'Dishwashers are primarily steel and plastic with no hazardous materials requiring special handling. They qualify for free county curbside bulk pickup (advance scheduling), sell to scrap metal yards for $5-$15, or can be professionally removed by Umuve for $89. Disconnection requires turning off the water supply valve under the sink and uncoupling the drain hose.',
    serviceSlug: 'appliance-removal',
    serviceName: 'Appliance Removal',
    isSimple: true,
    keyPoints: [
      'Turn off water supply (under-sink valve) and disconnect power at the breaker before removal.',
      'Dishwashers contain no hazardous refrigerants — no special prep for county curbside.',
      'Most South Florida cities accept dishwashers as standard bulk pickup items.',
      'Scrap metal yards pay $5-$15 per unit — call ahead for current rates.',
      'Working dishwashers sell for $50-$150 on Facebook Marketplace or Craigslist.',
      'Umuve removes dishwashers starting at $89, including disconnection and hauling.',
    ],
    relatedGuides: [
      { slug: 'how-to-dispose-of-appliances', title: 'How to Dispose of Appliances' },
      { slug: 'how-to-dispose-of-a-washer-dryer', title: 'How to Dispose of a Washer and Dryer' },
      { slug: 'how-to-remove-a-kitchen-sink', title: 'How to Remove a Kitchen Sink' },
      { slug: 'renovation-debris-disposal-guide', title: 'Renovation Debris Disposal Guide' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'hollywood-fl', name: 'Hollywood' },
    ],
  },
  {
    slug: 'how-to-dispose-of-a-dehumidifier',
    title: 'How to Dispose of a Dehumidifier in South Florida (2026)',
    metaDescription: 'How to dispose of a dehumidifier in South Florida. Refrigerant rules, free county pickup, FPL rebates, and professional removal.',
    h1: 'How to Dispose of a Dehumidifier in South Florida',
    subtitle: 'EPA-compliant dehumidifier disposal — refrigerant rules, rebates, and pickup options.',
    quickAnswer: 'Dehumidifiers contain refrigerants (R-410A or R-22) that require EPA-certified recovery before disposal — the same requirement as refrigerators and AC units. FPL\'s appliance recycling program sometimes covers dehumidifiers. County curbside requires certified refrigerant evacuation first. Umuve handles dehumidifiers from $89 with certified refrigerant handling.',
    serviceSlug: 'appliance-removal',
    serviceName: 'Appliance Removal',
    isSimple: true,
    keyPoints: [
      'Dehumidifiers contain refrigerants — same EPA rules as refrigerators apply.',
      'Do not crush, puncture, or cut refrigerant lines — illegal under the Clean Air Act.',
      'Check FPL\'s appliance rebate program for dehumidifier eligibility (800-226-3545).',
      'County curbside requires documented refrigerant removal — same as air conditioners.',
      'Professional removal by Umuve starts at $89, includes EPA-compliant refrigerant handling.',
      'Working units sell for $30-$100 on Facebook Marketplace depending on capacity.',
    ],
    relatedGuides: [
      { slug: 'how-to-dispose-of-appliances', title: 'How to Dispose of Appliances' },
      { slug: 'how-to-dispose-of-a-refrigerator', title: 'How to Dispose of a Refrigerator' },
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
      { slug: 'how-to-dispose-of-a-washer-dryer', title: 'How to Dispose of a Washer and Dryer' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
  },
  {
    slug: 'how-to-dispose-of-a-stove-oven',
    title: 'How to Dispose of a Stove or Oven in South Florida (2026)',
    metaDescription: 'How to dispose of an old stove or oven in South Florida. Gas vs electric disconnection, county pickup, scrap value, and professional removal from $89.',
    h1: 'How to Dispose of a Stove or Oven in South Florida',
    subtitle: 'Gas and electric stove removal and disposal across Palm Beach, Broward, and Miami-Dade.',
    quickAnswer: 'Stoves and ovens are primarily steel with no hazardous materials (no refrigerants). Gas stoves require a licensed plumber or gas technician to disconnect the gas line before removal. Electric stoves are straightforward to disconnect and haul. County curbside accepts both. Scrap metal yards take stoves for $5-$20. Umuve removes stoves from $89.',
    serviceSlug: 'appliance-removal',
    serviceName: 'Appliance Removal',
    isSimple: true,
    keyPoints: [
      'Gas stoves: ALWAYS have a licensed gas technician cap the gas line before moving. Never disconnect gas yourself.',
      'Electric stoves: unplug (120V) or turn off the breaker (240V) before disconnecting the plug.',
      'Both types are accepted as standard bulk curbside items — no special hazardous waste prep.',
      'Scrap metal yards pay $5-$20 per stove/oven. Bring ID; some require title/proof of ownership.',
      'Working gas ranges sell for $100-$300 on Facebook Marketplace; electric for $75-$200.',
      'Professional removal by Umuve starts at $89 including disconnection coordination.',
    ],
    relatedGuides: [
      { slug: 'how-to-dispose-of-appliances', title: 'How to Dispose of Appliances' },
      { slug: 'how-to-dispose-of-a-washer-dryer', title: 'How to Dispose of a Washer and Dryer' },
      { slug: 'how-to-remove-a-kitchen-sink', title: 'How to Remove a Kitchen Sink' },
      { slug: 'renovation-debris-disposal-guide', title: 'Renovation Debris Disposal Guide' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'coral-springs-fl', name: 'Coral Springs' },
    ],
  },
];

// ─── DIY Removal Guides ───────────────────────────────────────────────────────

const diyGuides = [
  {
    slug: 'how-to-remove-a-toilet',
    title: 'How to Remove a Toilet (Step-by-Step Guide for South Florida)',
    metaDescription: 'Step-by-step guide to removing a toilet yourself. Tools needed, safety tips, disposal options, and when to call a plumber. South Florida specific tips.',
    h1: 'How to Remove a Toilet: Step-by-Step Guide',
    subtitle: 'Remove your old toilet safely with this complete guide — then book Umuve to haul it away.',
    quickAnswer: 'Toilet removal is a manageable DIY project for most homeowners. You need: an adjustable wrench, utility knife, rubber gloves, a bucket, and a helper for the lift. The process takes 30-60 minutes. Once removed, the toilet can go to the county transfer station ($30-$60), a curbside bulk pickup (schedule first), or call Umuve for $89 same-day haul-away.',
    serviceSlug: 'construction-debris',
    serviceName: 'Construction Debris',
    isDiy: true,
    steps: [
      { num: '1', title: 'Turn off the water supply', body: 'Locate the shut-off valve on the wall behind the toilet and turn it clockwise until fully closed. Flush the toilet to empty the tank and bowl. Use a sponge to remove any remaining water from the tank and bowl — this reduces weight and prevents spills.' },
      { num: '2', title: 'Disconnect the water supply line', body: 'The braided metal or plastic line connects the shut-off valve to the bottom of the tank. Unscrew the nut at the tank connection by hand or with pliers. Have a towel or small bucket ready for residual water.' },
      { num: '3', title: 'Remove the tank lid and set aside', body: 'Lift the porcelain tank lid off and set it somewhere safe. It is fragile and heavy. If it breaks it becomes a sharp hazard.' },
      { num: '4', title: 'Unscrew the tank-to-bowl bolts', body: 'Inside the tank near the bottom are two bolts connecting the tank to the bowl. Use a screwdriver and adjustable wrench to remove them. Some are corroded — a penetrating lubricant (WD-40) helps. The tank should lift straight up once the bolts are out.' },
      { num: '5', title: 'Remove the toilet seat', body: 'Lift the plastic caps at the rear of the seat, unscrew the bolts, and remove the seat. This is optional but makes the bowl lighter and easier to carry.' },
      { num: '6', title: 'Cut the caulk line', body: 'Most toilets are caulked to the floor around the base. Run a utility knife around the entire perimeter to break the caulk seal. This prevents cracking the toilet or tile when lifting.' },
      { num: '7', title: 'Remove the floor bolt caps and nuts', body: 'Pop off the plastic caps at the base of the toilet. Unscrew the nuts with an adjustable wrench. The toilet is now held only by gravity and the wax ring.' },
      { num: '8', title: 'Lift and remove the bowl', body: 'Have your helper ready. Grip the bowl firmly at both sides. Rock gently forward and back to break the wax ring seal, then lift straight up. A standard toilet bowl weighs 60-100 lbs. Set it on cardboard or a tarp to avoid scratching the floor.' },
      { num: '9', title: 'Stuff the drain opening', body: 'Immediately stuff a rag or rubber plug into the floor drain opening. Sewer gases are toxic and can fill a room quickly. This is not optional.' },
      { num: '10', title: 'Scrape the old wax ring', body: 'Use a putty knife to scrape the old wax ring off the floor flange and discard it in a plastic bag. Wax rings are single-use and must be replaced for any new toilet installation.' },
    ],
    relatedGuides: [
      { slug: 'how-to-remove-drywall', title: 'How to Remove Drywall' },
      { slug: 'renovation-debris-disposal-guide', title: 'Renovation Debris Disposal Guide' },
      { slug: 'how-to-remove-a-kitchen-sink', title: 'How to Remove a Kitchen Sink' },
      { slug: 'how-to-dispose-of-concrete', title: 'How to Dispose of Concrete' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
    disposalNote: 'Once removed, your toilet can be disposed of through: (1) County curbside bulk pickup — schedule first, most cities accept porcelain fixtures; (2) County C&D transfer station drop-off ($30-$60); (3) Umuve same-day pickup starting at $89. Toilets in working condition can sometimes be donated to Habitat for Humanity ReStore.',
  },
  {
    slug: 'how-to-remove-drywall',
    title: 'How to Remove Drywall (Step-by-Step Guide)',
    metaDescription: 'Step-by-step drywall removal guide. Tools, safety tips for older homes, asbestos warnings, and disposal options in South Florida.',
    h1: 'How to Remove Drywall: Step-by-Step Guide',
    subtitle: 'Safe drywall removal from start to finish — plus disposal options across South Florida.',
    quickAnswer: 'Drywall removal is dusty, manageable DIY work. Before you start: if your home was built before 1980, test for asbestos in the drywall and joint compound. Tools needed include a utility knife, reciprocating saw, pry bar, and dust mask (N95 minimum). Debris must go to C&D facilities — not regular trash. Umuve hauls drywall debris same-day from $149.',
    serviceSlug: 'construction-debris',
    serviceName: 'Construction Debris',
    isDiy: true,
    steps: [
      { num: '1', title: 'Test for asbestos if home is pre-1980', body: 'Joint compound and some drywall products from before 1980 may contain asbestos. Hire a certified asbestos inspector ($200-$400) before disturbing any material in an older South Florida home. This is not optional — asbestos is a Class 1 human carcinogen.' },
      { num: '2', title: 'Turn off electrical circuits in the work area', body: 'Drywall conceals wiring, outlets, and switches. Turn off the relevant circuit breakers at the panel. Use a non-contact voltage tester near outlet locations before cutting.' },
      { num: '3', title: 'Score along studs with a utility knife', body: 'Find the stud locations with a stud finder. Score a vertical line along each stud edge with a sharp utility knife. This gives you a clean cut line and prevents jagged crumbling.' },
      { num: '4', title: 'Make horizontal cuts between studs', body: 'Use a reciprocating saw or drywall saw to cut horizontal lines between studs at the top and bottom of the section you are removing. Work in manageable sections — 4-foot wide pieces are easier to handle.' },
      { num: '5', title: 'Punch and pull the sections', body: 'Strike the drywall between scored cuts with your fist or a hammer to break it. Insert a pry bar and pull sections away from the wall. Work from the center of each section toward the edges.' },
      { num: '6', title: 'Remove drywall screws from studs', body: 'Use a drill with a screw bit or a pry bar to remove all remaining screws and nails from the studs. Leaving them in creates hazards during rebuilding.' },
      { num: '7', title: 'Collect and bag debris immediately', body: 'Gypsum dust is an irritant. Work with an N95 mask and eye protection. Collect debris into heavy-duty 60-gallon contractor bags as you go. Do not let it pile on the floor.' },
      { num: '8', title: 'Clean up residual dust', body: 'Vacuum with a HEPA-filter shop vac before sweeping — sweeping re-suspends fine particles. Damp mop afterward. Gypsum dust can clog HVAC filters if it circulates.' },
    ],
    relatedGuides: [
      { slug: 'how-to-dispose-of-drywall', title: 'How to Dispose of Drywall' },
      { slug: 'renovation-debris-disposal-guide', title: 'Renovation Debris Disposal Guide' },
      { slug: 'how-to-remove-a-toilet', title: 'How to Remove a Toilet' },
      { slug: 'how-to-remove-a-kitchen-sink', title: 'How to Remove a Kitchen Sink' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'coral-springs-fl', name: 'Coral Springs' },
    ],
    disposalNote: 'Drywall debris is C&D waste — not regular trash. Disposal options: (1) County C&D transfer station ($30-$80 per load); (2) Gypsum recycler (free for clean, unpainted drywall); (3) Umuve same-day hauling from $149. Never mix drywall with regular garbage — it is a code violation in all three South Florida counties.',
  },
  {
    slug: 'how-to-remove-a-kitchen-sink',
    title: 'How to Remove a Kitchen Sink (Step-by-Step Guide)',
    metaDescription: 'How to remove a kitchen sink yourself. Plumbing disconnection steps, tools needed, and disposal options in South Florida.',
    h1: 'How to Remove a Kitchen Sink: Step-by-Step Guide',
    subtitle: 'Remove your old kitchen sink safely — then haul it away or call Umuve.',
    quickAnswer: 'Kitchen sink removal requires turning off the water supply lines (under the sink), disconnecting the drain trap and garbage disposal if present, and lifting the sink out of the countertop. Stainless sinks can be donated to Habitat ReStore if in good condition. Cast iron sinks sell for $20-$80 at scrap metal yards. Umuve removes old sinks for $89.',
    serviceSlug: 'construction-debris',
    serviceName: 'Construction Debris',
    isDiy: true,
    steps: [
      { num: '1', title: 'Turn off water supply valves', body: 'Under the sink are two shut-off valves (hot and cold). Turn both clockwise until fully closed. Turn on the faucet to release any pressure and drain remaining water from the lines.' },
      { num: '2', title: 'Disconnect the supply lines', body: 'Use an adjustable wrench to unscrew the braided supply lines from both the shut-off valves and the faucet connections underneath. Have a towel ready — residual water will spill.' },
      { num: '3', title: 'Disconnect the garbage disposal (if present)', body: 'Turn off the disposal at the wall switch and unplug it from the outlet under the sink. Most disposals twist off a mounting ring — turn counterclockwise. Support the weight as it releases.' },
      { num: '4', title: 'Remove the drain trap (P-trap)', body: 'The curved pipe under the sink drain connects to the wall drain. Unscrew both slip nuts (hand-tighten only — use pliers if stuck) and pull the P-trap away. Water will spill — have your bucket ready.' },
      { num: '5', title: 'Disconnect the drain basket', body: 'From under the sink, unscrew the drain basket locknut with a locknut wrench or pliers. Once loosened, the basket can be pushed up and out from above.' },
      { num: '6', title: 'Remove mounting clips or brackets', body: 'Undermount sinks are held by mounting clips along the rim. Loosen the screws on each clip. Drop-in sinks may have clips or simply rest in a caulked cutout.' },
      { num: '7', title: 'Cut the caulk bead', body: 'Run a utility knife around the entire perimeter of the sink rim where it meets the countertop. Cut through all the caulk to prevent tearing the countertop when lifting.' },
      { num: '8', title: 'Lift out the sink', body: 'For drop-in sinks: push up from below and lift from above simultaneously. For undermount sinks: lower carefully once mounting clips are removed. Cast iron sinks can weigh 100-300 lbs — get help.' },
    ],
    relatedGuides: [
      { slug: 'renovation-debris-disposal-guide', title: 'Renovation Debris Disposal Guide' },
      { slug: 'how-to-remove-a-toilet', title: 'How to Remove a Toilet' },
      { slug: 'how-to-remove-drywall', title: 'How to Remove Drywall' },
      { slug: 'how-to-dispose-of-appliances', title: 'How to Dispose of Appliances' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'doral-fl', name: 'Doral' },
    ],
    disposalNote: 'Sink disposal options: (1) Stainless or cast iron sinks with scrap value go to scrap metal yards ($5-$80 depending on weight); (2) Porcelain sinks in excellent condition to Habitat ReStore; (3) County transfer station C&D drop-off; (4) Umuve pickup from $89 for a sink plus any other renovation debris.',
  },
  {
    slug: 'how-to-take-apart-a-bed-frame',
    title: 'How to Take Apart a Bed Frame (Step-by-Step)',
    metaDescription: 'How to disassemble and dispose of a bed frame. Step-by-step guide for wood, metal, and upholstered frames plus South Florida disposal options.',
    h1: 'How to Take Apart a Bed Frame',
    subtitle: 'Disassemble your old bed frame safely — wood, metal, and upholstered styles covered.',
    quickAnswer: 'Most bed frames take 15-30 minutes to disassemble with basic tools. Metal frames: remove bolts at corner joints. Wood platform beds: unscrew the slats then the side rails from the headboard and footboard. Upholstered frames: no disassembly needed, just remove for pickup. Umuve removes bed frames for $89, or county curbside is free with scheduling.',
    serviceSlug: 'furniture-removal',
    serviceName: 'Furniture Removal',
    isDiy: true,
    steps: [
      { num: '1', title: 'Remove the mattress and box spring first', body: 'Clear the entire sleeping surface — mattress, box spring, and any foam toppers. Set aside or schedule a separate pickup. Working on an empty frame is much easier and safer.' },
      { num: '2', title: 'Remove slats (platform and wood frames)', body: 'Lift out any individual wooden slats from their notches or hooks. Bundle and tie them together. If they are screwed down, use a drill with a screw bit to remove them first.' },
      { num: '3', title: 'Photograph the frame before disassembly', body: 'If there is any chance you might want to reassemble, take photos of the joint connections before breaking them down. This also helps if you are selling parts.' },
      { num: '4', title: 'Locate and remove all bolts and screws', body: 'Metal frames typically use hex bolts at corner brackets — use an Allen wrench or socket. Wood frames may use cam-lock fasteners, screws, or bolts at rail-to-headboard joints. Check underneath the frame for any floor brackets.' },
      { num: '5', title: 'Separate the rails from headboard and footboard', body: 'Once all hardware is removed, slide or lift the side rails out of their brackets. Most bed frame systems separate into: headboard, footboard, two side rails, and slats.' },
      { num: '6', title: 'Break down upholstered frames', body: 'Upholstered platform beds typically do not need to be disassembled for removal — they can be taken whole. If needed for door clearance, check if the headboard detaches (usually 2-4 bolts at the back).' },
      { num: '7', title: 'Bundle and tie components', body: 'Tie metal rails together and wooden slats into bundles for easier transport. This also prevents pieces from scratching walls and floors during removal.' },
    ],
    relatedGuides: [
      { slug: 'how-to-dispose-of-a-mattress', title: 'How to Dispose of a Mattress' },
      { slug: 'what-to-do-with-old-furniture', title: 'What to Do with Old Furniture' },
      { slug: 'declutter-before-moving', title: 'Declutter Before Moving' },
      { slug: 'how-to-take-apart-a-couch', title: 'How to Take Apart a Couch' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
    disposalNote: 'Bed frame disposal options: (1) Metal frames go to scrap metal yards ($5-$15); (2) Wood frames can go curbside with scheduling; (3) Solid wood frames in good condition to Habitat ReStore or Craigslist; (4) Umuve picks up bed frames plus mattresses together for best value — starting at $89 for both.',
  },
  {
    slug: 'how-to-take-apart-a-couch',
    title: 'How to Take Apart a Couch or Sectional',
    metaDescription: 'How to disassemble a couch, sofa, or sectional for disposal or moving. Step-by-step breakdown guide for South Florida homeowners.',
    h1: 'How to Take Apart a Couch or Sectional',
    subtitle: 'Break down your sofa or sectional for easier removal, moving, or disposal.',
    quickAnswer: 'A couch can be broken down into: removable cushions (separate immediately), sections of a sectional (connected by metal clips), and the frame itself (upholstery cut away, wood and metal separated). Full disassembly takes 30-90 minutes with a utility knife, reciprocating saw, pry bar, and bolt cutter. Or call Umuve — we handle this for you starting at $89.',
    serviceSlug: 'couch-removal',
    serviceName: 'Couch Removal',
    isDiy: true,
    steps: [
      { num: '1', title: 'Remove cushions and pillows', body: 'Strip all loose cushions and pillows. Check under cushions for coins, remotes, and small items before proceeding. Cushions can often be compressed and bagged for separate trash disposal.' },
      { num: '2', title: 'Disconnect sectional sections', body: 'Sectional sofas connect via metal clips or hooks on the underside. Tilt one section and look for the connecting hardware. Metal clasps typically slide up and off; metal clips may need a flathead screwdriver to release.' },
      { num: '3', title: 'Remove the legs', body: 'Most couch legs screw off counterclockwise. Removing them reduces overall height by 4-8 inches and often allows the sofa to fit through doors. Some are held with bolts through the bottom frame — use a wrench.' },
      { num: '4', title: 'Attempt the door test before further disassembly', body: 'With legs removed and cushions off, try the doorway again. Many sofas that appear too large fit through standard 32-inch or 34-inch doorways when tilted vertically or at a diagonal angle.' },
      { num: '5', title: 'Remove the back (if detachable)', body: 'Some sofa designs have a detachable back cushion or back section. Check along the rear bottom for bolts or clips connecting the back frame to the seat frame. This alone can make a sofa fit through most doors.' },
      { num: '6', title: 'Full disassembly: cut the upholstery', body: 'If the couch needs to be fully broken down: use a sharp utility knife to cut the fabric along all seams. Pull the upholstery off the frame. Remove any staples with pliers. This is dusty, dirty work.' },
      { num: '7', title: 'Remove foam and padding', body: 'Foam sections compress significantly. Stuff foam into contractor bags. These can go in regular trash in small amounts or be dropped at foam recycling facilities.' },
      { num: '8', title: 'Break down the frame', body: 'Couch frames are typically plywood, particle board, or solid wood with metal spring assemblies. Use a reciprocating saw or hand saw to cut sections. Metal spring assemblies can go to scrap metal yards.' },
    ],
    relatedGuides: [
      { slug: 'how-to-dispose-of-a-couch', title: 'How to Dispose of a Couch' },
      { slug: 'what-to-do-with-old-furniture', title: 'What to Do with Old Furniture' },
      { slug: 'declutter-before-moving', title: 'Declutter Before Moving' },
      { slug: 'how-to-take-apart-a-bed-frame', title: 'How to Take Apart a Bed Frame' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'coral-springs-fl', name: 'Coral Springs' },
    ],
    disposalNote: 'After disassembly: bag foam for regular trash (small amounts), take metal frames to scrap yards, put wood sections out for curbside bulk pickup (scheduled), or call Umuve to haul the entire disassembled pile from $89. Umuve also handles the disassembly for you — often faster than DIY.',
  },
];

// ─── Lifestyle / Checklist Guides ────────────────────────────────────────────

const checklistGuides = [
  {
    slug: 'declutter-before-moving',
    title: 'How to Declutter Before Moving (Complete Guide)',
    metaDescription: 'Complete guide to decluttering before a move in South Florida. Room-by-room checklist, timeline, donation options, and Umuve junk removal for the big stuff.',
    h1: 'How to Declutter Before Moving: A Complete Guide',
    subtitle: 'Save money on your move and start fresh — room-by-room checklist for South Florida movers.',
    quickAnswer: 'Decluttering before a move reduces your moving cost by 20-40% by eliminating boxes you do not need to pack and transport. Start 4-6 weeks before move day. Work room-by-room using the keep/donate/trash method. Schedule Umuve for large item removal 1-2 weeks before move day so donated items leave the house before packing begins.',
    serviceSlug: 'estate-cleanout',
    serviceName: 'Estate Cleanout',
    isChecklist: true,
    timeline: [
      { when: '6 weeks before move', tasks: ['Start with storage areas: garage, attic, storage unit', 'Identify large furniture pieces that will NOT move with you', 'List items for Facebook Marketplace and list immediately', 'Call Habitat ReStore and Salvation Army to schedule large donation pickups'] },
      { when: '4 weeks before move', tasks: ['Tackle bedroom closets: anything not worn in 18 months goes', 'Clear under beds and in basements', 'Kitchen: purge duplicate tools, expired food, appliances not used in a year', 'Schedule Umuve for any large items: sofas, mattresses, appliances'] },
      { when: '2 weeks before move', tasks: ['Books, media, and decorative items: only keep what you love', 'Clear garage of tools and equipment you are not taking', 'Confirm donation pickups are scheduled', 'Confirm Umuve pickup date for large items'] },
      { when: '1 week before move', tasks: ['Final pass through every room', 'Move donated items to one staging area for easy pickup access', 'Dispose of hazardous items: paint at HHW, chemicals at county events', 'Run a Craigslist and Facebook check on any last-minute items'] },
      { when: 'Move day', tasks: ['Final sweep — anything remaining that is not going with you goes directly to Umuve or curbside (scheduled)', 'Do not let last-minute clutter delay your movers'] },
    ],
    roomRooms: [
      { room: 'Kitchen', tips: 'Appliances: only keep those used at least monthly. Dishes, pots, glasses — do you really need 4 sets? Tupperware: recycle mismatched or stained pieces. Junk drawer: dump it, keep the essentials.' },
      { room: 'Master Bedroom', tips: 'Clothes: 18-month rule. Mattresses and bed frames: if upgrading, schedule removal now, not moving day. Nightstands and dressers: sell what you can on Facebook Marketplace.' },
      { room: 'Living Room', tips: 'Sofas and sectionals: if they are worn or do not fit the new space, remove now. Entertainment centers, bookshelves, and TV stands often do not survive moves intact.' },
      { room: 'Garage', tips: 'The hardest room. Tools you have not used in 2 years: sell or donate. Sporting equipment: will you actually use it? Old car parts, paint cans, and chemicals: HHW disposal first.' },
      { room: 'Kids Rooms', tips: 'Broken toys go. Clothes and shoes get sized before packing. Furniture too small for the new space gets listed immediately.' },
    ],
    relatedGuides: [
      { slug: 'what-to-do-with-old-furniture', title: 'What to Do with Old Furniture' },
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
      { slug: 'move-out-cleaning-checklist', title: 'Move-Out Cleaning Checklist' },
      { slug: 'downsizing-tips', title: 'Downsizing Tips' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
  },
  {
    slug: 'declutter-for-spring-cleaning',
    title: 'Declutter for Spring Cleaning: Room-by-Room Guide',
    metaDescription: 'Complete spring cleaning declutter guide for South Florida homes. Room-by-room checklist, donation tips, and junk removal options.',
    h1: 'Declutter for Spring Cleaning: Room-by-Room Guide',
    subtitle: 'A practical spring cleaning declutter plan for South Florida homeowners.',
    quickAnswer: 'Spring cleaning in South Florida is most effective when it combines deep cleaning with purposeful decluttering. Work room-by-room over 1-3 weekends. Donate usable items to Habitat ReStore or Salvation Army. Schedule Umuve for large items you cannot donate. Use county HHW events (typically every April-May) for paint, chemicals, and electronics.',
    serviceSlug: 'garage-cleanout',
    serviceName: 'Garage Cleanout',
    isChecklist: true,
    timeline: [
      { when: 'Weekend 1: Main Living Areas', tasks: ['Living room: assess furniture for wear, sell or donate pieces no longer loved', 'Dining room: purge extra chairs and table leaves not used', 'Kitchen: appliances (if not used in 6 months, donate), expired pantry items, duplicate tools', 'Entryway: clear clutter accumulation zone, donate or trash'] },
      { when: 'Weekend 2: Bedrooms and Bathrooms', tasks: ['Clothes: try the 12-month rule for seasonal South Florida wear', 'Medicine cabinet: dispose of expired medications at pharmacy take-back', 'Linen closets: donate towels and sheets in good condition to animal shelters', 'Under beds: clear and organize or remove storage entirely'] },
      { when: 'Weekend 3: Garage, Storage, and Outdoor', tasks: ['Garage: the longest task. Set up 4 zones: keep, sell, donate, trash', 'Sports equipment: anything unused in 2 seasons', 'Holiday decorations: a South Florida honest assessment of what you actually set up', 'Outdoor furniture: assess condition, repair or replace, remove worn items'] },
    ],
    roomRooms: [
      { room: 'Garage', tips: 'Every garage cleanout in South Florida should start with removing: old paint (HHW), old tires (county events or Umuve), old appliances (scrap or Umuve), tools not used in 2+ years (sell or donate), holiday items not used in 2+ years.' },
      { room: 'Kitchen', tips: 'South Florida kitchens accumulate single-use appliances quickly. Juicers, bread makers, pasta machines — if unused in 6 months, donate to Goodwill or Habitat ReStore. Also: expired or stale pantry items, mismatched storage containers, duplicate cooking tools.' },
      { room: 'Bedrooms', tips: 'The 12-month rule works well in South Florida because the seasons are minimal. If you have not worn something in a year, it is going.' },
    ],
    relatedGuides: [
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
      { slug: 'declutter-before-moving', title: 'Declutter Before Moving' },
      { slug: 'what-to-do-with-old-furniture', title: 'What to Do with Old Furniture' },
      { slug: 'downsizing-tips', title: 'Downsizing Tips' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'coral-springs-fl', name: 'Coral Springs' },
    ],
  },
  {
    slug: 'what-to-do-with-old-furniture',
    title: 'What to Do with Old Furniture in South Florida',
    metaDescription: 'What to do with old furniture in South Florida — sell, donate, recycle, or remove. Best options for couches, mattresses, dressers, and more.',
    h1: 'What to Do with Old Furniture in South Florida',
    subtitle: 'Sell, donate, recycle, or remove old furniture — the best options by condition and type.',
    quickAnswer: 'Old furniture in South Florida has four paths: sell it (Facebook Marketplace and Craigslist are active in this market), donate it (Habitat for Humanity ReStore, Salvation Army, Goodwill), recycle materials at certified facilities, or call Umuve for professional removal starting at $89. The right choice depends on the item\'s condition and how quickly you need it gone.',
    serviceSlug: 'furniture-removal',
    serviceName: 'Furniture Removal',
    isChecklist: true,
    timeline: [
      { when: 'Step 1: Assess Condition', tasks: ['Excellent condition (like new): sell first on Facebook Marketplace or Craigslist', 'Good condition (minor wear): donate to Habitat ReStore, Salvation Army, or Goodwill', 'Fair condition (stains, light damage): Facebook Marketplace at low price or free', 'Poor condition (structural damage, major staining): professional removal or curbside'] },
      { when: 'Step 2: Try to Sell (1 week)', tasks: ['List on Facebook Marketplace first — South Florida\'s most active used furniture market', 'Price fairly: a couch that cost $800 new is worth $100-$300 used in good condition', 'Post clear photos in natural light with accurate description', 'Be responsive — buyers move fast in this market'] },
      { when: 'Step 3: Donate (if not sold in 7 days)', tasks: ['Habitat for Humanity ReStore: call your local location first to confirm acceptance', 'Salvation Army: call (800) 728-7825 for free large furniture pickup in many areas', 'Goodwill: most accept furniture in excellent condition; call ahead for large items', 'Local community Facebook groups and Buy Nothing groups'] },
      { when: 'Step 4: Remove (if not donated)', tasks: ['Schedule Umuve for same-day or next-day pickup', 'County curbside: schedule first, items go out the morning of pickup', 'Umuve donates items in good condition on your behalf before hauling anything to recycling'] },
    ],
    roomRooms: [
      { room: 'Sofas and Sectionals', tips: 'South Florida\'s active Facebook Marketplace means quality sectionals sell quickly. Price at 20-30% of retail for good condition. If donating, Salvation Army pickup is the easiest option. Umuve removes same-day with 90% donation or recycling rate.' },
      { room: 'Mattresses', tips: 'Mattresses cannot be donated if they have any stains. If yours is clean and under 5 years old, Habitat ReStore may accept it. Otherwise, professional removal at $89-$199 routes it to certified mattress recyclers.' },
      { room: 'Dressers and Bedroom Furniture', tips: 'Solid wood dressers sell extremely well in South Florida — $75-$300 for quality pieces. IKEA and flat-pack furniture has lower resale value but is accepted at Goodwill. Paint or refinish before listing to increase sale price significantly.' },
    ],
    relatedGuides: [
      { slug: 'how-to-dispose-of-a-couch', title: 'How to Dispose of a Couch' },
      { slug: 'how-to-dispose-of-a-mattress', title: 'How to Dispose of a Mattress' },
      { slug: 'declutter-before-moving', title: 'Declutter Before Moving' },
      { slug: 'estate-cleanout-checklist', title: 'Estate Cleanout Checklist' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
  },
  {
    slug: 'garage-cleanout-guide',
    title: 'Garage Cleanout Guide: How to Clear Your Garage in One Weekend',
    metaDescription: 'Complete garage cleanout guide for South Florida homeowners. Step-by-step plan, what to keep/donate/toss, hazardous material disposal, and professional cleanout pricing.',
    h1: 'Garage Cleanout Guide: Clear Your Garage in One Weekend',
    subtitle: 'A practical, room-by-room garage cleanout plan for South Florida homes.',
    quickAnswer: 'A full garage cleanout takes one to two weekends for most South Florida homes. Professional garage cleanout by Umuve starts at $149 and takes 2-4 hours — we handle all sorting, loading, and disposal so you do not have to. DIY cleanouts require sorting into keep/donate/trash zones, scheduling HHW events for paint and chemicals, and either hauling or booking Umuve for the large items.',
    serviceSlug: 'garage-cleanout',
    serviceName: 'Garage Cleanout',
    isChecklist: true,
    timeline: [
      { when: 'Before You Start', tasks: ['Set up 4 zones in your driveway: KEEP, SELL/DONATE, TRASH, HAZARDOUS', 'Schedule a county HHW event for paint, chemicals, tires, and electronics', 'Book Umuve for the end of cleanout day (or day after) for large items', 'Get boxes, contractor bags, and labels ready'] },
      { when: 'Morning: Empty and Sort', tasks: ['Move everything out of the garage onto the driveway', 'Touch every item once — make a decision immediately', 'Tools you have not used in 2 years: sell or donate', 'Sports equipment: if it has not been used in a season, donate'] },
      { when: 'Afternoon: Process Each Zone', tasks: ['SELL/DONATE: photograph and post on Facebook Marketplace during the break, or load for Habitat/Goodwill', 'TRASH: fill contractor bags; call Umuve for large items or haul to transfer station', 'HAZARDOUS: stage safely for HHW event (paint, chemicals, old batteries)', 'KEEP: bring back in with intention — no more "just in case" storage'] },
      { when: 'Final: Organize the Keep Zone', tasks: ['Install wall-mounted shelving if budget allows ($50-$200 at Home Depot)', 'Bike hooks and overhead storage systems maximize vertical space', 'Label all storage bins', 'Leave a clear path to the car — every time'] },
    ],
    roomRooms: [
      { room: 'What to Always Dispose Of', tips: 'Old paint cans (HHW event or PaintCare), old tires (county event), old appliances (Umuve or scrap metal), expired chemicals and pesticides (HHW), electronic waste (county event or Umuve), boxes of random junk not accessed in 2+ years.' },
      { room: 'What to Always Sell', tips: 'Power tools in working condition ($20-$200 each on Facebook), sporting equipment ($10-$100), name-brand storage systems, outdoor furniture in good shape, working appliances.' },
      { room: 'What Umuve Handles Best', tips: 'Old refrigerators, washing machines, and appliances. Broken or worn furniture. Boxes of unsortable mixed junk. Old mattresses. Renovation debris. When you have a full garage of mixed items, Umuve\'s flat-rate pricing beats the math of multiple trips and disposal fees.' },
    ],
    relatedGuides: [
      { slug: 'declutter-for-spring-cleaning', title: 'Declutter for Spring Cleaning' },
      { slug: 'how-to-dispose-of-paint', title: 'How to Dispose of Old Paint' },
      { slug: 'how-to-dispose-of-appliances', title: 'How to Dispose of Appliances' },
      { slug: 'declutter-before-moving', title: 'Declutter Before Moving' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
  },
  {
    slug: 'estate-cleanout-checklist',
    title: 'Estate Cleanout Checklist: Complete Guide for South Florida',
    metaDescription: 'Estate cleanout checklist for South Florida. Step-by-step guide for clearing a home after a death, divorce, or sale. Donation, disposal, and professional cleanout options.',
    h1: 'Estate Cleanout Checklist: Complete Guide',
    subtitle: 'A compassionate, practical checklist for clearing an estate in South Florida.',
    quickAnswer: 'Estate cleanouts in South Florida cost $399-$3,500 professionally depending on home size. DIY cleanouts take 1-4 weekends with a full family team. Start with valuables and documents, then work room by room. Donate usable items before scheduling removal. Umuve handles the full estate cleanout with compassion and 84% donation or recycling rate.',
    serviceSlug: 'estate-cleanout',
    serviceName: 'Estate Cleanout',
    isChecklist: true,
    timeline: [
      { when: 'Week 1: Secure and Document', tasks: ['Locate and secure all financial documents, jewelry, and valuables', 'Change locks if property was unoccupied', 'Photograph every room for insurance and estate records', 'Identify and set aside items designated in the will or that family wants', 'Check for safe deposit box keys, storage unit keys, vehicle titles'] },
      { when: 'Week 2: Family Sorting', tasks: ['Gather family members for a sorting day — agreement upfront prevents conflict', 'Divide into rooms and assign family members to make decisions', 'Box or tag items each person wants to keep', 'Identify high-value items for appraisal (antiques, art, jewelry, collections)', 'Contact an estate sale company if large quantity of sellable items exists'] },
      { when: 'Week 3: Donation and Sales', tasks: ['Schedule Salvation Army or Habitat for Humanity for furniture pickup', 'List sellable items on Facebook Marketplace or with an estate sale service', 'Drop off clothing and smaller items at Goodwill', 'Bank charity donation receipts for tax purposes'] },
      { when: 'Week 4: Professional Cleanout', tasks: ['Book Umuve for full cleanout of remaining items', 'Professional cleanout team sorts, loads, and disposes in one visit', 'Schedule cleaning crew after Umuve finishes', 'Final walk-through for any overlooked items'] },
    ],
    roomRooms: [
      { room: 'Documents and Valuables', tips: 'Before anything else: locate birth certificates, social security cards, wills, deeds, vehicle titles, insurance policies, financial statements, and jewelry. These can be in drawers, safe deposit boxes, storage units, or hidden in closets. Do not let document search happen concurrently with physical cleanout.' },
      { room: 'Kitchen', tips: 'Small appliances in working condition to Habitat ReStore. Quality cookware to Goodwill. Pantry: most food banks accept unopened non-perishables. Medications: pharmacy take-back or DEA National Rx Take-Back.' },
      { room: 'Garage and Storage', tips: 'Tools and equipment: estate sale or Facebook Marketplace. Old paint, chemicals: HHW event. Old appliances: Umuve or scrap metal. Vehicles: Florida DMV title transfer process.' },
    ],
    relatedGuides: [
      { slug: 'hoarder-cleanout-guide', title: 'Hoarder Cleanout Guide' },
      { slug: 'what-to-do-with-old-furniture', title: 'What to Do with Old Furniture' },
      { slug: 'storage-unit-cleanout-guide', title: 'Storage Unit Cleanout Guide' },
      { slug: 'downsizing-tips', title: 'Downsizing Tips' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
  },
  {
    slug: 'move-out-cleaning-checklist',
    title: 'Move-Out Cleaning Checklist for South Florida Renters and Sellers',
    metaDescription: 'Complete move-out cleaning checklist for South Florida. Get your deposit back, pass inspection, and leave your home spotless. Junk removal tips included.',
    h1: 'Move-Out Cleaning Checklist for South Florida',
    subtitle: 'Get your deposit back and pass inspection with this complete South Florida move-out guide.',
    quickAnswer: 'South Florida landlords and buyers have high standards for move-out condition. Start junk removal 2 weeks before move-out — do not leave it for the last day. Umuve handles large item removal so cleaning crews can work on an empty space. Use this room-by-room checklist to ensure deposit return and sale readiness.',
    serviceSlug: 'estate-cleanout',
    serviceName: 'Estate Cleanout',
    isChecklist: true,
    timeline: [
      { when: '2 Weeks Before Move-Out: Remove Everything', tasks: ['Book Umuve for any items not moving with you', 'Schedule county bulk pickup for large items that do not need professional removal', 'Clear garage, storage areas, and patio', 'Remove all wall hangings and patch nail holes'] },
      { when: '1 Week Before: Deep Cleaning Begins', tasks: ['Appliances: clean oven inside and out, clean refrigerator shelves, wipe dishwasher interior', 'Bathrooms: remove all personal items, scrub grout, clean behind toilet', 'Blinds and window tracks: South Florida dust accumulates fast', 'Ceiling fans: landlords check these in Florida'] },
      { when: 'Final 48 Hours', tasks: ['Steam clean carpets if present (required by most leases)', 'Final mop of all hard floors', 'Wipe all baseboards and door frames', 'Final exterior cleanup: pressure wash driveway if needed, clear patio', 'Document condition with photos before handing over keys'] },
    ],
    roomRooms: [
      { room: 'Kitchen', tips: 'Clean the inside of the oven with oven cleaner (leave overnight if needed). Clean refrigerator shelves and drawers. Wipe down all cabinet interiors. Clean the garbage disposal with ice and salt. Degrease the hood vent filter.' },
      { room: 'Bathrooms', tips: 'Grout lines, caulk condition, toilet base, and inside of drain covers are the spots South Florida landlords most often cite. Use a grout brush and bleach solution. Remove all silicone caulk that has turned pink (common in humid Florida) and regrout before inspection.' },
      { room: 'South Florida Specific', tips: 'Mold and mildew are common in South Florida\'s humidity. Check behind appliances, under sinks, and in bathroom ceiling corners. Clean or disclose any mold you find — hiding it costs you the deposit plus potential liability. AC filter replacement is also typically required.' },
    ],
    relatedGuides: [
      { slug: 'declutter-before-moving', title: 'Declutter Before Moving' },
      { slug: 'what-to-do-with-old-furniture', title: 'What to Do with Old Furniture' },
      { slug: 'estate-cleanout-checklist', title: 'Estate Cleanout Checklist' },
      { slug: 'downsizing-tips', title: 'Downsizing Tips' },
    ],
    cityLinks: [
      { city: 'miami-fl', name: 'Miami' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
  },
  {
    slug: 'renovation-debris-disposal-guide',
    title: 'Renovation Debris Disposal Guide for South Florida',
    metaDescription: 'How to dispose of renovation debris in South Florida. C&D waste rules, dumpster vs professional removal, costs per yard, and same-day hauling options.',
    h1: 'Renovation Debris Disposal Guide',
    subtitle: 'From drywall to concrete to tile — disposing of renovation waste in South Florida properly.',
    quickAnswer: 'Renovation debris is classified as Construction and Demolition (C&D) waste in South Florida and cannot go in regular curbside trash. Options: roll-off dumpster rental ($250-$600), professional same-day hauling by Umuve starting at $149, or county C&D transfer station drop-off. Planning your debris disposal before demolition begins prevents costly project delays.',
    serviceSlug: 'construction-debris',
    serviceName: 'Construction Debris',
    isChecklist: true,
    timeline: [
      { when: 'Before Demolition: Plan Your Disposal', tasks: ['Determine debris types: drywall, concrete, wood, tile, fixtures', 'Test for asbestos if home is pre-1980 (call certified inspector)', 'Decide: dumpster (multi-day project) vs professional removal (single-day)', 'Book Umuve if single-day or intermittent cleanouts work better', 'Verify your city\'s permit requirements for the renovation'] },
      { when: 'During Renovation: Separate By Type', tasks: ['Keep concrete separate from mixed debris (concrete recyclers often accept free)', 'Keep clean drywall separate (gypsum recyclers accept clean drywall free)', 'Keep metal separately (highest scrap value, often free to dispose)', 'Mixed debris goes in the dumpster or to Umuve'] },
      { when: 'Post-Renovation: Final Cleanout', tasks: ['Sweep and collect all fine debris before vacuuming', 'Book Umuve for final haul if dumpster is gone', 'Arrange transfer station drop-off for remaining material if self-hauling', 'Document the clean state for permit close-out if required'] },
    ],
    roomRooms: [
      { room: 'Drywall', tips: 'Clean, unpainted drywall to gypsum recyclers (often free). Mixed or painted drywall to C&D transfer station or Umuve. Never put drywall in regular trash — it is prohibited in all three South Florida counties.' },
      { room: 'Concrete', tips: 'Clean concrete (no mixed debris) to concrete recyclers (often free). Rebar-reinforced concrete to C&D recyclers that have appropriate crushers. Heavy — weigh options carefully before choosing a dumpster.' },
      { room: 'Tile, Cabinets, and Fixtures', tips: 'Salvageable cabinets and fixtures to Habitat ReStore. Broken tile to C&D facility. Porcelain fixtures (toilets, sinks) to county curbside or Umuve. Metal fixtures to scrap yard.' },
    ],
    relatedGuides: [
      { slug: 'how-to-dispose-of-concrete', title: 'How to Dispose of Concrete' },
      { slug: 'how-to-dispose-of-drywall', title: 'How to Dispose of Drywall' },
      { slug: 'how-to-remove-a-toilet', title: 'How to Remove a Toilet' },
      { slug: 'how-to-remove-a-kitchen-sink', title: 'How to Remove a Kitchen Sink' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'doral-fl', name: 'Doral' },
    ],
  },
  {
    slug: 'hoarder-cleanout-guide',
    title: 'Hoarder Cleanout Guide: How to Clear a Hoarding Situation in South Florida',
    metaDescription: 'Compassionate guide to hoarder cleanouts in South Florida. Step-by-step plan, professional cleanout costs, mental health support resources, and what to expect.',
    h1: 'Hoarder Cleanout Guide: A Compassionate Approach',
    subtitle: 'Practical, respectful guidance for clearing hoarding situations in South Florida homes.',
    quickAnswer: 'Hoarding cleanouts are among the most complex and emotionally sensitive junk removal projects. Professional hoarding cleanouts by Umuve cost $399-$3,500 depending on home size and severity. The most successful cleanouts involve the person who lives there in the process, have realistic timelines (days to weeks, not hours), and use a professional team experienced with these situations.',
    serviceSlug: 'estate-cleanout',
    serviceName: 'Estate Cleanout',
    isChecklist: true,
    timeline: [
      { when: 'Phase 1: Assessment and Consent', tasks: ['If the person is still living there, involve them in the decision and process from the start', 'Walk through and document the scope with photos', 'Identify biohazard concerns: rodent droppings, mold, spoiled food, waste', 'Contact a professional biohazard cleaner if needed before junk removal', 'Set realistic expectations: hoarding cleanouts typically take days, not hours'] },
      { when: 'Phase 2: Category System', tasks: ['Work with a system the person can understand and participate in', 'Never throw away an item without the resident\'s awareness if they are present', 'Keep: things with real value or emotional significance', 'Donate: usable items the person is willing to part with', 'Remove: items that are damaged, expired, or have no use value'] },
      { when: 'Phase 3: Professional Removal', tasks: ['Book Umuve for the removal phase — compassionate, non-judgmental crews', 'Work room by room from the most functional space outward', 'Maintain clear paths at all times for safety', 'Schedule removal in stages if the person needs time between sessions'] },
      { when: 'Phase 4: Support', tasks: ['Connect with the South Florida chapter of NAMI (National Alliance on Mental Illness)', 'Therapists specializing in hoarding disorder in Palm Beach, Broward, and Miami-Dade', 'Build in maintenance visits to prevent recurrence', 'Consider support from hoarding disorder specialists at Memorial Healthcare in Broward'] },
    ],
    roomRooms: [
      { room: 'What to Know About Hoarding Cleanouts', tips: 'Hoarding disorder is a recognized mental health condition (DSM-5). It is not a character flaw or laziness. The most sustainable cleanouts address the underlying condition alongside the physical work. Forced cleanouts without the person\'s participation have a very high recurrence rate.' },
      { room: 'When Professional Help Is Needed', tips: 'Hoarding cleanouts with biohazards (animal waste, rotting materials, pest infestations) require a licensed biohazard remediation company before junk removal begins. Umuve does not work in active biohazard conditions but can follow immediately after remediation.' },
      { room: 'Cost Expectations', tips: 'A Level 1-2 hoarding situation (cluttered but accessible): $399-$899. Level 3 (pathways only, multiple rooms blocked): $899-$1,800. Level 4-5 (severe, structural concerns, multiple crews): $1,800-$3,500+. Cost includes multiple truckloads and extended crew time.' },
    ],
    relatedGuides: [
      { slug: 'estate-cleanout-checklist', title: 'Estate Cleanout Checklist' },
      { slug: 'storage-unit-cleanout-guide', title: 'Storage Unit Cleanout Guide' },
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
      { slug: 'downsizing-tips', title: 'Downsizing Tips' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'hollywood-fl', name: 'Hollywood' },
    ],
  },
  {
    slug: 'storage-unit-cleanout-guide',
    title: 'Storage Unit Cleanout Guide: How to Clear Your Unit Fast',
    metaDescription: 'Complete guide to clearing a storage unit in South Florida. Step-by-step plan, what to do with the contents, and professional cleanout services.',
    h1: 'Storage Unit Cleanout Guide',
    subtitle: 'Clear your storage unit efficiently — sell, donate, and remove in one organized process.',
    quickAnswer: 'Most storage units can be cleared in one to two days with a plan. Sort into sell, donate, and remove piles. List sellable items on Facebook Marketplace immediately — many units contain items worth $200-$1,000 total. Book Umuve to haul the remainder from $149. Clearing a unit on time prevents lien and auction proceedings that many South Florida storage operators use after 30 days of non-payment.',
    serviceSlug: 'estate-cleanout',
    serviceName: 'Estate Cleanout',
    isChecklist: true,
    timeline: [
      { when: 'Before You Arrive: Plan', tasks: ['Bring boxes, bags, markers, and labels', 'Arrange a truck or van if keeping items (or book movers)', 'Schedule Umuve for the day of clearing', 'Contact a consignment shop or estate sale company if high-value items are expected', 'Bring a friend — sorting alone is slow and exhausting'] },
      { when: 'Day of Cleanout: Sort First, Load Second', tasks: ['Move everything to the unit entrance or outside', 'Create 4 zones: KEEP, SELL/DONATE, TRASH/REMOVE, UNSURE', 'Touch every item once — quick decisions', 'Photograph sellable items immediately and post to Facebook Marketplace', 'Load trash/remove items for Umuve pickup or truck haul'] },
      { when: 'After Clearing: Follow-Through', tasks: ['Return keys to storage facility and get written confirmation of unit closure', 'Get written cancellation confirmation to prevent continued billing', 'Complete Facebook Marketplace transactions within 48 hours of posting', 'Confirm Goodwill or Habitat donation drop-off'] },
    ],
    roomRooms: [
      { room: 'What Typically Has Value', tips: 'Power tools and hand tools (sell on Facebook Marketplace), furniture in good condition, name-brand electronics, musical instruments, sporting equipment, collectibles and antiques (have them appraised before pricing), art (same), jewelry (pawn shop or estate jeweler appraisal first).' },
      { room: 'What to Donate', tips: 'Books (Better World Books, local library Friends groups), clothes (Goodwill, Salvation Army, clothing banks), kitchenware in good condition (Habitat ReStore), working small appliances (Goodwill).' },
      { room: 'What to Remove', tips: 'Broken furniture, water-damaged items, old mattresses, old appliances, boxes of mixed unsortable items. Umuve handles all of this in one pickup. If you have 1/4 truckload or more of junk to remove, professional pickup is faster and cheaper than multiple trips.' },
    ],
    relatedGuides: [
      { slug: 'estate-cleanout-checklist', title: 'Estate Cleanout Checklist' },
      { slug: 'hoarder-cleanout-guide', title: 'Hoarder Cleanout Guide' },
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
      { slug: 'downsizing-tips', title: 'Downsizing Tips' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
  },
  {
    slug: 'downsizing-tips',
    title: 'Downsizing Tips: How to Downsize Your Home in South Florida',
    metaDescription: 'Practical downsizing tips for South Florida homeowners. Room-by-room guide, what to sell vs donate, emotional aspects of downsizing, and junk removal help.',
    h1: 'Downsizing Tips: How to Downsize Your South Florida Home',
    subtitle: 'A practical and thoughtful guide to right-sizing your home and belongings in South Florida.',
    quickAnswer: 'Downsizing is most successful as a 60-90 day process — not a weekend project. Start with the garage and storage areas (lowest emotional load), finish with sentimental spaces. Sell quality items on Facebook Marketplace first, donate what does not sell, and call Umuve for everything that remains. The goal is not minimalism — it is intentionality.',
    serviceSlug: 'estate-cleanout',
    serviceName: 'Estate Cleanout',
    isChecklist: true,
    timeline: [
      { when: 'Months 1-2: Low-Emotion Areas First', tasks: ['Garage, shed, and outdoor storage', 'Duplicate kitchen items', 'Books and media', 'Clothes not worn in 12 months', 'Holiday decorations you no longer use'] },
      { when: 'Month 3: High-Emotion Areas', tasks: ['Sentimental items: photos, keepsakes, family heirlooms', 'Involve family in decisions before this phase to prevent conflict', 'Large furniture: photograph and measure before deciding what fits in the new space', 'Collections: sell, donate, or pass to family members who will value them'] },
      { when: 'Final Month: Remove and Clean', tasks: ['Book Umuve for all items not sold or donated', 'Schedule county bulk pickup for remaining large items', 'Donate remaining items to Habitat for Humanity, Goodwill, Salvation Army', 'Final deep clean of vacated spaces'] },
    ],
    roomRooms: [
      { room: 'The Mindset That Works', tips: 'Downsizing is not about loss — it is about keeping what you love and use. Ask for each item: Do I love this? Do I use this? Does someone else need this more? Items that pass all three questions stay. The rest finds a better home.' },
      { room: 'South Florida Specific Considerations', tips: 'Outdoor furniture and equipment: the South Florida market for quality patio furniture is strong. Boat and fishing gear: high local value. Winter clothing: donate to northern charities or shelters in other states. AC equipment and fans: high local demand, sell rather than discard.' },
      { room: 'Getting the Family Involved', tips: 'If downsizing involves a parent or family member, treat sentimental items with deep respect. Photograph items before donating to preserve the memory without the physical burden. Consider a "memory box" for each family member — a small curated collection of irreplaceable items from the family home.' },
    ],
    relatedGuides: [
      { slug: 'estate-cleanout-checklist', title: 'Estate Cleanout Checklist' },
      { slug: 'declutter-before-moving', title: 'Declutter Before Moving' },
      { slug: 'what-to-do-with-old-furniture', title: 'What to Do with Old Furniture' },
      { slug: 'garage-cleanout-guide', title: 'Garage Cleanout Guide' },
    ],
    cityLinks: [
      { city: 'west-palm-beach-fl', name: 'West Palm Beach' },
      { city: 'fort-lauderdale-fl', name: 'Fort Lauderdale' },
      { city: 'miami-fl', name: 'Miami' },
      { city: 'boca-raton-fl', name: 'Boca Raton' },
    ],
  },
];

// ─── All guides combined ──────────────────────────────────────────────────────

const allGuides = [...guides, ...lifestyleGuides, ...diyGuides, ...checklistGuides];

// ─── HTML Template Helpers ───────────────────────────────────────────────────

function head(g) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="${g.metaDescription}">
    <meta name="robots" content="index, follow">

    <!-- Open Graph -->
    <meta property="og:type" content="article">
    <meta property="og:url" content="${SITE}/guides/${g.slug}">
    <meta property="og:title" content="${g.title} | Umuve">
    <meta property="og:description" content="${g.metaDescription}">
    <meta property="og:image" content="${SITE}/logo-full.png">
    <meta property="og:site_name" content="Umuve">

    <!-- Twitter -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="${g.title}">
    <meta name="twitter:description" content="${g.metaDescription}">

    <!-- Canonical -->
    <link rel="canonical" href="${SITE}/guides/${g.slug}">

    <title>${g.title} | Umuve</title>

    <link rel="stylesheet" href="/styles.css">
    <link rel="stylesheet" href="/styles-seo.css">
    <link rel="icon" type="image/png" href="/logo-icon.png">

    <!-- Google Analytics -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=${GA4}"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', '${GA4}');
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
        fbq('init', '${PIXEL}');
        fbq('track', 'PageView');
    </script>
    <noscript><img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id=${PIXEL}&ev=PageView&noscript=1" alt="Facebook Pixel"></noscript>

    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@700;800;900&display=swap" rel="stylesheet">

    <!-- Structured Data - Article -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "${g.title}",
        "description": "${g.metaDescription}",
        "author": {"@type": "Organization", "name": "Umuve", "url": "${SITE}"},
        "publisher": {"@type": "Organization", "name": "Umuve", "logo": {"@type": "ImageObject", "url": "${SITE}/logo-full.png"}},
        "datePublished": "${DATE_ISO}",
        "dateModified": "${DATE_ISO}",
        "mainEntityOfPage": "${SITE}/guides/${g.slug}",
        "image": "${SITE}/logo-full.png"
    }
    </script>

    <!-- Structured Data - Breadcrumb -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "${SITE}"},
            {"@type": "ListItem", "position": 2, "name": "Guides", "item": "${SITE}/guides"},
            {"@type": "ListItem", "position": 3, "name": "${g.h1}", "item": "${SITE}/guides/${g.slug}"}
        ]
    }
    </script>${g.faqs ? faqSchema(g.faqs) : ''}

    <style>
        .guide-table { width: 100%; border-collapse: collapse; border-radius: 0.75rem; overflow: hidden; border: 1px solid rgba(0,0,0,0.08); margin-bottom: 2rem; }
        .guide-table th { background: #f9fafb; font-weight: 700; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.03em; color: #5c5c5c; padding: 0.85rem 1rem; text-align: left; border-bottom: 1px solid rgba(0,0,0,0.08); }
        .guide-table td { padding: 0.75rem 1rem; border-bottom: 1px solid rgba(0,0,0,0.04); font-size: 0.95rem; }
        .guide-table tbody tr:hover { background: #fafafa; }
        .guide-table tbody tr:last-child td { border-bottom: none; }
        .toc-link { display: block; padding: 0.4rem 0; color: #DC2626; text-decoration: none; font-size: 0.95rem; }
        .toc-link:hover { text-decoration: underline; }
        .option-card { background: white; border: 1px solid rgba(0,0,0,0.07); border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; }
        .option-card h3 { font-size: 1.2rem; font-weight: 700; margin-bottom: 0.75rem; }
        .county-block { background: #f9fafb; border-radius: 0.5rem; padding: 1rem 1.25rem; margin-bottom: 0.75rem; border-left: 3px solid #DC2626; }
        .county-block strong { display: block; margin-bottom: 0.25rem; font-size: 0.9rem; color: #DC2626; }
        .county-block p { color: #5c5c5c; line-height: 1.6; font-size: 0.9rem; margin: 0; }
        .mistake-card { padding: 1.25rem 1.5rem; background: #FFF7F7; border-radius: 0.75rem; border-left: 4px solid #DC2626; margin-bottom: 1rem; }
        .mistake-card strong { display: block; margin-bottom: 0.25rem; font-size: 1rem; }
        .mistake-card p { color: #5c5c5c; line-height: 1.6; font-size: 0.95rem; margin: 0; }
        .faq-item { border: 1px solid rgba(0,0,0,0.07); border-radius: 0.75rem; margin-bottom: 0.75rem; overflow: hidden; }
        .faq-q { padding: 1rem 1.25rem; font-weight: 600; cursor: pointer; display: flex; justify-content: space-between; align-items: center; background: #fafafa; }
        .faq-q:hover { background: #f3f4f6; }
        .faq-a { padding: 0 1.25rem 1rem; color: #5c5c5c; line-height: 1.7; display: none; }
        .faq-a.open { display: block; }
        .step-card { display: flex; gap: 1rem; margin-bottom: 1.5rem; }
        .step-num { flex-shrink: 0; width: 2.5rem; height: 2.5rem; background: #DC2626; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.1rem; }
        .step-content h3 { font-size: 1.05rem; font-weight: 700; margin-bottom: 0.4rem; }
        .step-content p { color: #5c5c5c; line-height: 1.65; font-size: 0.95rem; margin: 0; }
        .phase-card { background: white; border: 1px solid rgba(0,0,0,0.07); border-radius: 0.75rem; padding: 1.25rem 1.5rem; margin-bottom: 1rem; }
        .phase-card h3 { font-size: 1rem; font-weight: 700; color: #DC2626; margin-bottom: 0.5rem; }
        .phase-card ul { padding-left: 1.25rem; margin: 0; }
        .phase-card ul li { padding: 0.2rem 0; color: #5c5c5c; line-height: 1.6; font-size: 0.95rem; }
        .tip-card { background: #f9fafb; border-radius: 0.5rem; padding: 1rem 1.25rem; margin-bottom: 0.75rem; }
        .tip-card strong { display: block; font-size: 0.9rem; color: #1a1a1a; margin-bottom: 0.25rem; }
        .tip-card p { color: #5c5c5c; line-height: 1.6; font-size: 0.9rem; margin: 0; }
        .sticky-cta { position: fixed; bottom: 0; left: 0; right: 0; background: #DC2626; color: white; padding: 1rem; display: flex; justify-content: center; align-items: center; gap: 1rem; z-index: 200; }
        .sticky-cta a { color: white; font-weight: 700; text-decoration: none; }
        @media (max-width: 768px) {
            .guide-table { font-size: 0.85rem; }
            .guide-table th, .guide-table td { padding: 0.5rem 0.5rem; }
        }
    </style>
</head>`;
}

function faqSchema(faqs) {
  return `
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [${faqs.map(f => `
            {"@type": "Question", "name": "${f.q.replace(/"/g, '&quot;')}", "acceptedAnswer": {"@type": "Answer", "text": "${f.a.replace(/"/g, '&quot;')}"}}`).join(',')}
        ]
    }
    </script>`;
}

function nav() {
  return `
    <!-- Nav -->
    <nav style="position: sticky; top: 0; background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); z-index: 100; border-bottom: 1px solid rgba(0,0,0,0.06);">
        <div class="container">
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem 0;">
                <a href="/" style="display: flex; align-items: center; text-decoration: none;">
                    <img src="/logo-nav.png" alt="Umuve — Same-Day Junk Removal in South Florida" width="120" height="36" loading="eager">
                </a>
                <div style="display: flex; gap: 0.75rem; align-items: center;">
                    <a href="tel:+15619441636" style="color: #1a1a1a; text-decoration: none; font-weight: 600; font-size: 0.9rem;">${PHONE}</a>
                    <a href="${BOOK_URL}" class="btn btn-primary" style="padding: 0.6rem 1.25rem; font-size: 0.9rem;">Book Now</a>
                </div>
            </div>
        </div>
    </nav>`;
}

function breadcrumb(g) {
  return `
    <!-- Breadcrumb -->
    <div style="background: #f9fafb; padding: 0.75rem 0; border-bottom: 1px solid rgba(0,0,0,0.04);">
        <div class="container">
            <nav style="font-size: 0.85rem; color: #8a8a8a;">
                <a href="/" style="color: #5c5c5c; text-decoration: none;">Home</a>
                <span style="margin: 0 0.5rem;">&rsaquo;</span>
                <a href="/guides/junk-removal-cost-south-florida" style="color: #5c5c5c; text-decoration: none;">Guides</a>
                <span style="margin: 0 0.5rem;">&rsaquo;</span>
                <span style="color: #1a1a1a; font-weight: 500;">${g.h1}</span>
            </nav>
        </div>
    </div>`;
}

function hero(g) {
  return `
    <!-- Hero -->
    <section style="padding: 3rem 0 2rem; background: linear-gradient(135deg, #f9fafb 0%, #ffffff 100%);">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <p style="font-size: 0.85rem; color: #8a8a8a; margin-bottom: 0.5rem;">Last updated ${DATE}</p>
                <h1 style="font-family: Outfit, sans-serif; font-size: clamp(1.75rem, 4.5vw, 2.5rem); font-weight: 800; margin-bottom: 1rem; line-height: 1.2;">
                    ${g.h1}
                </h1>
                <p style="font-size: 1.05rem; color: #5c5c5c; margin-bottom: 1.5rem; line-height: 1.7;">
                    ${g.subtitle}
                </p>
                <div style="background: #EFF6FF; border: 2px solid #3B82F6; border-radius: 0.75rem; padding: 1.5rem; margin: 0 0 1.5rem;">
                    <p style="font-weight: 700; font-size: 1.05rem; margin-bottom: 0.5rem;">Quick Answer</p>
                    <p style="color: #1e3a5f; line-height: 1.7; margin: 0;">${g.quickAnswer}</p>
                </div>
                <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                    <a href="${BOOK_URL}" class="btn btn-primary">Book Free Pickup</a>
                    <a href="tel:+15619441636" class="btn btn-secondary">Call ${PHONE}</a>
                </div>
            </div>
        </div>
    </section>`;
}

function tocBlock(toc) {
  if (!toc || !toc.length) return '';
  return `
    <!-- Table of Contents -->
    <section style="padding: 2rem 0 0;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto; padding: 1.5rem 2rem; background: #f9fafb; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.06);">
                <h2 style="font-size: 1.05rem; font-weight: 700; margin-bottom: 0.75rem;">In This Guide</h2>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0 1.5rem;">
                    ${toc.map((t, i) => `<a href="#${t.id}" class="toc-link">${i + 1}. ${t.label}</a>`).join('')}
                </div>
            </div>
        </div>
    </section>`;
}

function optionProfessional(g) {
  if (!g.professional) return '';
  return `
    <!-- Option 1: Professional -->
    <section id="professional" style="padding: 3rem 0;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 0.5rem;">Option 1: Professional Removal by Umuve</h2>
                <p style="color: #5c5c5c; margin-bottom: 1.5rem; font-size: 1rem;">The fastest option — starting at ${g.professional.price}.</p>
                <div class="option-card">
                    <p style="line-height: 1.7; color: #3a3a3a; margin-bottom: 1.25rem;">${g.professional.description}</p>
                    <h4 style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: #5c5c5c; margin-bottom: 0.75rem;">What is Included</h4>
                    <ul style="padding-left: 1.25rem; margin-bottom: 1.5rem;">
                        ${g.professional.includes.map(i => `<li style="padding: 0.25rem 0; color: #3a3a3a; line-height: 1.6;">${i}</li>`).join('')}
                    </ul>
                    <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                        <a href="${BOOK_URL}" class="btn btn-primary">Book Same-Day Pickup</a>
                        <a href="tel:+15619441636" style="color: #DC2626; font-weight: 600; text-decoration: none; align-self: center;">Call ${PHONE}</a>
                    </div>
                </div>
                <p style="font-size: 0.85rem; color: #8a8a8a;">
                    Also see: <a href="/services/${g.serviceSlug}" style="color: #DC2626; text-decoration: none;">${g.serviceName} service page</a>
                    ${g.cityLinks ? ' &mdash; Available in ' + g.cityLinks.map(c => `<a href="/junk-removal/${c.city}/${g.serviceSlug}" style="color: #DC2626; text-decoration: none;">${c.name}</a>`).join(', ') : ''}
                </p>
            </div>
        </div>
    </section>`;
}

function optionCurbside(g) {
  if (!g.curbside) return '';
  return `
    <!-- Option 2: Municipal -->
    <section id="curbside" style="padding: 3rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 0.5rem;">Option 2: Municipal / County Pickup</h2>
                <p style="color: #5c5c5c; margin-bottom: 1.5rem;">Free for South Florida residents — but requires advance scheduling.</p>
                <div class="county-block"><strong>Palm Beach County</strong><p>${g.curbside.palmBeach}</p></div>
                <div class="county-block"><strong>Broward County</strong><p>${g.curbside.broward}</p></div>
                <div class="county-block"><strong>Miami-Dade County</strong><p>${g.curbside.miamiDade}</p></div>
            </div>
        </div>
    </section>`;
}

function optionDonation(g) {
  if (!g.donation) return '';
  return `
    <!-- Option 3: Donation -->
    <section id="donation" style="padding: 3rem 0;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 1rem;">Option 3: Donation</h2>
                <p style="line-height: 1.75; color: #3a3a3a; font-size: 1rem;">${g.donation}</p>
            </div>
        </div>
    </section>`;
}

function optionDiy(g) {
  if (!g.diy) return '';
  return `
    <!-- Option 4: DIY -->
    <section id="diy" style="padding: 3rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 1rem;">Option 4: DIY Disposal</h2>
                <p style="line-height: 1.75; color: #3a3a3a; font-size: 1rem;">${g.diy}</p>
            </div>
        </div>
    </section>`;
}

function costTable(g) {
  if (!g.costTable) return '';
  return `
    <!-- Cost Comparison -->
    <section id="cost-comparison" style="padding: 3rem 0;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 0.5rem; text-align: center;">Cost Comparison</h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 1.5rem;">Compare all options side by side.</p>
                <div style="overflow-x: auto;">
                    <table class="guide-table">
                        <thead>
                            <tr>
                                <th>Option</th>
                                <th>Cost</th>
                                <th>Timeline</th>
                                <th>Your Effort</th>
                                <th>Eco Impact</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${g.costTable.map(r => `<tr><td>${r.method}</td><td>${r.cost}</td><td>${r.time}</td><td>${r.effort}</td><td>${r.eco}</td></tr>`).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </section>`;
}

function environmental(g) {
  if (!g.environmental) return '';
  return `
    <!-- Environmental Impact -->
    <section id="environmental" style="padding: 3rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 1rem;">Environmental Impact</h2>
                <p style="line-height: 1.75; color: #3a3a3a; font-size: 1rem;">${g.environmental}</p>
            </div>
        </div>
    </section>`;
}

function mistakes(g) {
  if (!g.mistakes) return '';
  return `
    <!-- Common Mistakes -->
    <section id="mistakes" style="padding: 3rem 0;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 1.5rem;">Common Mistakes to Avoid</h2>
                ${g.mistakes.map(m => `<div class="mistake-card"><strong>${m.title}</strong><p>${m.body}</p></div>`).join('')}
            </div>
        </div>
    </section>`;
}

function faqSection(g) {
  if (!g.faqs) return '';
  return `
    <!-- FAQ -->
    <section id="faq" style="padding: 3rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 1.5rem;">Frequently Asked Questions</h2>
                ${g.faqs.map((f, i) => `
                <div class="faq-item">
                    <div class="faq-q" onclick="var a=this.nextElementSibling;a.classList.toggle('open');this.querySelector('span').textContent=a.classList.contains('open')?'-':'+'" style="font-size: 1rem;">
                        ${f.q} <span style="font-size: 1.25rem; color: #DC2626;">+</span>
                    </div>
                    <div class="faq-a">
                        <p>${f.a}</p>
                    </div>
                </div>`).join('')}
            </div>
        </div>
    </section>`;
}

function relatedGuides(g) {
  if (!g.relatedGuides || !g.relatedGuides.length) return '';
  return `
    <!-- Related Guides -->
    <section style="padding: 3rem 0;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.4rem; font-weight: 800; margin-bottom: 1rem;">Related Guides</h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                    ${g.relatedGuides.map(r => `
                    <a href="/guides/${r.slug}" style="display: block; padding: 1rem 1.25rem; background: #f9fafb; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.07); color: #1a1a1a; text-decoration: none; font-weight: 600; font-size: 0.95rem; transition: border-color 0.2s;">
                        ${r.title}
                    </a>`).join('')}
                    <a href="/guides/junk-removal-cost-south-florida" style="display: block; padding: 1rem 1.25rem; background: #f9fafb; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.07); color: #1a1a1a; text-decoration: none; font-weight: 600; font-size: 0.95rem;">
                        Junk Removal Cost Guide (South Florida)
                    </a>
                </div>
            </div>
        </div>
    </section>`;
}

function ctaSection() {
  return `
    <!-- CTA -->
    <section style="padding: 4rem 0; background: linear-gradient(135deg, #DC2626 0%, #B91C1C 100%); color: white;">
        <div class="container">
            <div style="max-width: 700px; margin: 0 auto; text-align: center;">
                <h2 style="font-family: Outfit, sans-serif; font-size: clamp(1.75rem, 4vw, 2.25rem); font-weight: 800; margin-bottom: 1rem; color: white;">
                    Ready to Get Rid of It?
                </h2>
                <p style="font-size: 1.05rem; margin-bottom: 2rem; opacity: 0.9; line-height: 1.7;">
                    Umuve serves all of South Florida with same-day pickup starting at $89. Licensed, insured, and 92% recycled or donated. No hidden fees.
                </p>
                <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                    <a href="${BOOK_URL}" style="background: white; color: #DC2626; font-weight: 700; padding: 0.9rem 2rem; border-radius: 0.5rem; text-decoration: none; font-size: 1rem;">
                        Book Free Pickup
                    </a>
                    <a href="tel:+15619441636" style="background: rgba(255,255,255,0.15); color: white; font-weight: 700; padding: 0.9rem 2rem; border-radius: 0.5rem; text-decoration: none; font-size: 1rem; border: 2px solid rgba(255,255,255,0.4);">
                        Call ${PHONE}
                    </a>
                </div>
                <p style="margin-top: 1.5rem; opacity: 0.75; font-size: 0.9rem;">
                    SMS: <a href="sms:${SMS}" style="color: white;">${SMS}</a> &bull; Palm Beach, Broward &amp; Miami-Dade
                </p>
            </div>
        </div>
    </section>`;
}

function footer() {
  return `
    <!-- Footer -->
    <footer style="background: #1a1a1a; color: #8a8a8a; padding: 2.5rem 0;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 1.5rem;">
                <div>
                    <img src="/logo-nav.png" alt="Umuve — Hauling Made Simple" width="107" height="32" loading="lazy" style="filter: brightness(0) invert(1); margin-bottom: 0.75rem;">
                    <p style="font-size: 0.85rem; line-height: 1.6; max-width: 280px;">Hauling Made Simple. Serving Palm Beach, Broward, and Miami-Dade counties.</p>
                </div>
                <div style="display: flex; gap: 2.5rem; flex-wrap: wrap;">
                    <div>
                        <h4 style="color: white; font-size: 0.9rem; font-weight: 700; margin-bottom: 0.75rem;">Services</h4>
                        <ul style="list-style: none; padding: 0; font-size: 0.85rem;">
                            <li style="margin-bottom: 0.4rem;"><a href="/services/furniture-removal" style="color: #8a8a8a; text-decoration: none;">Furniture Removal</a></li>
                            <li style="margin-bottom: 0.4rem;"><a href="/services/appliance-removal" style="color: #8a8a8a; text-decoration: none;">Appliance Removal</a></li>
                            <li style="margin-bottom: 0.4rem;"><a href="/services/estate-cleanout" style="color: #8a8a8a; text-decoration: none;">Estate Cleanout</a></li>
                            <li style="margin-bottom: 0.4rem;"><a href="/services/garage-cleanout" style="color: #8a8a8a; text-decoration: none;">Garage Cleanout</a></li>
                        </ul>
                    </div>
                    <div>
                        <h4 style="color: white; font-size: 0.9rem; font-weight: 700; margin-bottom: 0.75rem;">Guides</h4>
                        <ul style="list-style: none; padding: 0; font-size: 0.85rem;">
                            <li style="margin-bottom: 0.4rem;"><a href="/guides/junk-removal-cost-south-florida" style="color: #8a8a8a; text-decoration: none;">Cost Guide</a></li>
                            <li style="margin-bottom: 0.4rem;"><a href="/guides/how-to-dispose-of-a-mattress" style="color: #8a8a8a; text-decoration: none;">Mattress Disposal</a></li>
                            <li style="margin-bottom: 0.4rem;"><a href="/guides/garage-cleanout-guide" style="color: #8a8a8a; text-decoration: none;">Garage Cleanout</a></li>
                        </ul>
                    </div>
                    <div>
                        <h4 style="color: white; font-size: 0.9rem; font-weight: 700; margin-bottom: 0.75rem;">Contact</h4>
                        <ul style="list-style: none; padding: 0; font-size: 0.85rem;">
                            <li style="margin-bottom: 0.4rem;"><a href="tel:+15619441636" style="color: #8a8a8a; text-decoration: none;">${PHONE}</a></li>
                            <li style="margin-bottom: 0.4rem;"><a href="${BOOK_URL}" style="color: #8a8a8a; text-decoration: none;">Book Online</a></li>
                            <li style="margin-bottom: 0.4rem;"><a href="/privacy" style="color: #8a8a8a; text-decoration: none;">Privacy Policy</a></li>
                        </ul>
                    </div>
                </div>
            </div>
            <div style="max-width: 900px; margin: 2rem auto 0; padding-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.07); font-size: 0.8rem; text-align: center;">
                &copy; 2026 Umuve. All rights reserved. Licensed &amp; Insured. Serving Palm Beach, Broward, and Miami-Dade counties.
            </div>
        </div>
    </footer>

    <!-- Sticky CTA -->
    <div class="sticky-cta" style="display: none;" id="stickyCta">
        <span style="font-size: 0.9rem;">Same-day pickup from $89</span>
        <a href="${BOOK_URL}" style="background: white; color: #DC2626; font-weight: 700; padding: 0.5rem 1.25rem; border-radius: 0.4rem; font-size: 0.9rem;">Book Now</a>
        <a href="tel:+15619441636" style="font-size: 0.9rem; opacity: 0.85;">${PHONE}</a>
        <button onclick="document.getElementById('stickyCta').style.display='none'" style="background: none; border: none; color: white; font-size: 1.2rem; cursor: pointer; padding: 0 0.25rem;">&times;</button>
    </div>
    <script>
        window.addEventListener('scroll', function(){
            var el = document.getElementById('stickyCta');
            if(window.scrollY > 600) el.style.display='flex';
        }, {passive: true});
    </script>`;
}

// ─── Simple guide template (guides with isSimple flag) ───────────────────────

function buildSimpleGuide(g) {
  return `${head(g)}
<body>
${nav()}
${breadcrumb(g)}
${hero(g)}

    <section style="padding: 3rem 0;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.5rem; font-weight: 800; margin-bottom: 1.25rem;">Key Disposal Facts for ${g.h1.replace('How to Dispose of a ', '').replace('How to Dispose of an ', '')}</h2>
                <ul style="padding-left: 1.25rem; margin-bottom: 2rem;">
                    ${g.keyPoints.map(p => `<li style="padding: 0.4rem 0; color: #3a3a3a; line-height: 1.65; font-size: 1rem;">${p}</li>`).join('')}
                </ul>

                <div style="background: #FEF2F2; border: 1px solid #FECACA; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 2rem;">
                    <h3 style="font-size: 1.1rem; font-weight: 700; color: #DC2626; margin-bottom: 0.75rem;">County Disposal Rules</h3>
                    <p style="color: #3a3a3a; line-height: 1.7; font-size: 0.95rem; margin: 0;">
                        All three South Florida counties — Palm Beach, Broward, and Miami-Dade — accept this type of appliance through scheduled bulk curbside pickup. Schedule online or by phone with your city or county solid waste department. Most appointments are available within 5-14 business days. No special prep required unless the unit contains refrigerants.
                    </p>
                </div>

                <div style="background: white; border: 1px solid rgba(0,0,0,0.07); border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 2rem;">
                    <h3 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 0.75rem;">Professional Removal by Umuve</h3>
                    <p style="color: #3a3a3a; line-height: 1.7; font-size: 0.95rem; margin-bottom: 1rem;">
                        Umuve removes this type of appliance starting at $89 with same-day service throughout South Florida. We handle disconnection, loading, hauling, and certified recycling — no prep needed on your end.
                    </p>
                    <a href="${BOOK_URL}" class="btn btn-primary">Book Same-Day Pickup</a>
                </div>
            </div>
        </div>
    </section>

    ${relatedGuides(g)}
    ${ctaSection()}
    ${footer()}
</body>
</html>`;
}

// ─── DIY guide template ───────────────────────────────────────────────────────

function buildDiyGuide(g) {
  return `${head(g)}
<body>
${nav()}
${breadcrumb(g)}
${hero(g)}

    ${tocBlock([
    { id: 'steps', label: 'Step-by-Step Instructions' },
    { id: 'tools', label: 'Tools You Need' },
    { id: 'disposal', label: 'Disposing of the Old Item' },
    { id: 'professional', label: 'Skip the DIY: Book Umuve' },
  ])}

    <!-- Steps -->
    <section id="steps" style="padding: 3rem 0;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 1.5rem;">Step-by-Step: ${g.h1}</h2>
                ${g.steps.map(s => `
                <div class="step-card">
                    <div class="step-num">${s.num}</div>
                    <div class="step-content">
                        <h3>${s.title}</h3>
                        <p>${s.body}</p>
                    </div>
                </div>`).join('')}
            </div>
        </div>
    </section>

    <!-- Disposal Note -->
    <section id="disposal" style="padding: 3rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 1rem;">Disposing of the Removed Item</h2>
                <p style="line-height: 1.75; color: #3a3a3a; font-size: 1rem;">${g.disposalNote}</p>
            </div>
        </div>
    </section>

    <!-- Professional option -->
    <section id="professional" style="padding: 3rem 0;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 1rem;">Skip the DIY: Let Umuve Handle It</h2>
                <p style="color: #3a3a3a; line-height: 1.75; margin-bottom: 1.5rem;">
                    If you would rather not deal with the disconnection, the heavy lifting, or the disposal logistics, Umuve handles everything start to finish — same-day, starting at $89. We carry from anywhere in your home, load, haul, and recycle or donate responsibly.
                </p>
                <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                    <a href="${BOOK_URL}" class="btn btn-primary">Book Same-Day Service</a>
                    <a href="tel:+15619441636" style="color: #DC2626; font-weight: 600; text-decoration: none; align-self: center;">Call ${PHONE}</a>
                </div>
                <p style="margin-top: 1rem; font-size: 0.9rem; color: #8a8a8a;">
                    Service available in <a href="/junk-removal/${g.cityLinks[0].city}/${g.serviceSlug}" style="color: #DC2626; text-decoration: none;">${g.cityLinks[0].name}</a>,
                    <a href="/junk-removal/${g.cityLinks[1].city}/${g.serviceSlug}" style="color: #DC2626; text-decoration: none;">${g.cityLinks[1].name}</a>,
                    <a href="/junk-removal/${g.cityLinks[2].city}/${g.serviceSlug}" style="color: #DC2626; text-decoration: none;">${g.cityLinks[2].name}</a>, and all of South Florida.
                </p>
            </div>
        </div>
    </section>

    ${relatedGuides(g)}
    ${ctaSection()}
    ${footer()}
</body>
</html>`;
}

// ─── Checklist/lifestyle guide template ──────────────────────────────────────

function buildChecklistGuide(g) {
  return `${head(g)}
<body>
${nav()}
${breadcrumb(g)}
${hero(g)}

    ${tocBlock([
    { id: 'timeline', label: 'Timeline and Checklist' },
    { id: 'room-by-room', label: 'Room-by-Room Tips' },
    { id: 'junk-removal', label: 'When to Call Umuve' },
  ])}

    <!-- Timeline -->
    <section id="timeline" style="padding: 3rem 0;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 1.5rem;">Checklist and Timeline</h2>
                ${g.timeline.map(phase => `
                <div class="phase-card">
                    <h3>${phase.when}</h3>
                    <ul>${phase.tasks.map(t => `<li>${t}</li>`).join('')}</ul>
                </div>`).join('')}
            </div>
        </div>
    </section>

    <!-- Room by Room -->
    <section id="room-by-room" style="padding: 3rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 1.5rem;">Room-by-Room Guide</h2>
                ${g.roomRooms.map(r => `
                <div class="tip-card">
                    <strong>${r.room}</strong>
                    <p>${r.tips}</p>
                </div>`).join('')}
            </div>
        </div>
    </section>

    <!-- Junk Removal CTA -->
    <section id="junk-removal" style="padding: 3rem 0;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 1rem;">When to Call Umuve</h2>
                <p style="color: #3a3a3a; line-height: 1.75; margin-bottom: 1.5rem;">
                    Once you have sorted and staged your items for removal, Umuve makes the actual hauling effortless. We pick up furniture, appliances, boxes of junk, and renovation debris — anything that is not going with you. Same-day service throughout South Florida starting at $89. Our teams carry, load, and haul while you focus on what comes next.
                </p>
                <div style="display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem;">
                    <a href="${BOOK_URL}" class="btn btn-primary">Book Same-Day Pickup</a>
                    <a href="tel:+15619441636" style="color: #DC2626; font-weight: 600; text-decoration: none; align-self: center;">Call ${PHONE}</a>
                </div>
                <p style="font-size: 0.9rem; color: #8a8a8a;">
                    Serving <a href="/junk-removal/${g.cityLinks[0].city}" style="color: #DC2626; text-decoration: none;">${g.cityLinks[0].name}</a>,
                    <a href="/junk-removal/${g.cityLinks[1].city}" style="color: #DC2626; text-decoration: none;">${g.cityLinks[1].name}</a>,
                    <a href="/junk-removal/${g.cityLinks[2].city}" style="color: #DC2626; text-decoration: none;">${g.cityLinks[2].name}</a>, and all of South Florida.
                </p>
            </div>
        </div>
    </section>

    ${relatedGuides(g)}
    ${ctaSection()}
    ${footer()}
</body>
</html>`;
}

// ─── Full disposal guide template ────────────────────────────────────────────

function buildFullGuide(g) {
  return `${head(g)}
<body>
${nav()}
${breadcrumb(g)}
${hero(g)}
${tocBlock(g.toc)}
${optionProfessional(g)}
${optionCurbside(g)}
${optionDonation(g)}
${optionDiy(g)}
${costTable(g)}
${environmental(g)}
${mistakes(g)}
${faqSection(g)}
${relatedGuides(g)}
${ctaSection()}
${footer()}
</body>
</html>`;
}

// ─── Generate all files ───────────────────────────────────────────────────────

const outputDir = path.join(__dirname, '../guides');
if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

let count = 0;
for (const g of allGuides) {
  let html;
  if (g.isSimple) {
    html = buildSimpleGuide(g);
  } else if (g.isDiy) {
    html = buildDiyGuide(g);
  } else if (g.isChecklist) {
    html = buildChecklistGuide(g);
  } else {
    html = buildFullGuide(g);
  }
  const filepath = path.join(outputDir, `${g.slug}.html`);
  fs.writeFileSync(filepath, html);
  count++;
  console.log(`  Generated: ${g.slug}.html`);
}

console.log(`\nDone. Generated ${count} guide pages to guides/`);

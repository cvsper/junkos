#!/usr/bin/env node

/**
 * Umuve SEO Neighborhood Sub-Page Generator
 * Generates neighborhood-level pages for hyper-local SEO targeting.
 * For each of the 42 cities, generates 3 neighborhood pages.
 * Output: pages/junk-removal/{city}-fl/{neighborhood-slug}.html
 *
 * URL pattern: /junk-removal/{city}-fl/{neighborhood-slug}
 * Example: /junk-removal/boca-raton-fl/mizner-park
 *
 * Existing rewrite in vercel.json handles routing:
 *   /junk-removal/:city/:service → /pages/junk-removal/:city/:service
 * Neighborhood slugs are distinct from service slugs — no conflicts.
 */

const fs = require('fs');
const path = require('path');

const cities = require('./data/cities.json');
const services = require('./data/services.json');

// --- Slugify neighborhood names ---
function slugify(name) {
    return name
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, '')
        .trim()
        .replace(/\s+/g, '-')
        .replace(/-+/g, '-');
}

// --- Deterministic hash picker ---
function pickByHash(arr, ...seeds) {
    const str = seeds.join('|');
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) - hash) + str.charCodeAt(i);
        hash |= 0;
    }
    return arr[Math.abs(hash) % arr.length];
}

// --- County-specific charity/donation partners ---
const countyCharities = {
    'Palm Beach': ['Habitat for Humanity of Palm Beach County', 'Palm Beach County Food Bank', 'Goodwill of the Palm Beaches', 'The Arc of Palm Beach County'],
    'Broward': ['Habitat for Humanity of Broward', 'LifeNet4Families', 'Goodwill of South Florida', 'Broward Partnership for the Homeless'],
    'Miami-Dade': ['Habitat for Humanity of Greater Miami', 'Miami Rescue Mission', 'Goodwill of South Florida', 'Chapman Partnership']
};

// --- Neighborhood type classification ---
// Returns one of: 'gated', 'downtown', 'beach', 'historic', 'suburban', 'luxury', 'senior', 'rural'
function classifyNeighborhood(neighborhoodName, citySlug) {
    const name = neighborhoodName.toLowerCase();

    // Gated/HOA communities
    const gatedKeywords = ['polo', 'boca west', 'broken sound', 'aero club', 'mirasol', 'pga national', 'windmill ranch', 'embassy lakes', 'heron bay', 'eagle trace', 'savanna', 'the ridges', 'grand palms', 'silver lakes', 'chapel trail', 'regency lakes', 'wynmoor', 'woodlands', 'mainlands', 'rock creek', 'olympia', 'madison green', 'saratoga lakes', 'crestwood', 'lacuna', 'the gardens', 'turnberry'];
    if (gatedKeywords.some(k => name.includes(k.toLowerCase()))) return 'gated';

    // Downtown/urban high-rise
    const downtownKeywords = ['downtown', 'brickell', 'miracle mile', 'las olas', 'wynwood', 'midtown', 'doral isles', 'aventura mall', 'williams island', 'golden isles', 'three islands', 'gulfstream'];
    if (downtownKeywords.some(k => name.includes(k.toLowerCase()))) return 'downtown';

    // Beach/waterfront
    const beachKeywords = ['beach', 'island', 'oceanfront', 'ocean', 'bay', 'cove', 'singer island', 'hypoluxo', 'lantana beach', 'crandon', 'ocean club', 'blue heron'];
    if (beachKeywords.some(k => name.includes(k.toLowerCase()))) return 'beach';

    // Historic
    const historicKeywords = ['historic', 'old northwood', 'sailboat bend', 'victoria park', 'colee hammock', 'northwood', 'crafts section', 'pineapple grove', 'marina historic', 'flamingo park', 'college park', 'lucerne', 'fulford', 'griffing park', 'carol city', 'bunche park', 'park', 'sans souci'];
    if (historicKeywords.some(k => name.includes(k.toLowerCase()))) return 'historic';

    // Senior/55+
    const seniorKeywords = ['leisureville', 'wynmoor', 'woodmont', 'mainlands', 'palm aire', 'crystal lake'];
    if (seniorKeywords.some(k => name.includes(k.toLowerCase()))) return 'senior';

    // Rural/large lot
    const ruralKeywords = ['farms', 'ranch', 'ranchettes', 'acres', 'estates', 'long lake', 'rolling oaks', 'pine island ridge'];
    if (ruralKeywords.some(k => name.includes(k.toLowerCase()))) return 'rural';

    // Luxury
    const luxuryKeywords = ['royal oaks', 'loch lomond', 'coral pine', 'banyan lakes', 'keystone', 'palm beach polo', 'jupiter island', 'riviera', 'riviera isles', 'sunset lakes', 'silver shores', 'costa del sol', 'lakes by the bay', 'the hammocks'];
    if (luxuryKeywords.some(k => name.includes(k.toLowerCase()))) return 'luxury';

    // Default to suburban
    return 'suburban';
}

// --- Generate neighborhood type-specific "Why Choose" reasons ---
function getNeighborhoodWhyChoose(neighborhoodName, neighborhoodType, cityName) {
    const reasons = {
        gated: [
            `Pre-cleared access at ${neighborhoodName}'s gate — no guest pass delays, no waiting at security, no HOA violations`,
            `We know the HOA rules in ${neighborhoodName} — everything from approved truck parking to waste area access, handled correctly`,
            `${neighborhoodName} residents get matched with operators who have completed prior jobs in this community`
        ],
        downtown: [
            `We know the freight elevator schedules and loading dock rules at ${neighborhoodName} high-rises — no wasted time on arrival`,
            `${neighborhoodName} building managers trust us — we follow parking and loading protocols that keep your building staff happy`,
            `Urban removal specialists for ${neighborhoodName}: tight hallways, narrow elevators, and city parking logistics are our daily routine`
        ],
        beach: [
            `Salt air and humidity accelerate damage in ${neighborhoodName} — we remove corroded outdoor furniture, weathered patio sets, and beach-adjacent debris others won't touch`,
            `Condo associations in ${neighborhoodName} have strict rules about debris staging and truck access — we've navigated these before`,
            `${neighborhoodName} seasonal residents get priority same-day scheduling to fit around your Florida calendar`
        ],
        historic: [
            `Historic district rules in ${neighborhoodName} require careful debris handling — we protect your property and your neighbors' during every removal`,
            `Our operators understand the tight lot lines and mature tree canopies in ${neighborhoodName} — we get in and out without landscape damage`,
            `${neighborhoodName} renovation debris specialists: old plaster, vintage fixtures, century-old lumber — handled with the care these materials deserve`
        ],
        senior: [
            `Patient, respectful operators who understand the pace and priorities of ${neighborhoodName} residents — no rush, no pressure`,
            `We sort carefully — setting aside anything sentimental or valuable before loading, always with your consent`,
            `${neighborhoodName} community rules and activity schedules respected: we work within your community's approved hours and access routes`
        ],
        rural: [
            `${neighborhoodName}'s large lots and long driveways are no problem — our trucks are equipped for rural access and heavy loads`,
            `We haul the full range of rural property items: farm equipment, large appliances, outbuilding contents, and acreage debris`,
            `${neighborhoodName} neighbors don't have city bulk pickup — Umuve is your reliable alternative with same-day service`
        ],
        luxury: [
            `White-glove service for ${neighborhoodName}: uniformed operators, covered truck beds, and zero property damage — guaranteed`,
            `We handle high-value item sorting in ${neighborhoodName} estates — furniture, art pieces, and collectibles treated with care before any item moves`,
            `Discretion is standard in ${neighborhoodName}: quiet removal without noise, without mess, and without a truck sitting in your driveway all day`
        ],
        suburban: [
            `${neighborhoodName} families trust us for garage cleanouts, move-out hauls, and whole-home decluttering — we've done hundreds of suburban jobs like yours`,
            `Same-day service means your ${neighborhoodName} project doesn't sit half-done — we match you with a local operator in under ${30} minutes`,
            `We donate usable items from ${neighborhoodName} homes to local charities — keeping your community's contributions local`
        ]
    };
    return reasons[neighborhoodType] || reasons['suburban'];
}

// --- Generate neighborhood-specific FAQ questions ---
function getNeighborhoodFAQs(neighborhoodName, neighborhoodType, city, neighborhoodSlug) {
    const charities = countyCharities[city.county] || countyCharities['Palm Beach'];
    const localCharity = charities[0];
    const cityName = city.name;

    const faqs = {
        gated: [
            {
                q: `Do you have gate access for ${neighborhoodName} in ${cityName}?`,
                a: `Yes. We coordinate gate access before arrival — no delays at security, no guest pass complications. Our operators have completed prior jobs in ${neighborhoodName} and know the entry procedures. We arrive on time and get straight to work.`
            },
            {
                q: `Does my HOA allow Umuve trucks in ${neighborhoodName}?`,
                a: `We carry full liability insurance and follow all HOA rules regarding truck size, parking location, and approved working hours. In most gated communities including ${neighborhoodName}, we use the designated vendor entrance and coordinate with on-site management when required.`
            },
            {
                q: `How much does junk removal cost in ${neighborhoodName}, ${cityName}?`,
                a: `Junk removal in ${neighborhoodName} starts at $119 for a single item. Full garage cleanouts average $249-$399. Whole-home or estate cleanouts range from $399-$1,800+ depending on volume. Get an instant quote online — no phone call required.`
            },
            {
                q: `Can you remove items from inside a gated community without a resident present?`,
                a: `Yes, with prior authorization. We can coordinate access with your HOA management directly if you provide written authorization. This is common in ${neighborhoodName} when residents need removal during work hours. Call (561) 944-1636 to arrange.`
            }
        ],
        downtown: [
            {
                q: `Do you handle freight elevator coordination at ${neighborhoodName} buildings?`,
                a: `Yes. We contact building management before arrival to reserve freight elevator windows, confirm loading dock availability, and get any required vendor passes. In ${neighborhoodName}, most buildings have specific time slots — we work within them so you don't have to manage the logistics.`
            },
            {
                q: `Is there extra cost for high-rise removal in ${neighborhoodName}?`,
                a: `No floor surcharges. Our pricing is based on volume and item type, not what floor you're on. Whether you're on the 2nd or 32nd floor in ${neighborhoodName}, the quoted price is the price you pay.`
            },
            {
                q: `How do you handle parking in ${neighborhoodName} for junk removal?`,
                a: `Our operators are experienced with urban parking restrictions in ${cityName}. We use loading zones, coordinate with building management for dock access, and work quickly to minimize street presence. In most ${neighborhoodName} buildings we're in and out within 90 minutes.`
            },
            {
                q: `Can you remove items from a condo in ${neighborhoodName}?`,
                a: `Absolutely. Condo removal is one of our most common services in ${neighborhoodName}. We handle elevator logistics, coordinate with building staff, respect noise rules, and leave hallways spotless. Same-day booking available from $119.`
            }
        ],
        beach: [
            {
                q: `Do you remove weathered and salt-damaged items from ${neighborhoodName} properties?`,
                a: `Yes. Salt air damage is a reality in ${neighborhoodName}, and we handle corroded patio furniture, weathered outdoor sets, damaged pool equipment, and beach-adjacent debris regularly. No extra charge for weathered or water-damaged items.`
            },
            {
                q: `Does my condo association allow junk removal in ${neighborhoodName}?`,
                a: `Most condo associations in ${neighborhoodName} permit licensed, insured haulers like Umuve during designated hours. We carry full liability insurance and follow all building-specific protocols. Call (561) 944-1636 if you need us to coordinate directly with your property manager.`
            },
            {
                q: `How much does junk removal cost in ${neighborhoodName}, ${cityName}?`,
                a: `Starting at $119 for a single item. Outdoor furniture and patio sets average $149-$299. Full condo cleanouts range from $399-$1,800 depending on size and volume. All prices include labor, hauling, and eco-friendly disposal.`
            },
            {
                q: `Can you remove boat equipment and marine items in ${neighborhoodName}?`,
                a: `Yes. We haul boat accessories, dock equipment, marine furniture, and waterfront property items throughout ${cityName}. Items go to recyclers or donation centers as appropriate. Same-day service available.`
            }
        ],
        historic: [
            {
                q: `Are you careful around historic structures when working in ${neighborhoodName}?`,
                a: `Absolutely. Our operators in ${neighborhoodName} are trained to protect mature trees, historic facades, and adjacent property during every removal. We use protective coverings on floors and door frames, and take extra care navigating through vintage home layouts with narrow hallways and tight doorways.`
            },
            {
                q: `Can you handle renovation debris from ${neighborhoodName} historic homes?`,
                a: `Yes. Old plaster, vintage lumber, historic tile, and century-old fixtures are materials we handle regularly in ${neighborhoodName}. We sort carefully — some vintage materials have salvage value and we'll set those aside on request. Everything else goes to appropriate recycling or disposal facilities.`
            },
            {
                q: `How much does junk removal cost in ${neighborhoodName}, ${cityName}?`,
                a: `Starting at $119 for a single item. Renovation debris removal starts at $149. Estate and whole-home cleanouts range from $399 to $1,800+. All prices are upfront with no surprise fees.`
            },
            {
                q: `Do you work with contractors doing historic renovations in ${neighborhoodName}?`,
                a: `Yes. We serve as debris removal partners for contractors throughout ${cityName}'s historic neighborhoods. We offer recurring pickup schedules, same-day availability, and competitive rates for ongoing projects. Call (561) 944-1636 to discuss contractor arrangements.`
            }
        ],
        senior: [
            {
                q: `Are your operators respectful and patient in ${neighborhoodName}?`,
                a: `Yes. Our operators who serve ${neighborhoodName} are experienced with senior and retirement community protocols — patient, respectful, and focused on your comfort throughout the process. We set aside anything you want to keep and only remove what you've confirmed.`
            },
            {
                q: `Do you work within ${neighborhoodName}'s approved hours and community rules?`,
                a: `Yes. We respect ${neighborhoodName}'s activity schedules, approved vendor hours, and access procedures. We contact community management when required and follow all on-site rules. No surprises for you or your neighbors.`
            },
            {
                q: `Can you help with a downsizing cleanout in ${neighborhoodName}?`,
                a: `Absolutely. Downsizing cleanouts are one of our most common services in ${neighborhoodName}. We sort carefully, donate usable items to ${localCharity}, recycle responsibly, and leave the space clean. Pricing starts at $399 for a 1-bedroom unit and goes up based on volume.`
            },
            {
                q: `How much does junk removal cost in ${neighborhoodName}, ${cityName}?`,
                a: `Starting at $119 for a single item pickup. Full apartment cleanouts average $399-$799. Pricing is upfront and transparent — you approve the quote before we start. No hidden fees, no pressure.`
            }
        ],
        rural: [
            {
                q: `Can you access large lots and rural properties in ${neighborhoodName}?`,
                a: `Yes. Our trucks handle long driveways, dirt roads, uneven terrain, and wide-lot access in ${neighborhoodName}. We're equipped for the full range of rural property items — farm debris, outbuilding contents, large appliances, and acreage cleanouts.`
            },
            {
                q: `Do you pick up rural property items like farm equipment in ${neighborhoodName}?`,
                a: `We pick up most rural property items: large appliances, outbuilding contents, old farm equipment, construction debris, and yard waste. For very large industrial machinery, we'd assess on a case-by-case basis. Call (561) 944-1636 for large or unusual items.`
            },
            {
                q: `How much does junk removal cost in ${neighborhoodName}, ${cityName}?`,
                a: `Starting at $119 for a single item. Outbuilding or barn cleanouts start at $249. Large property cleanouts range from $499 to $1,800+ depending on volume. Pricing includes labor, loading, and hauling to appropriate facilities.`
            },
            {
                q: `Is same-day service available for ${neighborhoodName}?`,
                a: `Yes. Same-day service is available across ${city.county} County including ${neighborhoodName}. Book before noon for same-day pickup. Average response time for rural areas in ${cityName} is ${city.avgResponseMinutes + 5} minutes from booking confirmation.`
            }
        ],
        luxury: [
            {
                q: `Do you offer discreet, white-glove junk removal in ${neighborhoodName}?`,
                a: `Yes. In ${neighborhoodName}, we use covered truck beds, uniformed operators, and standard property protection protocols. We work efficiently and quietly — no loud equipment, no debris left behind, no visible mess during the process.`
            },
            {
                q: `How do you handle high-value items during removal in ${neighborhoodName}?`,
                a: `Before any item moves, we walk through with you to identify what stays, what gets donated, and what gets removed. We never make assumptions. Furniture, art adjacent items, and anything flagged as potentially valuable is set aside for your review.`
            },
            {
                q: `How much does junk removal cost in ${neighborhoodName}, ${cityName}?`,
                a: `Starting at $119 for a single item. Estate cleanouts start at $399. Full luxury home cleanouts can range from $1,200 to $3,500+ depending on volume and property size. All pricing is provided upfront before work begins.`
            },
            {
                q: `Do you have experience with ${neighborhoodName}-style properties in ${cityName}?`,
                a: `Yes. Our operators have completed hundreds of jobs in ${cityName}'s premium neighborhoods. We understand the expectations around property care, timing, and professional conduct. ${city.rating} stars from ${city.reviewCount} verified reviews reflects our standard of service.`
            }
        ],
        suburban: [
            {
                q: `How much does junk removal cost in ${neighborhoodName}, ${cityName}?`,
                a: `Junk removal in ${neighborhoodName} starts at $119 for a single item. A full garage cleanout averages $249. Whole-home cleanouts range from $399 to $1,800+ depending on volume. Get an instant quote online in 3 minutes — no phone call needed.`
            },
            {
                q: `Can you pick up large items from inside my home in ${neighborhoodName}?`,
                a: `Yes. Our operators navigate stairs, hallways, and tight doorways daily across ${cityName}. Sectionals that won't fit through doors get disassembled on-site at no extra charge. Second-floor removals cost the same as ground-floor pickups.`
            },
            {
                q: `Is same-day service available in ${neighborhoodName}, ${cityName}?`,
                a: `Yes. Same-day junk removal is available across all of ${city.county} County. Book before noon and we typically match you with an operator the same day. Average response time in ${cityName} is ${city.avgResponseMinutes} minutes from booking.`
            },
            {
                q: `What happens to items you remove from ${neighborhoodName} homes?`,
                a: `Usable items are donated to ${localCharity} and other ${city.county} County charities. Recyclable materials are sorted and sent to appropriate facilities. On average, 85-92% of what we collect across ${cityName} stays out of landfills.`
            }
        ]
    };

    return faqs[neighborhoodType] || faqs['suburban'];
}

// --- Generate neighborhood intro paragraph ---
function getNeighborhoodIntro(neighborhoodName, neighborhoodDesc, neighborhoodType, city) {
    const cityName = city.name;

    if (neighborhoodDesc) {
        // Lead with the city-specific description, then add type-specific context
        const typeContext = {
            gated: ` When you live in a gated community like ${neighborhoodName}, you need a hauler who knows the rules — gate access, HOA requirements, approved vendor hours. Umuve operators are pre-cleared for most ${cityName} communities, which means no delays, no code violations, and no headaches for you.`,
            downtown: ` High-rise and urban removal comes with real logistics challenges — freight elevator windows, loading dock schedules, city parking restrictions. Our operators handle every one of these in ${neighborhoodName} daily, so you get same-day service without the coordination burden.`,
            beach: ` Beach and waterfront properties have their own removal challenges: salt-damaged outdoor furniture, condo association rules, and seasonal timing pressures. Umuve handles all of it in ${neighborhoodName} with the same reliability and upfront pricing that ${cityName} residents count on.`,
            historic: ` Historic neighborhoods like ${neighborhoodName} require careful hands — tight lots, mature trees, vintage construction, and preservation-minded neighbors. Our operators handle renovation debris and whole-home cleanouts here routinely, with the care that these properties deserve.`,
            senior: ` In ${neighborhoodName}, our operators understand that a good cleanout is about trust and patience, not just speed. We sort carefully, set aside anything you want to keep, and handle everything else with dignity and respect.`,
            rural: ` ${neighborhoodName}'s larger lots and rural character mean bigger loads and longer drives — our trucks are equipped for both. Same-day service is available throughout ${cityName}, including rural properties in ${neighborhoodName}.`,
            luxury: ` In ${neighborhoodName}, we bring white-glove standards to every job: covered loads, protected floors, quiet operation, and operators who understand that your property deserves professional care from the first step to the last.`,
            suburban: ` In ${neighborhoodName}, the most common calls we get are garage cleanouts, furniture hauls, and move-out cleanups — and we've handled thousands of them across ${cityName}. Starting at $119, same-day service available.`
        };
        return neighborhoodDesc + (typeContext[neighborhoodType] || typeContext['suburban']);
    }

    // Fallback intros when no city-specific description exists
    const fallbacks = {
        gated: `Junk removal in ${neighborhoodName}, ${cityName} requires more than a truck and a crew — it requires gate access coordination, HOA knowledge, and timing that works within your community's rules. Umuve's local operators are pre-cleared at most ${cityName} gated communities. Same-day service, upfront pricing, no HOA violations. From $119.`,
        downtown: `${neighborhoodName}'s urban density means freight elevators, loading docks, and city parking are part of every junk removal job here. Umuve's operators handle all of it — freight elevator booking, dock coordination, and tight urban navigation — so your removal goes smoothly from start to finish. Same-day service from $119.`,
        beach: `${neighborhoodName}'s beachfront and waterfront properties produce a specific type of junk removal need: weathered outdoor furniture, condo-association-managed disposal, and season-timed cleanouts. Umuve serves ${neighborhoodName} with the reliability and same-day availability that ${cityName} residents expect. Starting at $119.`,
        historic: `${neighborhoodName}'s historic character comes with narrow lots, mature trees, and vintage construction that requires careful removal work. Umuve operators navigate these properties daily — from renovation debris to whole-home cleanouts. We protect what matters and remove what doesn't. From $119.`,
        senior: `${neighborhoodName} residents count on Umuve for patient, respectful junk removal that fits their schedule and community rules. Whether it's downsizing, a single-item pickup, or a full cleanout, our operators work at your pace and leave nothing behind — except a cleaner home. From $119.`,
        rural: `${neighborhoodName}'s larger lots and rural properties need a hauler that can handle the access and the volume. Umuve's trucks are equipped for long driveways, wide lots, and heavy loads across all of ${cityName}'s rural neighborhoods. Same-day service from $119.`,
        luxury: `${neighborhoodName} residents expect more from a junk removal company — and Umuve delivers. Professional operators, property-protective practices, discreet service, and upfront pricing that respects your time. From single-item hauls to whole-estate cleanouts, we bring the right level of care to every ${neighborhoodName} job. Starting at $119.`,
        suburban: `${neighborhoodName} is one of ${cityName}'s most active junk removal areas — garage cleanouts, furniture swaps, and move-out hauls are our bread and butter here. Umuve connects you with a local, licensed operator in under ${city.avgResponseMinutes} minutes. Same-day service, starting at $119.`
    };

    return fallbacks[neighborhoodType] || fallbacks['suburban'];
}

// --- Generate How It Works step 2 for neighborhoods ---
function getNeighborhoodHowItWorksStep2(neighborhoodType, neighborhood, city) {
    const step2 = {
        gated: `We coordinate gate access before dispatch — your operator arrives with building pass information already confirmed. No guest pass delays, no waiting at the ${neighborhood} entrance. Average match time: ${city.avgResponseMinutes} minutes.`,
        downtown: `We match you with an operator who knows ${neighborhood}'s freight elevator schedule and loading dock rules. Your operator arrives with dock access confirmed and elevator window reserved. Average match time: ${city.avgResponseMinutes} minutes.`,
        beach: `We find the nearest operator experienced with waterfront property and condo-association access in ${neighborhood}. Your operator arrives prepared for building protocols. Average match time: ${city.avgResponseMinutes} minutes.`,
        historic: `We match you with an operator experienced in ${city.name}'s historic neighborhoods — someone who understands tight lots, narrow hallways, and renovation debris. Average match time: ${city.avgResponseMinutes} minutes.`,
        senior: `We match you with a patient, experienced operator familiar with ${neighborhood}'s community rules and approved hours. Average match time: ${city.avgResponseMinutes} minutes.`,
        rural: `We find the nearest operator equipped for large-lot access — long driveways, wide properties, and heavy rural loads. Average match time: ${city.avgResponseMinutes + 5} minutes from confirmation.`,
        luxury: `We match you with one of our highest-rated operators experienced in ${city.name}'s premium neighborhoods. Property protection protocols are confirmed before arrival. Average match time: ${city.avgResponseMinutes} minutes.`,
        suburban: `Our system finds the nearest available operator in ${neighborhood} — ${city.operators} local operators across ${city.name} means fast matching. Average match time: ${city.avgResponseMinutes} minutes.`
    };
    return step2[neighborhoodType] || step2['suburban'];
}

// --- Generate services grid for the page ---
function generateServicesGrid(city) {
    const top5Services = services.slice(0, 5);
    const allServiceLinks = services.map(s => `
                    <a href="/junk-removal/${city.slug}-fl/${s.slug}" style="display: flex; align-items: center; gap: 0.6rem; padding: 0.85rem 1rem; background: white; border-radius: 0.5rem; border: 1px solid rgba(0,0,0,0.06); text-decoration: none; color: #1a1a1a; font-weight: 500; font-size: 0.9rem; transition: border-color 0.2s;">
                        <span style="color: #DC2626; font-size: 1rem;">&#10003;</span>
                        ${s.name}
                    </a>`).join('');

    return allServiceLinks;
}

// --- Generate FAQ Schema ---
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

// --- Main neighborhood page generator ---
function generateNeighborhoodPage(neighborhood, neighborhoodSlug, city, otherNeighborhoods, allCities) {
    const neighborhoodType = classifyNeighborhood(neighborhood, city.slug);
    const neighborhoodDesc = (city.neighborhoodDescriptions && city.neighborhoodDescriptions[neighborhood]) || null;

    const title = `Junk Removal in ${neighborhood}, ${city.name}, FL | Umuve`;
    const pageUrl = `https://goumuve.com/junk-removal/${city.slug}-fl/${neighborhoodSlug}`;

    const metaDesc = `Professional junk removal in ${neighborhood}, ${city.name}, FL — from $119. ${city.operators} local operators, same-day service. ${city.rating} stars from ${city.reviewCount} reviews. Book online.`;

    const introText = getNeighborhoodIntro(neighborhood, neighborhoodDesc, neighborhoodType, city);
    const whyChooseReasons = getNeighborhoodWhyChoose(neighborhood, neighborhoodType, city.name);
    const faqs = getNeighborhoodFAQs(neighborhood, neighborhoodType, city, neighborhoodSlug);
    const charities = countyCharities[city.county] || countyCharities['Palm Beach'];

    // Top 5 service links for this city
    const top5ServiceLinks = services.slice(0, 5).map(s =>
        `<a href="/junk-removal/${city.slug}-fl/${s.slug}" class="related-link">${s.name} in ${city.name}</a>`
    ).join('\n                    ');

    // Nearby neighborhood links (the other 2 neighborhoods we generated for this city)
    const nearbyNeighborhoodLinks = otherNeighborhoods
        .filter(n => n.name !== neighborhood)
        .map(n => `<a href="/junk-removal/${city.slug}-fl/${n.slug}" class="related-link">${n.name}</a>`)
        .join('\n                    ');

    // Nearby cities in same county
    const nearbyCities = allCities
        .filter(c => c.county === city.county && c.slug !== city.slug)
        .slice(0, 5);

    const howItWorksStep2 = getNeighborhoodHowItWorksStep2(neighborhoodType, neighborhood, city);

    // Infer county step 3 text
    let step3Text;
    if (city.county === 'Palm Beach') {
        step3Text = `Your operator arrives on schedule, handles all the heavy lifting, and leaves your ${neighborhood} property clean. 92% of what we collect in Palm Beach County gets donated or recycled — not landfilled.`;
    } else if (city.county === 'Miami-Dade') {
        step3Text = `Your operator handles all lifting, loading, and haul-out from your ${neighborhood} property. We sort and recycle whenever possible — keeping Miami-Dade cleaner, one job at a time.`;
    } else {
        step3Text = `Your operator arrives, handles every item, and leaves your ${neighborhood} property clean. Every job is sorted for donation, recycling, or proper disposal — eco-friendly service every time.`;
    }

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="${metaDesc}">
    <meta name="robots" content="index, follow">

    <!-- Open Graph -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="${pageUrl}">
    <meta property="og:title" content="${title}">
    <meta property="og:description" content="${metaDesc}">
    <meta property="og:image" content="https://goumuve.com/logo-full.png">
    <meta property="og:site_name" content="Umuve">

    <!-- Twitter -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="${title}">
    <meta name="twitter:description" content="${metaDesc}">

    <!-- Canonical -->
    <link rel="canonical" href="${pageUrl}">

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
    <noscript><img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id=1785795592383973&ev=PageView&noscript=1" alt="Facebook Pixel"></noscript>

    <!-- Preload fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@700;800;900&display=swap" rel="stylesheet">

    <!-- Structured Data - LocalBusiness -->
    <script type="application/ld+json">
    ${JSON.stringify({
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": `Umuve Junk Removal — ${neighborhood}, ${city.name}`,
        "image": ["https://goumuve.com/logo-full.png"],
        "url": pageUrl,
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
        "areaServed": [
            {
                "@type": "Place",
                "name": `${neighborhood}, ${city.name}, FL`
            },
            {
                "@type": "City",
                "name": city.name
            }
        ],
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
    }, null, 8)}
    </script>

    <!-- Structured Data - FAQ -->
    <script type="application/ld+json">
    ${generateFAQSchema(faqs)}
    </script>

    <!-- Structured Data - Breadcrumb -->
    <script type="application/ld+json">
    ${JSON.stringify({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://goumuve.com" },
            { "@type": "ListItem", "position": 2, "name": "Junk Removal", "item": "https://goumuve.com/junk-removal" },
            { "@type": "ListItem", "position": 3, "name": `${city.name}, FL`, "item": `https://goumuve.com/junk-removal/${city.slug}-fl` },
            { "@type": "ListItem", "position": 4, "name": neighborhood, "item": pageUrl }
        ]
    }, null, 8)}
    </script>

    <link rel="stylesheet" href="/styles-seo.css">
</head>
<body>
    <!-- Nav -->
    <nav style="position: sticky; top: 0; background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); z-index: 100; border-bottom: 1px solid rgba(0,0,0,0.06);">
        <div class="container">
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem 0;">
                <a href="/" style="display: flex; align-items: center; text-decoration: none;">
                    <img src="/logo-nav.png" alt="Umuve — Same-Day Junk Removal in South Florida" width="120" height="36" loading="eager">
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
                <span style="margin: 0 0.5rem;">&rsaquo;</span>
                <a href="/junk-removal/${city.slug}-fl" style="color: #5c5c5c; text-decoration: none;">Junk Removal</a>
                <span style="margin: 0 0.5rem;">&rsaquo;</span>
                <a href="/junk-removal/${city.slug}-fl" style="color: #5c5c5c; text-decoration: none;">${city.name}, FL</a>
                <span style="margin: 0 0.5rem;">&rsaquo;</span>
                <span style="color: #1a1a1a; font-weight: 500;">${neighborhood}</span>
            </nav>
        </div>
    </div>

    <!-- Hero -->
    <section style="padding: 3.5rem 0 3rem; background: linear-gradient(135deg, #f9fafb 0%, #ffffff 100%);">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto; text-align: center;">
                <h1 style="font-family: Outfit, sans-serif; font-size: clamp(2rem, 5vw, 2.75rem); font-weight: 800; margin-bottom: 1.5rem; line-height: 1.15;">
                    Junk Removal in ${neighborhood}, ${city.name}, FL<br>
                    <span style="color: #DC2626;">From $119 — Same-Day Service</span>
                </h1>
                <p style="font-size: 1.1rem; color: #5c5c5c; margin-bottom: 2rem; line-height: 1.7; text-align: left;">
                    ${introText}
                </p>
                <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                    <a href="https://app.goumuve.com/book" class="btn btn-primary btn-xl">Get Free Quote</a>
                    <a href="tel:+15619441636" class="btn btn-secondary btn-xl">Call (561) 944-1636</a>
                </div>
                <p style="margin-top: 1rem; font-size: 0.85rem; color: #8a8a8a;">
                    ${city.rating}&#9733; from ${city.reviewCount} reviews &bull; Licensed &amp; Insured &bull; Same-Day Available
                </p>
            </div>
        </div>
    </section>

    <!-- City Stats Bar -->
    <div style="max-width: 800px; margin: 0 auto; padding: 0 1.5rem;">
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: 2rem auto 0; text-align: center;">
            <div>
                <div style="font-size: 1.75rem; font-weight: 800; color: #DC2626;">${city.jobsCompleted.toLocaleString()}+</div>
                <div style="font-size: 0.8rem; color: #8a8a8a;">Jobs in ${city.name}</div>
            </div>
            <div>
                <div style="font-size: 1.75rem; font-weight: 800; color: #DC2626;">${city.operators}</div>
                <div style="font-size: 0.8rem; color: #8a8a8a;">Local Operators</div>
            </div>
            <div>
                <div style="font-size: 1.75rem; font-weight: 800; color: #DC2626;">${city.avgResponseMinutes}min</div>
                <div style="font-size: 0.8rem; color: #8a8a8a;">Avg Response</div>
            </div>
            <div>
                <div style="font-size: 1.75rem; font-weight: 800; color: #DC2626;">${city.rating}&#9733;</div>
                <div style="font-size: 0.8rem; color: #8a8a8a;">${city.reviewCount} Reviews</div>
            </div>
        </div>
    </div>

    <!-- Trust Badges -->
    <div style="display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap; margin: 1.5rem auto; max-width: 700px; padding: 0 1.5rem;">
        <div style="text-align: center;">
            <img src="/images/seo/trust-badges/licensed-insured.svg" alt="Licensed and Insured" width="64" height="64" loading="lazy">
            <div style="font-size: 0.75rem; color: #5c5c5c; margin-top: 0.25rem;">Licensed &amp; Insured</div>
        </div>
        <div style="text-align: center;">
            <img src="/images/seo/trust-badges/eco-friendly.svg" alt="92% Recycled" width="64" height="64" loading="lazy">
            <div style="font-size: 0.75rem; color: #5c5c5c; margin-top: 0.25rem;">92% Recycled</div>
        </div>
        <div style="text-align: center;">
            <img src="/images/seo/trust-badges/same-day.svg" alt="Same-Day Service" width="64" height="64" loading="lazy">
            <div style="font-size: 0.75rem; color: #5c5c5c; margin-top: 0.25rem;">Same-Day Service</div>
        </div>
        <div style="text-align: center;">
            <img src="/images/seo/trust-badges/satisfaction.svg" alt="Satisfaction Guaranteed" width="64" height="64" loading="lazy">
            <div style="font-size: 0.75rem; color: #5c5c5c; margin-top: 0.25rem;">Satisfaction Guaranteed</div>
        </div>
    </div>

    <!-- Services Available -->
    <section style="padding: 3rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    All Services Available in ${neighborhood}
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    Every Umuve service is available throughout ${city.name} — including ${neighborhood}. Click any service for specific details and pricing.
                </p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem;">
                    ${generateServicesGrid(city)}
                </div>
            </div>
        </div>
    </section>

    <!-- Why Neighborhood Residents Choose Umuve -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    Why ${neighborhood} Residents Choose Umuve
                </h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap: 1.5rem;">
                    ${whyChooseReasons.map(reason => `
                    <div style="background: white; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.06);">
                        <div style="width: 48px; height: 48px; background: #FEE2E2; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-bottom: 1rem;">
                            <span style="color: #DC2626; font-size: 1.25rem; font-weight: 800;">&#10003;</span>
                        </div>
                        <p style="color: #3a3a3a; line-height: 1.6; font-weight: 500;">${reason}</p>
                    </div>`).join('')}
                </div>
            </div>
        </div>
    </section>

    <!-- How It Works -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    How Junk Removal Works in ${neighborhood}
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2.5rem; font-size: 1.05rem;">
                    Three steps. No phone tag, no waiting around for estimates.
                </p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 2rem;">
                    <div style="text-align: center; padding: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626; margin-bottom: 1rem;">01</div>
                        <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.75rem;">Book Online in 3 Minutes</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">Upload photos of your items, select your service, pick a date, and get instant pricing. No waiting, no home visits required.</p>
                    </div>
                    <div style="text-align: center; padding: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626; margin-bottom: 1rem;">02</div>
                        <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.75rem;">We Match You Locally</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">${howItWorksStep2}</p>
                    </div>
                    <div style="text-align: center; padding: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626; margin-bottom: 1rem;">03</div>
                        <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.75rem;">We Haul, You Relax</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">${step3Text}</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Pricing Overview -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 700px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    Junk Removal Pricing in ${neighborhood}
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    Transparent pricing — what you see is what you pay. All prices include labor, hauling, and eco-friendly disposal.
                </p>
                <div style="background: #FEF2F2; border: 1px solid #FECACA; border-radius: 0.75rem; padding: 1.25rem; margin-bottom: 2rem; text-align: center;">
                    <p style="font-size: 1.1rem; font-weight: 600; color: #DC2626;">
                        Average job cost in ${city.name}: $${city.avgJobCost}
                    </p>
                    <p style="font-size: 0.9rem; color: #5c5c5c; margin-top: 0.25rem;">
                        Based on ${city.jobsCompleted.toLocaleString()} completed jobs across ${city.name}
                    </p>
                </div>
                <div style="display: grid; gap: 0.75rem;">
                    <div class="pricing-row">
                        <div>
                            <strong>Single Item</strong><br>
                            <span style="font-size: 0.85rem; color: #8a8a8a;">One piece of furniture, appliance, or item</span>
                        </div>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #DC2626;">$119</span>
                    </div>
                    <div class="pricing-row">
                        <div>
                            <strong>Small Load</strong><br>
                            <span style="font-size: 0.85rem; color: #8a8a8a;">2-3 items, quarter truck</span>
                        </div>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #DC2626;">$149</span>
                    </div>
                    <div class="pricing-row popular">
                        <div>
                            <strong>Medium Load</strong> <span style="background: #DC2626; color: white; padding: 0.15rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; font-weight: 700;">MOST POPULAR</span><br>
                            <span style="font-size: 0.85rem; color: #8a8a8a;">Half truck, room cleanout</span>
                        </div>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #DC2626;">$299</span>
                    </div>
                    <div class="pricing-row">
                        <div>
                            <strong>Large Load</strong><br>
                            <span style="font-size: 0.85rem; color: #8a8a8a;">Three-quarter truck, multi-room</span>
                        </div>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #DC2626;">$449</span>
                    </div>
                    <div class="pricing-row">
                        <div>
                            <strong>Full Truck / Whole Home</strong><br>
                            <span style="font-size: 0.85rem; color: #8a8a8a;">Full truck load or complete home cleanout</span>
                        </div>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #DC2626;">$599+</span>
                    </div>
                </div>
                <p style="text-align: center; color: #8a8a8a; font-size: 0.85rem; margin-top: 1rem;">
                    For service-specific pricing, visit the <a href="/junk-removal/${city.slug}-fl" style="color: #DC2626;">full ${city.name} pricing page</a>.
                </p>
                <div style="text-align: center; margin-top: 2rem;">
                    <a href="https://app.goumuve.com/book" class="btn btn-primary btn-xl">Get Your Exact Price</a>
                </div>
            </div>
        </div>
    </section>

    <!-- FAQ -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    Frequently Asked Questions — Junk Removal in ${neighborhood}
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

    <!-- Nearby Neighborhoods -->
    ${otherNeighborhoods.filter(n => n.name !== neighborhood).length > 0 ? `
    <section style="padding: 3rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto; text-align: center;">
                <h2 style="font-size: 1.5rem; font-weight: 800; margin-bottom: 1rem;">
                    Other Neighborhoods We Serve in ${city.name}
                </h2>
                <p style="color: #5c5c5c; margin-bottom: 1.5rem;">
                    Umuve serves every neighborhood in ${city.name}. Here are a few more nearby areas:
                </p>
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: center;">
                    ${nearbyNeighborhoodLinks}
                    <a href="/junk-removal/${city.slug}-fl" class="related-link" style="font-weight: 700;">All of ${city.name}, FL &#8594;</a>
                </div>
            </div>
        </div>
    </section>` : ''}

    <!-- Related Services -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    Popular Services in ${city.name}
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    All services available throughout ${city.name}, including ${neighborhood}:
                </p>
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: center;">
                    ${top5ServiceLinks}
                </div>
                <div style="text-align: center; margin-top: 1.5rem;">
                    <a href="/junk-removal/${city.slug}-fl" class="related-link" style="font-weight: 700;">&#8592; All Services in ${city.name}, FL</a>
                </div>
            </div>
        </div>
    </section>

    <!-- Final CTA -->
    <section style="padding: 4rem 0; background: linear-gradient(135deg, #DC2626, #B91C1C); color: white; text-align: center;">
        <div class="container">
            <h2 style="font-family: Outfit; font-size: 2rem; font-weight: 800; margin-bottom: 1rem;">
                Ready for Junk Removal in ${neighborhood}?
            </h2>
            <p style="font-size: 1.1rem; margin-bottom: 2rem; opacity: 0.95; max-width: 600px; margin-left: auto; margin-right: auto;">
                ${city.jobsCompleted.toLocaleString()}+ jobs completed across ${city.name}. Get your free quote in 3 minutes — same-day service available.
            </p>
            <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                <a href="https://app.goumuve.com/book" style="background: white; color: #DC2626; padding: 1rem 2.5rem; font-weight: 700; border-radius: 0.5rem; text-decoration: none; display: inline-block; font-size: 1.1rem;">Book Online Now</a>
                <a href="tel:+15619441636" style="background: rgba(255,255,255,0.15); color: white; padding: 1rem 2.5rem; font-weight: 700; border-radius: 0.5rem; text-decoration: none; display: inline-block; font-size: 1.1rem; border: 2px solid rgba(255,255,255,0.3);">Call (561) 944-1636</a>
                <a href="sms:+18444356005" style="background: rgba(255,255,255,0.1); color: white; padding: 1rem 2.5rem; font-weight: 700; border-radius: 0.5rem; text-decoration: none; display: inline-block; font-size: 1.1rem; border: 2px solid rgba(255,255,255,0.2);">Text (844) 435-6005</a>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer style="background: #111111; color: white; padding: 3rem 0 5rem;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 2rem;">
                <div>
                    <img src="/logo-nav.png" alt="Umuve — Hauling Made Simple" width="107" height="32" loading="lazy" style="filter: brightness(10); margin-bottom: 1rem;">
                    <p style="color: #8a8a8a; font-size: 0.9rem; line-height: 1.6;">Hauling made simple. Professional junk removal across South Florida.</p>
                </div>
                <div>
                    <h4 style="font-weight: 700; margin-bottom: 0.75rem; font-size: 0.9rem;">Services</h4>
                    <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                        ${services.slice(0, 5).map(s => `<a href="/services/${s.slug}" style="color: #8a8a8a; text-decoration: none; font-size: 0.85rem;">${s.name}</a>`).join('\n                        ')}
                    </div>
                </div>
                <div>
                    <h4 style="font-weight: 700; margin-bottom: 0.75rem; font-size: 0.9rem;">Nearby Cities</h4>
                    <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                        ${nearbyCities.map(c => `<a href="/junk-removal/${c.slug}-fl" style="color: #8a8a8a; text-decoration: none; font-size: 0.85rem;">${c.name}, FL</a>`).join('\n                        ')}
                    </div>
                </div>
                <div>
                    <h4 style="font-weight: 700; margin-bottom: 0.75rem; font-size: 0.9rem;">Contact</h4>
                    <div style="display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.85rem;">
                        <a href="tel:+15619441636" style="color: #8a8a8a; text-decoration: none;">(561) 944-1636</a>
                        <a href="sms:+18444356005" style="color: #8a8a8a; text-decoration: none;">Text (844) 435-6005</a>
                        <a href="mailto:support@goumuve.com" style="color: #8a8a8a; text-decoration: none;">support@goumuve.com</a>
                        <a href="/privacy" style="color: #8a8a8a; text-decoration: none;">Privacy Policy</a>
                    </div>
                </div>
            </div>
            <div style="text-align: center; margin-top: 2rem; padding-top: 2rem; border-top: 1px solid rgba(255,255,255,0.1);">
                <p style="color: #5c5c5c; font-size: 0.8rem;">&copy; 2026 Umuve Inc. Licensed &amp; Insured. Serving Miami-Dade, Broward &amp; Palm Beach Counties.</p>
            </div>
        </div>
    </footer>

    <!-- Sticky CTA Bar -->
    <div class="sticky-cta">
        <a href="https://app.goumuve.com/book" class="book-btn">Book Junk Removal in ${neighborhood} &mdash; From $119</a>
        <a href="sms:+18444356005" class="sms-btn">Text Us</a>
    </div>

    <!-- FAQ Toggle Script -->
    <script>
        document.querySelectorAll('.faq-q').forEach(function(q) {
            q.addEventListener('click', function() {
                var a = this.nextElementSibling;
                var icon = this.querySelector('span:last-child');
                if (a.style.display === 'none' || !a.style.display) {
                    a.style.display = 'block';
                    icon.textContent = '\\u2212';
                } else {
                    a.style.display = 'none';
                    icon.textContent = '+';
                }
            });
        });
        document.querySelectorAll('.faq-a').forEach(function(a) { a.style.display = 'none'; });
    </script>
</body>
</html>`;

    return html;
}

// --- Main execution ---
const pagesDir = path.join(__dirname, '../pages/junk-removal');
let totalGenerated = 0;
const neighborhoodIndex = []; // For sitemap use

console.log(`Generating neighborhood pages for ${cities.length} cities (3 neighborhoods each)...`);

cities.forEach(city => {
    const cityDir = path.join(pagesDir, `${city.slug}-fl`);
    if (!fs.existsSync(cityDir)) {
        fs.mkdirSync(cityDir, { recursive: true });
    }

    // Take first 3 neighborhoods
    const targetNeighborhoods = (city.neighborhoods || []).slice(0, 3);

    // Build slug+name pairs for this city's 3 neighborhoods
    const neighborhoodMeta = targetNeighborhoods.map(n => ({
        name: n,
        slug: slugify(n)
    }));

    // Generate each neighborhood page
    neighborhoodMeta.forEach(({ name: neighborhood, slug: neighborhoodSlug }) => {
        const html = generateNeighborhoodPage(
            neighborhood,
            neighborhoodSlug,
            city,
            neighborhoodMeta, // pass all 3 for cross-linking
            cities
        );
        const filepath = path.join(cityDir, `${neighborhoodSlug}.html`);
        fs.writeFileSync(filepath, html);
        totalGenerated++;

        neighborhoodIndex.push({
            city: city.slug,
            neighborhood,
            slug: neighborhoodSlug,
            url: `https://goumuve.com/junk-removal/${city.slug}-fl/${neighborhoodSlug}`
        });
    });
});

console.log(`Generated ${totalGenerated} neighborhood pages across ${cities.length} cities.`);

// Write a JSON index file for sitemap generator to consume
const indexPath = path.join(__dirname, 'data/neighborhoods-index.json');
fs.writeFileSync(indexPath, JSON.stringify(neighborhoodIndex, null, 2));
console.log(`Wrote neighborhood index to seo-generator/data/neighborhoods-index.json (${neighborhoodIndex.length} entries)`);

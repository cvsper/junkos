#!/usr/bin/env node

/**
 * Umuve SEO Service×City Page Generator
 * Generates 42 cities × 14 services = 588 long-tail SEO pages
 * Output: pages/junk-removal/{city}-fl/{service}.html
 *
 * Targets keywords like "furniture removal boca raton" and
 * "mattress disposal fort lauderdale" — the same strategy
 * used by 1-800-GOT-JUNK and Junk King.
 */

const fs = require('fs');
const path = require('path');

const cities = require('./data/cities.json');
const services = require('./data/services.json');
const metadata = require('./data/metadata.json');

// --- Helper: pick item from array by deterministic hash ---
function pickByHash(arr, ...seeds) {
    const str = seeds.join('|');
    let hash = 5381;
    for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) + hash + str.charCodeAt(i)) | 0;
    }
    return arr[Math.abs(hash) % arr.length];
}

// --- County-specific charity/donation partners ---
const countyCharities = {
    'Palm Beach': ['Habitat for Humanity of Palm Beach County', 'Palm Beach County Food Bank', 'Goodwill of the Palm Beaches', 'The Arc of Palm Beach County'],
    'Broward': ['Habitat for Humanity of Broward', 'LifeNet4Families', 'Goodwill of South Florida', 'Broward Partnership for the Homeless'],
    'Miami-Dade': ['Habitat for Humanity of Greater Miami', 'Miami Rescue Mission', 'Goodwill of South Florida', 'Chapman Partnership'],
    'Martin': ['Habitat for Humanity of Martin County', 'House of Hope', 'Faith Farm Ministries', 'Salvation Army of Martin County'],
    'St. Lucie': ['Habitat for Humanity of St. Lucie County', 'Mustard Seed Ministries', 'Treasure Coast Food Bank', 'Grace Way Village']
};

// --- County-specific disposal regulations ---
const countyDisposalInfo = {
    'Palm Beach': 'Palm Beach County Solid Waste Authority operates the county landfill and recycling facilities on Jog Road. Residents get 2 free bulk pickups per month through the county, but items must be under 6 feet and 50 lbs.',
    'Broward': 'Broward County Waste and Recycling Services manages disposal through regional transfer stations. Most cities offer bulk pickup but limit to 4-6 items per scheduled pickup, with 2-week lead times.',
    'Miami-Dade': 'Miami-Dade County Department of Solid Waste manages the county landfill and recycling centers. Most municipalities limit bulk pickup to 2 items per week — anything beyond that requires private hauling.',
    'Martin': 'Martin County Solid Waste handles disposal via the Palm City Transfer Station. Bulk waste must be under 4ft in any dimension. Uncovered loads are subject to double tipping fees.',
    'St. Lucie': 'St. Lucie County Baling and Recycling Facility handles all county-wide disposal. Cities like Port St. Lucie and Fort Pierce have strict 2-cubic-yard limits for curbside bulk waste.'
};

// --- Intro templates per service type (6-8 varied templates) ---
const introTemplates = {
    'furniture-removal': [
        (city) => `Looking to get rid of old furniture in ${city.name}? Whether it's a worn-out couch, a bulky dresser that won't fit through the door, or a dining set you're replacing, Umuve makes furniture removal in ${city.name}, FL effortless. Our licensed operators handle everything — from navigating tight hallways and staircases to loading and hauling your unwanted pieces to donation centers or recycling facilities.`,
        (city) => `${city.name} residents trust Umuve for fast, affordable furniture removal. We serve all ${city.name} neighborhoods including ${city.neighborhoods.slice(0, 3).join(', ')}, picking up everything from single recliners to entire rooms of furniture. No phone tag, no waiting — book online and we'll have a local operator at your door, often the same day.`,
        (city) => `${city.localContext ? city.localContext.split('.')[0] + '.' : ''} That means furniture removal in ${city.name} is always in demand. Umuve connects you with local, licensed operators who haul couches, mattresses, dressers, and any furniture you need gone — starting at just $89. We serve ${city.neighborhoods.slice(0, 2).join(', ')} and every corner of ${city.name}.`,
        (city) => `Every year, ${city.name} residents replace thousands of pieces of furniture — and most of it can't go to the curb. ${city.county} County's bulk pickup limits make professional furniture removal a necessity, not a luxury. Umuve's ${city.operators} local operators serve all of ${city.name}, FL with same-day availability and transparent pricing. From ${city.landmarks ? city.landmarks[0] : 'downtown'} to ${city.neighborhoods[city.neighborhoods.length - 1]}, we've got you covered.`,
        (city) => `Moving, remodeling, or just tired of that old couch taking up space in your ${city.name} home? Umuve handles furniture removal across all of ${city.county} County, including ${city.neighborhoods.slice(0, 3).join(', ')}. Our operators are experienced with ${city.name}'s mix of ${city.population > 100000 ? 'high-rises, condos, and single-family homes' : 'condos and single-family homes'} — tight hallways, narrow stairs, and tricky doorways are no problem.`,
        (city) => `Here's the reality for ${city.name} homeowners: ${city.commonScenarios ? city.commonScenarios[0].toLowerCase() : 'old furniture piling up'} is just part of life in South Florida. Umuve makes the solution simple — book online in 3 minutes, and a local operator shows up same-day to haul everything away. ${city.jobsCompleted.toLocaleString()}+ furniture removal jobs completed across ${city.county} County. Starting at $89.`,
        (city) => `Professional furniture removal in ${city.name}, FL doesn't have to cost a fortune. Umuve's local operators start at $89 for single-piece pickup and scale up for full rooms and multi-room cleanouts. We donate usable furniture to ${countyCharities[city.county] ? countyCharities[city.county][0] : 'local charities'} and recycle the rest — 92% of what we collect stays out of landfills. Serving ${city.neighborhoods.join(', ')} and all of ${city.name}.`,
        (city) => `Need furniture removed near ${city.landmarks ? city.landmarks[0] : city.neighborhoods[0]} in ${city.name}? Umuve's operators handle it all: sectionals that won't fit through the door (we'll disassemble on-site), heavy dressers from second-floor bedrooms, dining sets, office desks, and everything in between. ${city.rating}★ rated with ${city.reviewCount} reviews from real ${city.name} customers.`
    ],
    'mattress-disposal': [
        (city) => `Getting rid of an old mattress in ${city.name} shouldn't be a hassle. Florida law prohibits mattress dumping, and most trash services won't take them curbside. Umuve provides same-day mattress disposal in ${city.name}, FL — we pick up from any room, wrap it for transport, and deliver it to specialized recycling facilities where 89% of materials are recovered.`,
        (city) => `Need a mattress removed in ${city.name}? Umuve serves all of ${city.county} County with fast, eco-friendly mattress disposal. Whether it's a king, queen, twin, or memory foam — we'll haul it out of any room, navigate stairs and tight spaces, and recycle the materials responsibly. Starting at just $89.`,
        (city) => `Every year, thousands of mattresses end up illegally dumped across ${city.county} County. Don't be part of the problem — Umuve provides legal, eco-friendly mattress disposal in ${city.name}, FL. We serve ${city.neighborhoods.slice(0, 3).join(', ')} and every neighborhood in the city. Book online in minutes, get pickup same-day.`,
        (city) => `Replacing your mattress in ${city.name}? The new one arrives, but the old one has nowhere to go. ${city.county} County trash services won't take it curbside, and you can't exactly fit a king mattress in your car. Umuve's ${city.name} operators pick up from any room — upstairs, downstairs, tight hallways — and handle proper recycling. ${city.reviewCount} five-star reviews and counting.`,
        (city) => `${city.name} residents near ${city.landmarks ? city.landmarks[0] : city.neighborhoods[0]} — Umuve handles mattress disposal the right way. Florida law requires proper mattress recycling, and we're fully compliant. Same-day pickup from $89. We serve all of ${city.name} including ${city.neighborhoods.slice(0, 2).join(' and ')}, with an average response time of just ${city.avgResponseMinutes} minutes.`,
        (city) => `${city.commonScenarios ? 'Whether it\'s ' + city.commonScenarios[0].toLowerCase() + ' or' : 'Whether it\'s'} simply upgrading your sleep setup, ${city.name} residents need a reliable mattress disposal partner. Umuve picks up mattresses from any floor, any room, any building type across ${city.county} County — and recycles 89% of materials. No curbside dumping, no hassle, no fines.`
    ],
    'appliance-removal': [
        (city) => `Upgrading your kitchen or laundry room in ${city.name}? Old appliances are heavy, awkward, and often contain materials that require special disposal. Umuve handles appliance removal in ${city.name}, FL the right way — including disconnection, careful removal from your home, and EPA-compliant recycling of refrigerants and hazardous components.`,
        (city) => `${city.name} homeowners choose Umuve for appliance removal because we handle the entire process — from disconnecting your old washer, dryer, or refrigerator to hauling it to certified recycling facilities. Serving all ${city.name} neighborhoods with same-day availability and upfront pricing from $89.`,
        (city) => `Old appliances don't belong on the curb in ${city.name} — especially refrigerators, AC units, and anything with refrigerants. ${city.county} County requires EPA-compliant disposal, and fines for violations reach $37,500 per day. Umuve handles it right: disconnection, safe removal, and certified recycling. Serving ${city.neighborhoods.slice(0, 3).join(', ')} and all of ${city.name}.`,
        (city) => `Renovating near ${city.landmarks ? city.landmarks[0] : city.neighborhoods[0]} in ${city.name}? That old fridge, dishwasher, or washer-dryer pair needs professional removal. Umuve's licensed operators disconnect, carry out, and recycle appliances of all sizes — from mini fridges to commercial-grade refrigeration. 95% of materials recovered. Starting at $89.`,
        (city) => `${city.name}'s ${city.population > 100000 ? 'dense housing and active renovation market' : 'active housing market'} means appliance removal is in constant demand. Umuve's ${city.operators} local operators handle everything from single dishwasher pickups to full kitchen appliance swaps. We serve all of ${city.county} County with same-day availability and transparent pricing — no hidden fees.`,
        (city) => `Don't let that dead appliance sit in your ${city.name} garage for another month. ${city.commonScenarios ? city.commonScenarios[0] + ' — and appliance removal is always part of the process.' : 'Appliance removal in ' + city.name + ' is quick and affordable.'} Umuve picks up same-day, handles all disconnection, and ensures EPA-compliant disposal. ${city.rating}★ from ${city.reviewCount} reviews.`
    ],
    'electronics-recycling': [
        (city) => `Don't let old electronics pile up in your ${city.name} home. Florida law prohibits e-waste in regular trash, and electronics contain valuable materials that should be recovered. Umuve provides certified electronics recycling in ${city.name}, FL — we pick up computers, TVs, printers, and all e-waste, ensuring secure data destruction and responsible recycling.`,
        (city) => `${city.name} residents can count on Umuve for convenient, certified electronics recycling. We serve all of ${city.county} County, picking up everything from old laptops and TVs to gaming consoles and office equipment. Every item goes to R2-certified facilities where 96% of materials are recovered.`,
        (city) => `That drawer full of old phones, the closet stuffed with outdated laptops, the garage with three broken printers — ${city.name} households accumulate e-waste fast. Umuve provides certified electronics recycling with secure data destruction across ${city.neighborhoods.slice(0, 3).join(', ')} and all of ${city.name}. Florida law prohibits e-waste in trash — we keep you compliant.`,
        (city) => `Upgrading your home office or gaming setup near ${city.landmarks ? city.landmarks[0] : city.neighborhoods[0]} in ${city.name}? Let Umuve handle the old electronics. We pick up computers, monitors, printers, gaming consoles, and all e-waste with secure data destruction and R2-certified recycling. Same-day service, starting at $89.`,
        (city) => `${city.name}'s ${city.population > 80000 ? 'tech-savvy population' : 'growing community'} generates serious e-waste. Umuve recycles electronics responsibly — no landfill dumping, no data left on drives, no hazardous materials entering the waste stream. We serve all of ${city.county} County with DoD-standard data wiping and certified recycling.`,
        (city) => `Florida makes it illegal to throw TVs, computers, and monitors in the trash — and for good reason. These items contain lead, mercury, and cadmium. Umuve provides legal, certified electronics recycling in ${city.name}, FL. We'll even provide data destruction certificates for businesses. ${city.operators} operators serving all of ${city.name}.`
    ],
    'couch-removal': [
        (city) => `That old couch isn't going to move itself — and in ${city.name}, getting a bulky sofa out of your home can be a real challenge. Umuve specializes in couch removal in ${city.name}, FL. Sectional that won't fit through the door? We'll disassemble it on-site. Second-floor apartment with narrow stairs? We've done thousands of these. Book online and relax.`,
        (city) => `Ready to replace your couch in ${city.name}? Umuve makes old sofa removal simple. We handle sectionals, sleeper sofas, recliners, loveseats, and every type of seating furniture. Serving all ${city.name} neighborhoods including ${city.neighborhoods.slice(0, 3).join(', ')} with same-day pickup from $89.`,
        (city) => `The average American couch weighs 100+ pounds and was never designed to go back through the door it came in. In ${city.name}, Umuve's operators solve that problem daily — disassembling sectionals, navigating tight ${city.population > 100000 ? 'condo hallways and apartment stairwells' : 'hallways and stairwells'}, and hauling everything to donation or recycling. 90% of couches we pick up stay out of landfills.`,
        (city) => `Getting a new couch delivered to your ${city.name} home near ${city.landmarks ? city.landmarks[0] : city.neighborhoods[0]}? Don't let the delivery guys leave before the old one is gone. Umuve provides same-day couch removal across ${city.county} County — book online, we match you with a local operator in ${city.avgResponseMinutes} minutes, and your old sofa disappears.`,
        (city) => `Couches are the #1 item ${city.name} residents call Umuve about — and for good reason. They're too big for the trash, too heavy to move alone, and ${city.county} County bulk pickup won't always take them. We handle it all: pickup from any room, disassembly if needed, and donation to ${countyCharities[city.county] ? countyCharities[city.county][0] : 'local charities'} when possible.`,
        (city) => `${city.commonScenarios ? city.commonScenarios[0] + ' often means old couches need to go.' : 'Old couches pile up fast in South Florida.'} Umuve handles couch removal in ${city.name}, FL from start to finish — we carry, load, haul, and recycle or donate. Serving ${city.neighborhoods.slice(0, 2).join(', ')} and every ${city.name} neighborhood. From $89, same-day service.`
    ],
    'refrigerator-disposal': [
        (city) => `Refrigerator disposal in ${city.name} requires more than just hauling — it requires EPA-compliant refrigerant recovery. Umuve handles the entire process: disconnection, careful removal from your kitchen, transport, and certified recycling. All Freon and refrigerants are safely recovered per federal guidelines. No shortcuts, no environmental risk.`,
        (city) => `Getting rid of an old fridge in ${city.name}? Don't risk fines by improper disposal. Umuve provides EPA-compliant refrigerator disposal across ${city.county} County, handling everything from mini fridges to commercial-grade units. We recover all refrigerants, recycle 95% of materials, and leave your kitchen clean.`,
        (city) => `That dead refrigerator in your ${city.name} garage is more than an eyesore — it's an environmental hazard if not disposed of properly. Freon and other refrigerants require EPA-certified recovery. Umuve handles it all: disconnection, careful removal (yes, even from tight kitchens near ${city.landmarks ? city.landmarks[0] : city.neighborhoods[0]}), and certified recycling. Starting at $89.`,
        (city) => `${city.name} homeowners upgrading their kitchens need EPA-compliant refrigerator disposal. The old fridge can't go curbside, and most trash services won't touch it. Umuve's ${city.operators} local operators handle disconnection, water line removal, careful carry-out, and transport to certified facilities. All refrigerants recovered per Section 608 guidelines. ${city.rating}★ service.`,
        (city) => `Improper refrigerator disposal in ${city.county} County can result in fines up to $37,500 per day per violation. That's not a typo. Umuve ensures full EPA compliance for every fridge we remove in ${city.name} — Freon recovery, materials recycling, and proper documentation. Serving all ${city.name} neighborhoods from $89.`,
        (city) => `From mini fridges in ${city.name} dorm rooms to commercial-grade units in restaurant kitchens, Umuve handles refrigerator disposal at every scale. We disconnect, remove, transport, and recycle — recovering refrigerants and 95% of materials. ${city.jobsCompleted.toLocaleString()}+ jobs across ${city.county} County. Same-day service available.`
    ],
    'hot-tub-removal': [
        (city) => `Removing a hot tub in ${city.name} is no DIY project. These 400-800 pound units require professional demolition, cutting, and hauling. Umuve handles hot tub removal in ${city.name}, FL from start to finish — we drain, disconnect, demolish if needed, and haul every piece away. Your backyard goes from eyesore to open space in a few hours.`,
        (city) => `${city.name}'s warm climate means plenty of hot tubs — and plenty of hot tubs that have seen better days. Umuve provides professional hot tub removal across ${city.county} County. We handle above-ground tubs, in-ground spas, and swim spas. All materials are separated for recycling: acrylic, wood, metals, and electrical components.`,
        (city) => `That cracked, unused hot tub in your ${city.name} backyard isn't just ugly — it's a liability. Standing water attracts mosquitoes, broken shells are a safety hazard, and abandoned tubs tank your property value. Umuve removes hot tubs across ${city.neighborhoods.slice(0, 3).join(', ')} and all of ${city.name} for $299-$799 depending on size.`,
        (city) => `South Florida's heat, humidity, and UV exposure destroy hot tubs faster than anywhere in the country. If your ${city.name} hot tub has reached end-of-life, Umuve handles the full removal: drain, disconnect, cut into manageable sections, haul away, and leave your patio or deck clean. ${city.operators} operators serving all of ${city.county} County.`,
        (city) => `Hot tub removal near ${city.landmarks ? city.landmarks[0] : city.neighborhoods[0]} in ${city.name}? Umuve specializes in it. We handle tricky backyard access — narrow side gates, raised decks, screened enclosures — and cut tubs into sections that fit through any opening. 73% of materials recycled. Average job time: 2-3 hours.`,
        (city) => `${city.name} homeowners are replacing old hot tubs with fire pits, outdoor kitchens, and expanded pool decks. Umuve makes the first step easy — we demolish and remove your old hot tub or spa in a single visit. Serving all of ${city.county} County. Book online in 3 minutes, get a free quote instantly.`
    ],
    'tv-recycling': [
        (city) => `Old TVs can't go in the trash in Florida — and they shouldn't. CRTs contain lead, and flat screens have mercury and other materials requiring proper handling. Umuve provides certified TV recycling and disposal in ${city.name}, FL. We'll even unmount wall-mounted TVs. Every unit goes to R2-certified e-waste facilities.`,
        (city) => `Upgrading your home theater in ${city.name}? Let Umuve handle the old TV. We pick up flat screens, CRT televisions, monitors, projectors, and all display electronics across ${city.county} County. Proper recycling, not landfill dumping — 97% of materials are recovered and processed responsibly.`,
        (city) => `That ancient CRT TV in your ${city.name} garage weighs 80+ pounds and is full of lead — and it's illegal to throw it in the trash. Umuve provides certified TV recycling across ${city.neighborhoods.slice(0, 3).join(', ')} and all of ${city.name}. We handle CRTs, flat screens, monitors, and projection TVs. R2-certified disposal from $89.`,
        (city) => `Florida law prohibits TVs in household trash — fines apply. Umuve ensures ${city.name} residents stay compliant with legal, certified TV recycling. We pick up from any room, unmount wall-mounted TVs, and transport everything to R2-certified facilities. ${city.rating}★ service from ${city.reviewCount} reviews.`,
        (city) => `Flat screen upgrades are happening all over ${city.name} — bigger screens, better resolution, new streaming tech. But what about the old TV? Umuve picks it up same-day, handles wall unmounting if needed, and ensures every component is properly recycled. Serving ${city.landmarks ? 'near ' + city.landmarks[0] + ' and' : ''} all ${city.name} neighborhoods.`,
        (city) => `TV recycling in ${city.name} doesn't have to be complicated. Umuve picks up, transports, and recycles — 97% of materials recovered at R2-certified facilities. We accept CRTs (yes, even the massive old tube TVs), flat screens, monitors, and projection TVs. ${city.operators} operators serving all of ${city.county} County from $89.`
    ],
    'construction-debris': [
        (city) => `Renovating in ${city.name}? Construction debris piles up fast — drywall, lumber, tile, concrete, and old fixtures. Umuve provides fast construction debris removal in ${city.name}, FL for homeowners and contractors alike. We load everything, separate recyclables, and haul it to licensed facilities. No dumpster rental needed.`,
        (city) => `${city.name} contractors and homeowners trust Umuve for construction debris removal. Whether you're demo-ing a bathroom, gutting a kitchen, or clearing a full renovation site, we handle drywall, lumber, tile, concrete, carpet, and all construction waste. Serving all of ${city.county} County with same-day availability.`,
        (city) => `${city.localContext ? city.localContext.split('.')[0] + '.' : ''} All that renovation activity in ${city.name} means construction debris needs to go somewhere — and fast. Umuve's operators load, haul, and sort debris for recycling. No dumpster rental, no permits, no waiting. From $149.`,
        (city) => `Dumpster rentals in ${city.name} cost $350-$600, require city permits ($50-$150), sit in your driveway for days, and you still have to do the loading yourself. Umuve shows up same-day, loads everything, hauls it away, and sorts recyclables — all for competitive pricing. Serving ${city.neighborhoods.slice(0, 3).join(', ')} and all of ${city.name}.`,
        (city) => `Contractors working in ${city.name} near ${city.landmarks ? city.landmarks[0] : city.neighborhoods[0]} — Umuve is your debris removal partner. We offer same-day pickup, recurring schedules for ongoing projects, and competitive rates for regular contractors in ${city.county} County. ${city.jobsCompleted.toLocaleString()}+ jobs completed and counting.`,
        (city) => `${city.commonScenarios ? city.commonScenarios.find(s => s.toLowerCase().includes('debris') || s.toLowerCase().includes('renovation') || s.toLowerCase().includes('construction')) || 'Renovation projects across ' + city.name : 'Renovation projects across ' + city.name} — Umuve handles the aftermath. We pick up drywall, lumber, tile, concrete, carpet, old cabinets, and all construction waste. 78% recycled. Serving all of ${city.county} County.`
    ],
    'yard-waste-removal': [
        (city) => `South Florida's tropical climate means ${city.name} homeowners deal with yard waste year-round — palm fronds, fallen branches, hedge trimmings, and storm debris. Umuve provides fast yard waste removal in ${city.name}, FL. We load everything, from small brush piles to large fallen trees, and compost or mulch 98% of green waste.`,
        (city) => `After a landscaping project or storm cleanup in ${city.name}, the last thing you want is a mountain of yard waste with nowhere to put it. Umuve handles yard waste removal across ${city.county} County — branches, leaves, sod, palm fronds, and all green debris. 98% composted or mulched. Zero landfill.`,
        (city) => `${city.name}'s tropical vegetation doesn't take a break — and neither do we. Palm fronds, fallen branches, hedge clippings, and storm debris are year-round realities in ${city.neighborhoods.slice(0, 2).join(' and ')}. Umuve provides same-day yard waste removal across all of ${city.name}, FL. Everything gets composted or mulched — zero green waste to landfill.`,
        (city) => `Hurricane season hits ${city.name} hard, and when it does, yard waste is the first problem and the most urgent. But even without storms, South Florida's aggressive tropical growth means ${city.name} homeowners face constant trimming, pruning, and debris. Umuve handles it all — from a few bags of clippings to truckloads of fallen trees. From $89.`,
        (city) => `Just finished a landscaping project near ${city.landmarks ? city.landmarks[0] : city.neighborhoods[0]} in ${city.name}? Umuve picks up the mess — branches, sod, palm fronds, hedge trimmings, and all green debris. 98% composted or mulched at licensed facilities. ${city.operators} operators serving ${city.name} with ${city.avgResponseMinutes}-minute average response.`,
        (city) => `${city.commonScenarios ? city.commonScenarios.find(s => s.toLowerCase().includes('yard') || s.toLowerCase().includes('storm') || s.toLowerCase().includes('debris') || s.toLowerCase().includes('tree')) || 'Yard waste from tropical landscaping' : 'Yard waste from tropical landscaping'} is a way of life in ${city.name}. Umuve turns that problem into a non-issue — same-day removal, 98% composting/mulching rate, zero landfill. Serving all of ${city.county} County.`
    ],
    'garage-cleanout': [
        (city) => `Can't park in your garage anymore? You're not alone — ${city.name} homeowners accumulate years of stuff in their garages. Umuve provides complete garage cleanout services in ${city.name}, FL. We sort, load, haul, and even sweep the floor. Usable items get donated, recyclables get recycled, and you get your garage back.`,
        (city) => `A full garage cleanout in ${city.name} can feel overwhelming, but Umuve makes it simple. Our operators sort through everything, separate items for donation and recycling, load up the truck, and leave your garage broom-clean. Serving all ${city.name} neighborhoods with transparent pricing from $149.`,
        (city) => `The average ${city.name} garage hasn't seen a car in years. Between the old bikes, holiday decorations, broken tools, and boxes from three moves ago, there's no room left. Umuve's garage cleanout service in ${city.name} handles everything — we sort, donate what's usable to ${countyCharities[city.county] ? countyCharities[city.county][0] : 'local charities'}, recycle what we can, and haul the rest.`,
        (city) => `${city.name} families near ${city.landmarks ? city.landmarks[0] : city.neighborhoods[0]} — reclaim your garage. Umuve's complete cleanout service includes sorting (we'll set aside anything you want to keep), loading, hauling, and sweeping. Average time: 2-4 hours. Average cost: $249 for a single-car garage. You'll wonder why you waited so long.`,
        (city) => `Garage cleanouts are Umuve's bread and butter in ${city.name}. We've cleaned out thousands of garages across ${city.county} County — from single-car units packed to the ceiling to double-car garages that haven't been organized in a decade. ${city.rating}★ service, transparent pricing, and a broom-clean finish every time.`,
        (city) => `${city.commonScenarios ? city.commonScenarios.find(s => s.toLowerCase().includes('garage')) || 'Packed garages in ' + city.name : 'Packed garages in ' + city.name} — sound familiar? Umuve provides same-day garage cleanout across all ${city.name} neighborhoods. We sort everything, donate usable items, recycle responsibly, and leave your floor swept. Starting at $149.`
    ],
    'estate-cleanout': [
        (city) => `Handling an estate cleanout in ${city.name} is emotionally and physically demanding. Umuve provides compassionate, professional estate cleanout services across ${city.county} County. We work with families, executors, and attorneys to clear entire homes with care — sorting valuables, donating usable items, and disposing of the rest responsibly.`,
        (city) => `When a loved one's ${city.name} home needs to be cleared, Umuve is here to help. Our experienced team handles full estate cleanouts with dignity and efficiency. We sort, donate, recycle, and haul — leaving the property clean and ready for sale or new occupants. Serving all of ${city.county} County.`,
        (city) => `Estate cleanouts in ${city.name} require patience, sensitivity, and professional capability. Umuve's operators understand the emotional weight of clearing a family home in ${city.neighborhoods.slice(0, 2).join(' or ')}. We work at your pace, set aside items you want to keep, donate to ${countyCharities[city.county] ? countyCharities[city.county][0] : 'local charities'}, and handle everything else. 84% donated or recycled.`,
        (city) => `${city.name}'s ${city.population > 100000 ? 'large and diverse population' : 'community'} means estate cleanouts are a regular necessity. Whether it's a ${city.population > 100000 ? 'high-rise condo' : 'family home'} in ${city.neighborhoods[0]} or a house in ${city.neighborhoods[city.neighborhoods.length - 1]}, Umuve handles the entire process — from walk-through assessment to final sweep. We coordinate with executors, attorneys, and real estate agents throughout ${city.county} County.`,
        (city) => `${city.commonScenarios ? city.commonScenarios.find(s => s.toLowerCase().includes('estate') || s.toLowerCase().includes('downsizing') || s.toLowerCase().includes('senior')) || 'Estate cleanouts in ' + city.name : 'Estate cleanouts in ' + city.name} — Umuve has done hundreds across ${city.county} County. Our compassionate operators sort, donate, recycle, and haul with care. From $399 for small apartments to $3,500+ for large estates. Every job leaves the property broom-clean and move-in ready.`,
        (city) => `Preparing a ${city.name} property for sale after a family transition? Umuve's estate cleanout service clears the entire home — furniture, appliances, personal items, garage, attic, everything. We work with ${city.county} County real estate agents and property managers to get properties market-ready fast. ${city.jobsCompleted.toLocaleString()}+ jobs completed in the area.`
    ],
    'office-commercial-cleanout': [
        (city) => `Moving offices, downsizing, or closing a ${city.name} business location? Umuve handles office and commercial cleanouts across ${city.county} County. We remove desks, cubicles, filing cabinets, IT equipment, and warehouse fixtures — often after-hours to minimize business disruption. Secure document shredding available on request.`,
        (city) => `${city.name} businesses trust Umuve for professional office cleanouts. Whether you're clearing one floor or an entire building, we handle it all — furniture, electronics, fixtures, and inventory. We work with property managers, landlords, and business owners to get spaces cleared fast and clean.`,
        (city) => `Commercial junk removal in ${city.name} has unique requirements — after-hours access, secure document destruction, and minimal disruption to surrounding tenants. Umuve handles it all. We serve ${city.landmarks ? 'the ' + city.landmarks[0] + ' area,' : ''} ${city.neighborhoods.slice(0, 2).join(', ')}, and all commercial zones in ${city.name}. From $299.`,
        (city) => `Office lease ending in ${city.name}? Landlord demanding a broom-clean space? Umuve's commercial cleanout team removes everything — desks, chairs, cubicles, servers, filing cabinets, break room furniture — and leaves your space move-out ready. After-hours and weekend scheduling available across ${city.county} County.`,
        (city) => `${city.name}'s ${city.population > 100000 ? 'active commercial real estate market' : 'business community'} means office and retail spaces turn over regularly. Umuve provides professional commercial cleanouts with secure IT equipment disposal, document shredding, and after-hours scheduling. ${city.operators} operators serving all of ${city.county} County.`,
        (city) => `From single offices near ${city.landmarks ? city.landmarks[0] : city.neighborhoods[0]} to entire ${city.name} warehouse cleanouts, Umuve handles commercial junk at every scale. Secure document shredding (FACTA/HIPAA compliant), R2-certified electronics recycling, and after-hours scheduling included. Get a free quote in 3 minutes.`
    ],
    'dumpster-alternative': [
        (city) => `Why rent a dumpster in ${city.name} when Umuve does all the work for you? No permits, no HOA headaches, no driveway damage, no waiting 3-5 days for pickup. We show up same-day, load everything ourselves, and haul it all away in one visit. Often cheaper than a dumpster rental when you factor in your time and labor.`,
        (city) => `${city.name} residents are switching from dumpster rentals to Umuve — and saving time, money, and hassle. A dumpster sits in your driveway for days. We come same-day, do all the loading, haul everything, and you're done in hours. No permits needed. No HOA violations. No back-breaking labor.`,
        (city) => `A dumpster rental in ${city.name} costs $350-$600, needs a city permit ($50-$150), blocks your driveway for days, risks HOA fines, and you still have to load it yourself. Or — Umuve shows up same-day, loads everything, and hauls it away in one visit. Same result, less money, zero effort. Serving all of ${city.county} County.`,
        (city) => `${city.name} HOAs hate dumpsters in driveways. ${city.county} County requires permits for street-placed dumpsters. And loading a dumpster yourself in South Florida heat? No thanks. Umuve is the smarter alternative — same-day service, we do all the labor, and your neighbors never see an ugly dumpster. From $149.`,
        (city) => `For ${city.name} renovation projects, cleanouts, and decluttering, Umuve beats dumpster rentals every time. We load everything (you don't lift a finger), we sort recyclables and donations, and we're done in hours — not days. Serving ${city.neighborhoods.slice(0, 3).join(', ')} and all of ${city.name}. ${city.reviewCount} five-star reviews.`,
        (city) => `${city.commonScenarios ? city.commonScenarios[0] : 'Big cleanout projects in ' + city.name} — you need hauling power, not a dumpster. Umuve's trucks hold up to 15 cubic yards (equivalent to a 15-20 yard dumpster) and we do ALL the loading. Same-day service, no permits, no HOA violations. The smarter way to haul in ${city.name}.`
    ]
};

// --- Service-specific pricing descriptions ---
const pricingByService = {
    'furniture-removal': [
        { label: 'Single Piece', desc: 'One couch, dresser, table, etc.', price: '$89' },
        { label: '2-3 Pieces', desc: 'Small room set or a few items', price: '$149' },
        { label: 'Full Room', desc: 'Bedroom, living room, or dining set', price: '$249', popular: true },
        { label: 'Multi-Room', desc: 'Multiple rooms or large move-out', price: '$399' },
        { label: 'Whole House', desc: 'Complete furniture removal', price: '$499+' }
    ],
    'mattress-disposal': [
        { label: 'Single Mattress', desc: 'Twin, full, or queen mattress', price: '$89' },
        { label: 'Mattress + Box Spring', desc: 'Standard set removal', price: '$119', popular: true },
        { label: 'King Set', desc: 'King mattress + box spring', price: '$139' },
        { label: 'Multiple Mattresses', desc: '2-3 mattresses or beds', price: '$179' },
        { label: 'Full Bedroom Set', desc: 'Mattress, frame, furniture', price: '$249+' }
    ],
    'appliance-removal': [
        { label: 'Single Appliance', desc: 'Washer, dryer, dishwasher, etc.', price: '$89' },
        { label: '2 Appliances', desc: 'Washer/dryer pair or similar', price: '$139', popular: true },
        { label: '3-4 Appliances', desc: 'Kitchen or laundry upgrade', price: '$199' },
        { label: 'Large Appliance', desc: 'Commercial fridge, walk-in unit', price: '$249' },
        { label: 'Full Kitchen', desc: 'All kitchen appliances', price: '$299+' }
    ],
    'electronics-recycling': [
        { label: 'Small Load', desc: 'Few devices, cables, accessories', price: '$89' },
        { label: 'Medium Load', desc: 'Computer, monitor, printer combo', price: '$119', popular: true },
        { label: 'Office Cleanout', desc: '5-10 devices, IT equipment', price: '$199' },
        { label: 'Large Cleanout', desc: '10+ devices, server equipment', price: '$249' },
        { label: 'Full IT Disposal', desc: 'Complete office e-waste', price: '$299+' }
    ],
    'couch-removal': [
        { label: 'Single Couch', desc: 'Standard sofa or loveseat', price: '$89' },
        { label: 'Sectional Sofa', desc: 'L-shape or U-shape sectional', price: '$139', popular: true },
        { label: 'Couch + Recliner', desc: 'Living room pair', price: '$149' },
        { label: 'Full Living Room', desc: 'Sofa set + extras', price: '$219' },
        { label: 'Multiple Rooms', desc: 'Several couches throughout home', price: '$299+' }
    ],
    'refrigerator-disposal': [
        { label: 'Mini Fridge', desc: 'Compact or dorm fridge', price: '$89' },
        { label: 'Standard Fridge', desc: 'Top or bottom freezer model', price: '$119', popular: true },
        { label: 'Large Fridge', desc: 'Side-by-side or French door', price: '$149' },
        { label: 'Fridge + Freezer', desc: 'Separate fridge and freezer units', price: '$199' },
        { label: 'Commercial Unit', desc: 'Restaurant or commercial grade', price: '$249+' }
    ],
    'hot-tub-removal': [
        { label: 'Small Spa', desc: '2-3 person portable hot tub', price: '$299' },
        { label: 'Standard Hot Tub', desc: '4-6 person above-ground', price: '$399', popular: true },
        { label: 'Large Hot Tub', desc: '7+ person or swim spa', price: '$549' },
        { label: 'In-Ground Spa', desc: 'Built-in spa with demolition', price: '$649' },
        { label: 'Hot Tub + Deck', desc: 'Tub removal + deck demolition', price: '$799+' }
    ],
    'tv-recycling': [
        { label: 'Single TV', desc: 'One flat screen or CRT', price: '$89' },
        { label: '2-3 TVs', desc: 'Multiple screens and monitors', price: '$119', popular: true },
        { label: 'Home Theater', desc: 'TV, speakers, equipment', price: '$149' },
        { label: 'Office Monitors', desc: '5-10 displays', price: '$199' },
        { label: 'Bulk E-Waste', desc: 'Large volume of screens', price: '$249+' }
    ],
    'construction-debris': [
        { label: 'Small Load', desc: 'Bathroom demo, minor reno', price: '$149' },
        { label: 'Quarter Truck', desc: 'Kitchen backsplash, flooring', price: '$199' },
        { label: 'Half Truck', desc: 'Full bathroom or room reno', price: '$325', popular: true },
        { label: 'Three-Quarter', desc: 'Kitchen gut or multi-room', price: '$499' },
        { label: 'Full Truck', desc: 'Major renovation or addition', price: '$699+' }
    ],
    'yard-waste-removal': [
        { label: 'Small Pile', desc: 'Few bags or small brush pile', price: '$89' },
        { label: 'Medium Load', desc: 'Post-landscaping cleanup', price: '$149', popular: true },
        { label: 'Large Load', desc: 'Tree trimming, major cleanup', price: '$249' },
        { label: 'Storm Cleanup', desc: 'Post-hurricane or storm debris', price: '$399' },
        { label: 'Full Property', desc: 'Complete lot clearing', price: '$499+' }
    ],
    'garage-cleanout': [
        { label: 'Partial Cleanout', desc: 'One wall or section', price: '$149' },
        { label: 'Single Car Garage', desc: 'Full single-car cleanout', price: '$249', popular: true },
        { label: 'Double Car Garage', desc: 'Full two-car cleanout', price: '$399' },
        { label: 'Garage + Attic', desc: 'Garage and attic combined', price: '$499' },
        { label: 'Garage + Shed', desc: 'Garage, shed, outdoor storage', price: '$599+' }
    ],
    'estate-cleanout': [
        { label: '1-Bedroom', desc: 'Apartment or small condo', price: '$399' },
        { label: '2-Bedroom', desc: 'Standard condo or apartment', price: '$799' },
        { label: '3-Bedroom', desc: 'Single-family home', price: '$1,240', popular: true },
        { label: '4+ Bedroom', desc: 'Large home, full cleanout', price: '$1,800' },
        { label: 'Estate + Storage', desc: 'Home + storage unit', price: '$2,500+' }
    ],
    'office-commercial-cleanout': [
        { label: 'Single Office', desc: 'One office or small suite', price: '$299' },
        { label: 'Small Suite', desc: '2-4 offices, reception area', price: '$599', popular: true },
        { label: 'Full Floor', desc: 'Complete office floor', price: '$995' },
        { label: 'Multi-Floor', desc: 'Multiple floors or large space', price: '$1,500' },
        { label: 'Warehouse', desc: 'Warehouse or retail space', price: '$2,500+' }
    ],
    'dumpster-alternative': [
        { label: 'Small Load', desc: 'Equivalent of 10-yard dumpster', price: '$149' },
        { label: 'Medium Load', desc: 'Equivalent of 15-yard dumpster', price: '$249', popular: true },
        { label: 'Large Load', desc: 'Equivalent of 20-yard dumpster', price: '$399' },
        { label: 'XL Load', desc: 'Equivalent of 30-yard dumpster', price: '$499' },
        { label: 'Full Truck', desc: 'Equivalent of 40-yard dumpster', price: '$599+' }
    ]
};

// --- Service-specific FAQ generators (city-enriched) ---
function getServiceCityFAQs(service, city) {
    const charities = countyCharities[city.county] || countyCharities['Palm Beach'];
    const localCharity = charities[0];
    const secondCharity = charities[1];
    const localTipText = city.localTip || `${city.name} residents can count on Umuve for fast, reliable service.`;
    const landmark = city.landmarks ? city.landmarks[0] : city.neighborhoods[0];

    const baseFAQs = {
        'furniture-removal': [
            { q: `How much does furniture removal cost in ${city.name}, FL?`, a: `Furniture removal in ${city.name} starts at $89 for a single piece. A full living room set averages $249. Pricing depends on the number of items, size, and accessibility. Get an instant quote online — no phone call needed. ${localTipText}` },
            { q: `Do you disassemble furniture in ${city.name}?`, a: `Yes. Our ${city.name} operators will disassemble beds, sectionals, desks, and other furniture that won't fit through doorways. Disassembly is included in the price at no extra charge. We handle tricky removals in ${city.neighborhoods.slice(0, 2).join(' and ')} every day.` },
            { q: `Can you remove furniture from upstairs in ${city.name}?`, a: `Absolutely. Our operators handle stairs, narrow hallways, elevators, and tight spaces every day across ${city.county} County — from ${landmark} to ${city.neighborhoods[city.neighborhoods.length - 1]}. No extra charge for stairs in most cases.` },
            { q: `Where does my old furniture go after removal?`, a: `We partner with ${localCharity}, ${secondCharity}, and local charities in ${city.county} County. Usable furniture is donated. Damaged pieces are recycled for materials. 92% of furniture we collect stays out of landfills. ${city.name} residents can feel good about responsible disposal.` }
        ],
        'mattress-disposal': [
            { q: `How much does mattress disposal cost in ${city.name}?`, a: `Mattress disposal in ${city.name} starts at $89 for a single mattress. A mattress and box spring set is typically $119. King sets run $139. All prices include pickup from any room and eco-friendly recycling.` },
            { q: `Can you pick up a mattress the same day in ${city.name}?`, a: `Yes. Umuve offers same-day mattress pickup across ${city.county} County. Book before noon and we'll typically have an operator at your ${city.name} address the same day. Average match time near ${landmark}: ${city.avgResponseMinutes} minutes.` },
            { q: `How do you recycle mattresses?`, a: `Mattresses are taken to specialized recycling facilities where they're disassembled. Steel springs are melted down, foam is repurposed for carpet padding, and fabric is processed into fiber. 89% of materials are recovered. ${city.county} County facilities handle all mattress recycling compliantly.` },
            { q: `Is it legal to dump a mattress in ${city.name}?`, a: `No. Illegal dumping in ${city.county} County carries fines up to $500 for first offenses and increases from there. ${localTipText} Umuve ensures your mattress is disposed of legally and responsibly.` }
        ],
        'appliance-removal': [
            { q: `How much does appliance removal cost in ${city.name}?`, a: `Appliance removal in ${city.name} starts at $89 for a single appliance. A washer/dryer pair is typically $139. Full kitchen appliance removal averages $299. All prices include disconnection and eco-friendly disposal.` },
            { q: `Do you disconnect appliances in ${city.name}?`, a: `Yes. Our operators can disconnect most standard appliances including washers, dryers, refrigerators, and dishwashers. For gas appliance disconnection or complex electrical work, we recommend hiring a licensed plumber or electrician first. We serve all ${city.name} neighborhoods.` },
            { q: `Do you handle refrigerant removal from appliances?`, a: `Absolutely. All refrigerant-containing appliances (refrigerators, AC units, dehumidifiers) are transported to EPA-certified facilities where refrigerants are properly recovered per Section 608 guidelines. Full compliance guaranteed in ${city.county} County.` },
            { q: `What happens to old appliances after removal?`, a: `95% of appliance materials are recycled. Metals (steel, copper, aluminum) are melted down, plastics are processed, and refrigerants are recovered. We use certified recycling facilities throughout ${city.county} County. Usable appliances are donated to ${localCharity}.` }
        ],
        'electronics-recycling': [
            { q: `How much does electronics recycling cost in ${city.name}?`, a: `Electronics recycling in ${city.name} starts at $89 for a small load. A standard computer, monitor, and printer combo is typically $119. Office IT cleanouts start at $199. All items go to R2-certified recyclers serving ${city.county} County.` },
            { q: `Do you wipe hard drives before recycling?`, a: `Yes. We offer secure data destruction for all storage devices. Hard drives can be wiped using DoD-standard methods or physically destroyed. Data destruction certificates are available upon request — essential for ${city.name} businesses handling sensitive data.` },
            { q: `Is it illegal to throw away electronics in Florida?`, a: `Yes. Florida prohibits TVs, computers, and certain electronics from regular household trash due to hazardous materials like lead, mercury, and cadmium. ${city.county} County enforces these regulations. Umuve ensures full compliance for ${city.name} residents and businesses.` },
            { q: `What electronics do you accept in ${city.name}?`, a: `We accept virtually all electronics: computers, laptops, TVs, monitors, printers, phones, tablets, gaming consoles, stereo equipment, cables, and small appliances. The only items we can't take are smoke detectors and certain industrial equipment. We serve all of ${city.name} including ${city.neighborhoods.slice(0, 3).join(', ')}.` }
        ],
        'couch-removal': [
            { q: `How much does couch removal cost in ${city.name}?`, a: `Couch removal in ${city.name} starts at $89 for a standard sofa or loveseat. Sectionals average $139. A full living room set runs $219. All prices include labor, loading, hauling, and disposal — no hidden fees.` },
            { q: `Can you remove a sectional from a second floor?`, a: `Yes. Our ${city.name} operators specialize in navigating large furniture through tight spaces — whether it's a ${city.population > 100000 ? 'high-rise condo hallway' : 'narrow staircase'} in ${city.neighborhoods[0]} or a tricky doorway in ${city.neighborhoods[1]}. If a sectional won't fit through the door, we'll disassemble it on-site at no extra charge.` },
            { q: `Do you donate couches in good condition?`, a: `Absolutely. Gently used couches are donated to ${localCharity}, ${secondCharity}, and local shelters in ${city.county} County. 90% of the couches we pick up are donated or recycled — not landfilled.` },
            { q: `How fast can I get a couch removed in ${city.name}?`, a: `Umuve offers same-day couch removal across ${city.county} County. Book before noon for same-day service. Average operator matching time in ${city.name} is ${city.avgResponseMinutes} minutes. We serve all neighborhoods from ${city.neighborhoods[0]} to ${city.neighborhoods[city.neighborhoods.length - 1]}.` }
        ],
        'refrigerator-disposal': [
            { q: `How much does refrigerator disposal cost in ${city.name}?`, a: `Refrigerator disposal in ${city.name} starts at $89 for a mini fridge. Standard refrigerators are $119-$149 depending on size. French door and commercial units run up to $249. All prices include disconnection and EPA-compliant recycling.` },
            { q: `Do you handle Freon removal in ${city.name}?`, a: `Yes. All refrigerant-containing units are transported to EPA-certified facilities where Freon, R-134a, and other refrigerants are safely recovered per federal Section 608 guidelines. This is included in our service for all ${city.name} and ${city.county} County pickups — no extra charge.` },
            { q: `Can you disconnect my water line?`, a: `Yes. Our operators can disconnect standard water lines for refrigerators with ice makers or water dispensers. We'll also turn off the water supply valve to prevent leaks. Serving all ${city.name} neighborhoods including ${city.neighborhoods.slice(0, 3).join(', ')}.` },
            { q: `Is it illegal to dump a refrigerator in Florida?`, a: `Yes. Improper refrigerator disposal violates EPA regulations due to refrigerants and insulating foams. Fines can reach $37,500 per day per violation in ${city.county} County. ${localTipText} Umuve ensures full regulatory compliance for every unit we remove in ${city.name}.` }
        ],
        'hot-tub-removal': [
            { q: `How much does hot tub removal cost in ${city.name}?`, a: `Hot tub removal in ${city.name} starts at $299 for a small portable spa. Standard 4-6 person hot tubs average $399. Large or in-ground spas run $549-$799. Pricing includes demolition, removal, hauling, and disposal.` },
            { q: `Do you disconnect plumbing and electrical?`, a: `We disconnect standard plumbing connections. For hardwired electrical, we recommend having a licensed electrician disconnect the power before our arrival. This ensures safety and code compliance in ${city.county} County.` },
            { q: `How do you remove hot tubs from backyards?`, a: `We disassemble the hot tub on-site, cutting it into manageable sections. The pieces are carried out through standard gates, side yards, or over fences if needed. We've removed hot tubs from backyards across ${city.neighborhoods.slice(0, 3).join(', ')} and all of ${city.name}.` },
            { q: `How long does hot tub removal take in ${city.name}?`, a: `Most hot tub removals take 2-3 hours from start to finish. This includes draining, demolition (if needed), loading, and cleanup. In-ground spas may take longer depending on construction. ${localTipText}` }
        ],
        'tv-recycling': [
            { q: `How much does TV recycling cost in ${city.name}?`, a: `TV recycling in ${city.name} starts at $89 for a single TV. Multiple TVs and monitors are $119. A full home theater system (TV + equipment) is typically $149. All items go to R2-certified e-waste facilities serving ${city.county} County.` },
            { q: `Do you accept CRT TVs in ${city.name}?`, a: `Yes. We accept CRT (tube) TVs of all sizes — even those 200-pound monsters from the 90s. CRTs require special handling due to lead content, which is why they can't go in regular trash. We ensure proper recycling at certified facilities near ${city.name}.` },
            { q: `Can you unmount a wall-mounted TV?`, a: `Yes. Our operators will safely unmount wall-mounted TVs, remove brackets, and patch the wall if you provide patching supplies. Wall unmounting is included in the service price. We handle wall-mounted TVs in ${city.neighborhoods.slice(0, 2).join(' and ')} and across ${city.name} daily.` },
            { q: `Is it illegal to throw away TVs in Florida?`, a: `Yes. Florida law prohibits TVs and monitors from household waste due to hazardous materials including lead (CRTs) and mercury (flat screens). ${city.county} County enforces this strictly. Umuve ensures every TV is properly recycled per state and federal regulations.` }
        ],
        'construction-debris': [
            { q: `How much does construction debris removal cost in ${city.name}?`, a: `Construction debris removal in ${city.name} starts at $149 for a small load (bathroom demo). A half-truck load for a full room renovation averages $325. Full truck loads for major projects run $699+. All prices include loading and hauling. ${localTipText}` },
            { q: `Do you work with contractors in ${city.name}?`, a: `Yes. Many ${city.county} County contractors use Umuve as their go-to debris removal service. We offer recurring pickup schedules, same-day availability, and competitive rates for contractors working in ${city.neighborhoods.slice(0, 2).join(', ')} and across ${city.name}.` },
            { q: `Do you accept hazardous construction materials?`, a: `We do NOT accept asbestos, lead paint, or hazardous chemicals. We handle standard construction debris: drywall, lumber, tile, concrete, carpet, cabinets, and fixtures. For hazardous materials in ${city.county} County, we can recommend certified disposal services.` },
            { q: `Is Umuve cheaper than a dumpster for construction debris?`, a: `Often yes. When you factor in dumpster rental fees ($300-$600), permit costs ($50-$150 in ${city.name}), delivery/pickup wait times, and your own loading labor, Umuve's all-inclusive pricing frequently comes out ahead — especially for jobs near ${landmark} where dumpster placement is restricted.` }
        ],
        'yard-waste-removal': [
            { q: `How much does yard waste removal cost in ${city.name}?`, a: `Yard waste removal in ${city.name} starts at $89 for a small pile. Post-landscaping cleanup averages $149. Large loads (tree trimming, storm cleanup) run $249-$499. All green waste is composted or mulched — zero landfill.` },
            { q: `Do you haul hurricane debris in ${city.name}?`, a: `Yes. Umuve provides storm debris removal across ${city.county} County. After major storms, we scale up operations to help ${city.name} residents clear fallen trees, palm fronds, fencing, and other hurricane damage as quickly as possible. ${city.name}'s ${city.landmarks ? city.landmarks[0] + ' area and' : ''} all neighborhoods are covered.` },
            { q: `Can you remove tree stumps?`, a: `We remove above-ground tree debris including trunks and large branches. For stump grinding or root removal, we recommend a tree service specialist. We can haul away the debris they leave behind. This is a common service pairing for ${city.name} homeowners.` },
            { q: `Do you compost yard waste?`, a: `Yes. 98% of yard waste we collect is composted or processed into mulch at licensed green waste facilities in ${city.county} County. This includes branches, leaves, grass clippings, palm fronds, and sod. Zero green waste goes to landfills. ${localTipText}` }
        ],
        'garage-cleanout': [
            { q: `How much does a garage cleanout cost in ${city.name}?`, a: `Garage cleanout in ${city.name} starts at $149 for a partial cleanout. A full single-car garage averages $249. Double-car garages run $399. All prices include sorting, loading, hauling, and floor sweeping.` },
            { q: `How long does a garage cleanout take?`, a: `A single-car garage cleanout typically takes 2-3 hours. Double-car garages take 3-4 hours. This includes sorting items, loading the truck, and sweeping the floor clean. Our operators in ${city.neighborhoods.slice(0, 2).join(' and ')} handle these daily.` },
            { q: `Can I keep some items while you remove the rest?`, a: `Absolutely. Our operators will work with you to identify what stays and what goes. We can also help organize what you're keeping while we clear out the rest. ${localTipText}` },
            { q: `What about paint cans and chemicals in the garage?`, a: `We can remove sealed, non-leaking paint cans and household chemicals. Open, leaking, or hazardous materials require special disposal — we'll let you know during the cleanout and recommend proper disposal options in ${city.county} County.` }
        ],
        'estate-cleanout': [
            { q: `How much does an estate cleanout cost in ${city.name}?`, a: `Estate cleanout in ${city.name} starts at $399 for a small apartment. A standard 3-bedroom home averages $1,240. Large estates run $1,800-$3,500. Pricing depends on the home's size, contents volume, and any special requirements.` },
            { q: `How long does an estate cleanout take?`, a: `Most estate cleanouts in ${city.name} take 4-8 hours for a standard home. Larger properties or heavily packed homes may require 1-2 days. We'll provide a timeline estimate during our walk-through assessment. Properties in ${city.neighborhoods.slice(0, 2).join(' and ')} typically fall in the standard range.` },
            { q: `Do you work with executors and families?`, a: `Yes. We work directly with families, executors, attorneys, and real estate agents throughout ${city.county} County. Our team handles everything with sensitivity and can set aside items families want to keep. We also coordinate with ${localCharity} for donations.` },
            { q: `What happens to valuables during an estate cleanout?`, a: `Before we begin, we do a walk-through with you to identify items to keep, donate, or dispose of. We set aside anything of value for the family. Usable items go to ${localCharity} and ${secondCharity}. We handle the rest with care. ${localTipText}` }
        ],
        'office-commercial-cleanout': [
            { q: `How much does an office cleanout cost in ${city.name}?`, a: `Office cleanout in ${city.name} starts at $299 for a single office. Small suites average $599. Full floor cleanouts run $995+. Pricing depends on square footage, furniture volume, and IT equipment. We offer after-hours scheduling at no extra charge.` },
            { q: `Do you offer after-hours service in ${city.name}?`, a: `Yes. We understand business operations can't stop for a cleanout. We offer evening and weekend scheduling for businesses near ${landmark} and across ${city.county} County to minimize disruption to your team and customers.` },
            { q: `Can you handle secure document destruction?`, a: `Yes. We provide secure on-site or off-site document shredding services. Certificates of destruction are available upon request. All shredding complies with FACTA and HIPAA requirements — critical for ${city.name} businesses handling sensitive data.` },
            { q: `Do you work with property managers?`, a: `Absolutely. We work with property managers, landlords, and commercial real estate agents throughout ${city.name} and ${city.county} County. We can handle tenant cleanouts, pre-lease preparation, and ongoing commercial waste removal. ${localTipText}` }
        ],
        'dumpster-alternative': [
            { q: `Is Umuve cheaper than renting a dumpster in ${city.name}?`, a: `Often yes. A 20-yard dumpster rental in ${city.name} costs $350-$550 plus a $50-$150 permit, plus your loading labor, plus 3-5 day wait. Umuve's equivalent half-truck load is $249 all-inclusive, same-day, and we do all the work. Near ${landmark}, where dumpster placement is restricted, we're the only realistic option.` },
            { q: `Do I need a permit for Umuve's service?`, a: `No. Unlike dumpster rentals, Umuve's junk removal service requires zero permits in ${city.name} or anywhere in ${city.county} County. We pull up, load, and leave. No city approvals, no HOA complaints, no driveway damage. ${localTipText}` },
            { q: `How much can Umuve haul in one trip?`, a: `Our trucks hold up to 15 cubic yards — equivalent to about 9 pickup truck loads. That's comparable to a 15-20 yard dumpster. For larger projects in ${city.name}, we can make multiple trips or schedule multi-day service.` },
            { q: `Can you come the same day in ${city.name}?`, a: `Yes. Same-day service is available across ${city.county} County. Book before noon for same-day pickup. Average operator matching time in ${city.name} is ${city.avgResponseMinutes} minutes. We serve all neighborhoods from ${city.neighborhoods[0]} to ${city.neighborhoods[city.neighborhoods.length - 1]}.` }
        ]
    };

    return baseFAQs[service.slug] || baseFAQs['furniture-removal'];
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

// --- Get related service×city combos for internal linking ---
function getRelatedServiceCities(service, city, allServices, allCities) {
    const links = [];

    // Same service, nearby cities (same county)
    const nearbyCities = allCities
        .filter(c => c.county === city.county && c.slug !== city.slug)
        .slice(0, 2);
    nearbyCities.forEach(c => {
        links.push({ url: `/junk-removal/${c.slug}-fl/${service.slug}`, text: `${service.name} in ${c.name}` });
    });

    // Same city, different services
    const otherServices = allServices
        .filter(s => s.slug !== service.slug)
        .slice(0, 3);
    otherServices.forEach(s => {
        links.push({ url: `/junk-removal/${city.slug}-fl/${s.slug}`, text: `${s.name} in ${city.name}` });
    });

    return links;
}

// --- Generate Why Choose section cards ---
function generateWhyChooseCards(city, service) {
    if (city.whyChoose && city.whyChoose.length > 0) {
        return city.whyChoose.map(reason => `
                    <div style="background: white; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.06);">
                        <div style="width: 48px; height: 48px; background: #FEE2E2; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-bottom: 1rem;">
                            <span style="color: #DC2626; font-size: 1.25rem; font-weight: 800;">&#10003;</span>
                        </div>
                        <p style="color: #3a3a3a; line-height: 1.6; font-weight: 500;">${reason}</p>
                    </div>`).join('');
    }
    // Fallback generic cards
    return `
                    <div style="background: white; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.06);">
                        <h3 style="font-weight: 700; margin-bottom: 0.5rem;">25% Less Than the Big Guys</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">No franchise fees, no corporate overhead. Our $${service.minCost} starting price beats national chains by at least 25%.</p>
                    </div>
                    <div style="background: white; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.06);">
                        <h3 style="font-weight: 700; margin-bottom: 0.5rem;">Same-Day Service</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">Book before noon, get service today. Average operator match time in ${city.name} is just ${city.avgResponseMinutes} minutes.</p>
                    </div>
                    <div style="background: white; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.06);">
                        <h3 style="font-weight: 700; margin-bottom: 0.5rem;">Local ${city.name} Operators</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">${city.operators} licensed and insured operators serving ${city.name} and all of ${city.county} County.</p>
                    </div>`;
}

// --- Generate Neighborhoods section ---
function generateNeighborhoodsSection(city, service) {
    const neighborhoods = city.neighborhoods || [];
    if (neighborhoods.length === 0) return '';

    const neighborhoodCards = neighborhoods.map((n, i) => {
        // Use city-specific neighborhood descriptions if available, fall back to generic
        let desc;
        if (city.neighborhoodDescriptions && city.neighborhoodDescriptions[n]) {
            desc = city.neighborhoodDescriptions[n];
        } else {
            const fallbacks = [
                `Serving ${n} with same-day ${service.name.toLowerCase()} — book online, we'll be there fast.`,
                `${n} residents get priority matching with nearby operators for quick ${service.name.toLowerCase()}.`,
                `Full ${service.name.toLowerCase()} coverage in ${n} — stairs, tight spaces, no problem.`,
                `${n} is one of our most active ${service.name.toLowerCase()} zones in ${city.name}.`,
                `We know ${n} well — trusted by homeowners and businesses for reliable ${service.name.toLowerCase()}.`
            ];
            desc = fallbacks[i % fallbacks.length];
        }
        return `
                    <div style="background: white; padding: 1.25rem; border-radius: 0.75rem; border: 1px solid rgba(0,0,0,0.06);">
                        <h3 style="font-size: 1rem; font-weight: 700; margin-bottom: 0.5rem; color: #DC2626;">${n}</h3>
                        <p style="color: #5c5c5c; font-size: 0.9rem; line-height: 1.5;">${desc}</p>
                    </div>`;
    }).join('');

    return `
    <!-- Local Service Areas / Neighborhoods -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    ${service.name} Neighborhoods We Serve in ${city.name}
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    Our ${city.operators} local operators cover every neighborhood in ${city.name}, FL. Here's where we're most active:
                </p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                    ${neighborhoodCards}
                </div>
            </div>
        </div>
    </section>`;
}

// --- Main page generator ---
// --- Generate "How It Works" step 2 description based on city characteristics ---
function getHowItWorksStep2(city) {
    // Gated / HOA-heavy communities
    const gatedCities = ['boca-raton', 'wellington', 'weston', 'palm-beach-gardens', 'cooper-city', 'pembroke-pines', 'coral-springs', 'deerfield-beach'];
    // High-rise / condo-heavy cities
    const highRiseCities = ['miami', 'miami-beach', 'fort-lauderdale', 'aventura', 'brickell', 'hallandale-beach', 'key-biscayne', 'doral'];
    // Waterfront / island cities
    const waterfrontCities = ['key-biscayne', 'miami-beach', 'jupiter', 'riviera-beach', 'lantana'];
    // Senior / 55+ heavy
    const seniorCities = ['boynton-beach', 'tamarac', 'coconut-creek', 'deerfield-beach'];
    // Rural / large-lot
    const ruralCities = ['davie', 'jupiter', 'homestead', 'greenacres'];
    // Budget-friendly / working class
    const budgetCities = ['hialeah', 'miami-gardens', 'homestead', 'greenacres', 'lake-worth'];

    if (highRiseCities.includes(city.slug)) {
        return `We match you with an operator who knows your building's freight elevator schedule and loading dock rules — no wasted time, no access issues. Average match time: ${city.avgResponseMinutes} minutes.`;
    } else if (gatedCities.includes(city.slug)) {
        return `Our system matches you with an operator pre-cleared at your community's gate — no guest pass delays, no waiting at security. Average match time: ${city.avgResponseMinutes} minutes.`;
    } else if (seniorCities.includes(city.slug)) {
        return `We match you with a patient, experienced operator familiar with your community's access rules and schedules. Average match time: ${city.avgResponseMinutes} minutes.`;
    } else if (waterfrontCities.includes(city.slug)) {
        return `Our system finds an operator experienced with waterfront property access — seawalls, dock areas, and island logistics. Average match time: ${city.avgResponseMinutes} minutes.`;
    } else if (ruralCities.includes(city.slug)) {
        return `We match you with the closest operator equipped for large-lot access — dirt roads, long driveways, and rural properties are no problem. Average match time: ${city.avgResponseMinutes} minutes.`;
    } else if (budgetCities.includes(city.slug)) {
        return `We find the nearest available operator in your neighborhood — ${city.operators} local operators means fast, affordable matching. Average match time: ${city.avgResponseMinutes} minutes.`;
    } else {
        return `Our system finds the nearest available ${city.name} operator — average match time is ${city.avgResponseMinutes} minutes. You'll get a confirmation with your operator's details.`;
    }
}

// --- Generate "How It Works" step 3 description based on city type ---
function getHowItWorksStep3(city, service) {
    const population = city.population || 50000;
    if (population > 150000) {
        return `Your operator arrives on schedule, handles all the heavy lifting — ${service.process} Serving all ${city.name} neighborhoods, from ${city.neighborhoods[0]} to ${city.neighborhoods[city.neighborhoods.length - 1]}.`;
    } else if (city.county === 'Miami-Dade') {
        return `${service.process} We recycle and donate whenever possible — keeping Miami-Dade cleaner, one job at a time.`;
    } else if (city.county === 'Palm Beach') {
        return `${service.process} 92% of what we collect in Palm Beach County gets donated or recycled — not landfilled.`;
    } else {
        return `${service.process} Every item is sorted for donation, recycling, or proper disposal. Your ${city.name} job stays eco-friendly.`;
    }
}

// --- How It Works intro (was identical "Three steps" on every page) ---
function getHowItWorksIntro(city, service) {
    const templates = [
        `Three steps. That's it. No phone tag, no waiting around for ${service.name.toLowerCase()} estimates.`,
        `Getting rid of junk in ${city.name} shouldn't take all day. Here's how we keep it simple.`,
        `${city.name} residents book ${service.name.toLowerCase()} in under 3 minutes — no phone calls, no home visits.`,
        `Why do ${city.jobsCompleted.toLocaleString()}+ ${city.county} County customers choose Umuve? Because it's this easy:`,
        `Skip the phone tag. ${city.operators} operators across ${city.name} are ready — just follow these 3 steps.`,
        `From ${city.neighborhoods[0]} to ${city.neighborhoods[city.neighborhoods.length - 1]}, here's how ${service.name.toLowerCase()} works with Umuve.`,
    ];
    return pickByHash(templates, city.slug, service.slug, 'hiw-intro');
}

// --- How It Works Step 1 (was identical "Upload photos" on every page) ---
function getHowItWorksStep1(city, service) {
    const templates = [
        `Upload photos of your items, select ${service.name.toLowerCase()} as your service, pick a date, and get instant pricing. No waiting, no home visits needed.`,
        `Snap a few photos of what needs to go, choose a time that works for your ${city.name} schedule, and get your price upfront — all online.`,
        `Tell us what you need removed and when. Our ${city.name} pricing engine gives you an instant quote based on ${city.jobsCompleted.toLocaleString()}+ local jobs.`,
        `Open the app, upload pics, and pick your date. Instant pricing for ${service.name.toLowerCase()} — no phone call, no technician visit, no surprise fees.`,
        `Start by describing your ${service.name.toLowerCase()} job. Add photos for an exact quote, or estimate the load size. Either way, pricing is locked in before you confirm.`,
        `Book from your couch in ${city.neighborhoods[0]} or your office in ${city.neighborhoods[1]} — just upload photos, pick a time, and confirm. 3 minutes tops.`,
    ];
    return pickByHash(templates, city.slug, service.slug, 'hiw-step1');
}

// --- Pricing section intro (was identical "Transparent pricing" on every page) ---
function getPricingIntro(city, service) {
    const templates = [
        `Transparent pricing — what you see is what you pay. All prices include labor, hauling, and eco-friendly disposal.`,
        `No hidden fees, no bait-and-switch. Every ${service.name.toLowerCase()} quote in ${city.name} includes labor, truck, and disposal.`,
        `Prices below are based on ${city.jobsCompleted.toLocaleString()} completed jobs across ${city.county} County. What you're quoted is what you pay — period.`,
        `${city.name} ${service.name.toLowerCase()} pricing is straightforward: labor + hauling + disposal, all included. No surprise charges at the curb.`,
        `We've completed ${city.jobsCompleted.toLocaleString()}+ ${service.name.toLowerCase()} jobs in ${city.county} County. These prices reflect what ${city.name} residents actually pay:`,
        `Flat-rate ${service.name.toLowerCase()} pricing for ${city.name}, FL. Includes pickup from any room, loading, hauling, and responsible disposal or recycling.`,
    ];
    return pickByHash(templates, city.slug, service.slug, 'pricing-intro');
}

// --- Final CTA text (was identical "jobs completed across South Florida" on every page) ---
function getFinalCTA(city, service) {
    const templates = [
        `${city.jobsCompleted.toLocaleString()}+ jobs completed across ${city.county} County. Get your free quote in 3 minutes — same-day service available.`,
        `Join ${city.reviewCount}+ ${city.name} residents who rated us ${city.rating}★. Book your ${service.name.toLowerCase()} now — most jobs completed same day.`,
        `${city.operators} operators standing by in ${city.name}. Average response: ${city.avgResponseMinutes} minutes. Book online now or call.`,
        `From $${service.minCost} in ${city.name}, FL. Licensed, insured, and ${city.rating}★ rated. Don't let junk sit another day — book in 3 minutes.`,
        `${city.name} trusts Umuve for ${service.name.toLowerCase()} — ${city.jobsCompleted.toLocaleString()}+ jobs and counting. Get your price in 3 minutes.`,
        `Same-day ${service.name.toLowerCase()} across ${city.neighborhoods.slice(0, 2).join(', ')} and all of ${city.name}. Free quotes, no obligation.`,
    ];
    return pickByHash(templates, city.slug, service.slug, 'final-cta');
}

// --- Comparison intro (was similar across counties) ---
function getComparisonIntro(city, service) {
    const templates = [
        `See how Umuve stacks up against the national franchises for ${service.name.toLowerCase()} in ${city.county} County.`,
        `${city.name} residents compare: Umuve vs. the big chains for ${service.name.toLowerCase()}.`,
        `Before you book ${service.name.toLowerCase()} in ${city.name}, see how pricing and service compare to the competition.`,
        `National franchises charge premium prices in ${city.county} County. Here's what you'd actually pay with each:`,
    ];
    return pickByHash(templates, city.slug, service.slug, 'comp-intro');
}

// --- Generate meta description with variety ---
function generateMetaDescription(service, city, cityIndex) {
    const templates = [
        `Professional ${service.name.toLowerCase()} in ${city.name}, FL from $${service.minCost}. ${city.operators} local operators, avg ${city.avgResponseMinutes} min response. ${city.localTip ? city.localTip.split(' — ')[0] + '.' : ''} Book online.`,
        `Need ${service.name.toLowerCase()} in ${city.name}? Serving ${city.neighborhoods[0]}, ${city.neighborhoods[1]} & more. From $${service.minCost}, same-day. ${city.reviewCount} five-star reviews.`,
        `${city.name} ${service.name.toLowerCase()} starting at $${service.minCost}. We serve all of ${city.county} County — ${city.jobsCompleted.toLocaleString()}+ jobs done. Book in 3 minutes.`,
        `Same-day ${service.name.toLowerCase()} in ${city.name}, FL. ${city.operators} operators, $${service.minCost} starting price. Licensed & insured. ${city.rating} stars from ${city.reviewCount} reviews. Book now.`,
        `${service.name} in ${city.name}, FL — avg job $${city.avgJobCost}. Serving ${city.neighborhoods.slice(0, 2).join(', ')} & all of ${city.county} County. Upfront pricing, same-day service. (561) 944-1636.`
    ];
    const hash = (cityIndex * 7 + service.slug.length * 13) % templates.length;
    return templates[hash];
}

// --- Main page generator ---
function generateServiceCityPage(service, city, allServices, allCities) {
    const title = `${service.name} in ${city.name}, FL | Umuve`;
    const cityIndex = allCities.findIndex(c => c.slug === city.slug);
    const description = generateMetaDescription(service, city, cityIndex);
    const pageUrl = `https://goumuve.com/junk-removal/${city.slug}-fl/${service.slug}`;

    // Pick intro template deterministically using city+service combo
    const templates = introTemplates[service.slug] || introTemplates['furniture-removal'];
    const templateIndex = (cityIndex * 7 + service.slug.length * 3) % templates.length;
    const introText = templates[templateIndex](city);

    const faqs = getServiceCityFAQs(service, city);
    const pricing = pricingByService[service.slug] || pricingByService['furniture-removal'];
    const relatedLinks = getRelatedServiceCities(service, city, allServices, allCities);

    // Nearby cities for footer
    const nearbyCities = allCities
        .filter(c => c.county === city.county && c.slug !== city.slug)
        .slice(0, 5);

    // Local context paragraph
    const localContextHTML = city.localContext ? `
    <!-- Local Context -->
    <section style="padding: 2.5rem 0 0;">
        <div class="container">
            <div class="content-block" style="border-left: 4px solid #DC2626;">
                <h2 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 0.75rem;">${service.name} in ${city.name} — Local Context</h2>
                <p>${city.localContext}</p>
            </div>
        </div>
    </section>` : '';

    // Why Choose section
    const whyChooseCards = generateWhyChooseCards(city, service);

    // Neighborhoods section
    const neighborhoodsSection = generateNeighborhoodsSection(city, service);

    // County specific stats (AEO Booster)
    const stats = metadata.countyStats[city.county] || metadata.countyStats['Palm Beach'];

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="${description}">
    <meta name="robots" content="index, follow">

    <!-- Open Graph -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="${pageUrl}">
    <meta property="og:title" content="${title}">
    <meta property="og:description" content="${description}">
    <meta property="og:image" content="https://goumuve.com/logo-full.png">
    <meta property="og:site_name" content="Umuve">

    <!-- Twitter -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="${title}">
    <meta name="twitter:description" content="${description}">

    <!-- Canonical -->
    <link rel="canonical" href="${pageUrl}">

    <title>${title}</title>

    <link rel="stylesheet" href="/styles.css">
    <link rel="stylesheet" href="/blog/blog.css">
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
        "name": `Umuve ${service.name} — ${city.name}`,
        "image": [
            "https://goumuve.com/logo-full.png",
            `https://goumuve.com/images/seo/services/${service.slug}.webp`,
            `https://goumuve.com/images/seo/cities/${city.slug}/${service.slug}-hero.webp`
        ],
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
    }, null, 8)}
    </script>

    <!-- Structured Data - Service -->
    <script type="application/ld+json">
    ${JSON.stringify({
        "@context": "https://schema.org",
        "@type": "Service",
        "serviceType": service.name,
        "provider": {
            "@type": "Organization",
            "name": "Umuve",
            "url": "https://goumuve.com",
            "logo": "https://goumuve.com/logo-full.png",
            "telephone": "+15619441636"
        },
        "areaServed": {
            "@type": "City",
            "name": city.name,
            "containedIn": {
                "@type": "State",
                "name": "Florida"
            }
        },
        "offers": {
            "@type": "AggregateOffer",
            "lowPrice": String(service.minCost),
            "highPrice": String(service.maxCost),
            "priceCurrency": "USD"
        },
        "description": `${service.name} in ${city.name}, FL. ${service.description}`
    }, null, 8)}
    </script>

    <!-- Structured Data - FAQ -->
    <script type="application/ld+json">
    ${generateFAQSchema(faqs)}
    </script>

    <!-- Structured Data - Reviews -->
    <script type="application/ld+json">
    ${JSON.stringify({
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": `Umuve ${service.name} — ${city.name}`,
        "review": (city.reviews || []).map(r => ({
            "@type": "Review",
            "reviewRating": {
                "@type": "Rating",
                "ratingValue": String(r.rating),
                "bestRating": "5"
            },
            "author": {
                "@type": "Person",
                "name": r.author
            },
            "datePublished": r.date,
            "reviewBody": r.text
        }))
    }, null, 8)}
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
            { "@type": "ListItem", "position": 4, "name": service.name, "item": pageUrl }
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
                <span style="color: #1a1a1a; font-weight: 500;">${service.name}</span>
            </nav>
        </div>
    </div>

    <!-- Hero -->
    <section style="padding: 3.5rem 0 3rem; background: linear-gradient(135deg, #f9fafb 0%, #ffffff 100%);">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto; text-align: center;">
                <h1 style="font-family: Outfit, sans-serif; font-size: clamp(2rem, 5vw, 2.75rem); font-weight: 800; margin-bottom: 1.5rem; line-height: 1.15;">
                    ${service.name} in ${city.name}, FL<br>
                    <span style="color: #DC2626;">From $${service.minCost} — Same-Day Service</span>
                </h1>
                <p style="font-size: 1.1rem; color: #5c5c5c; margin-bottom: 2rem; line-height: 1.7; text-align: left;">
                    ${introText}
                </p>
                <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                    <a href="https://app.goumuve.com/book" class="btn btn-primary btn-xl">Get Free Quote</a>
                    <a href="tel:+15619441636" class="btn btn-secondary btn-xl">Call (561) 944-1636</a>
                </div>
                <p style="margin-top: 1rem; font-size: 0.85rem; color: #8a8a8a;">
                    ${city.rating}&#9733; from ${city.reviewCount} reviews &bull; Licensed & Insured &bull; ${service.ecoFriendly}
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

    <!-- Service Image -->
    <picture>
        <source srcset="/images/seo/services/${service.slug}.webp" type="image/webp">
        <img src="/images/seo/services/${service.slug}.jpg"
             alt="${service.name} in ${city.name}, FL - Umuve junk removal truck loading ${service.items[0].toLowerCase()}"
             width="800" height="450" loading="eager"
             style="width: 100%; max-width: 800px; height: auto; border-radius: 0.75rem; margin: 1rem auto 2rem; display: block; padding: 0 1.5rem;"
             onerror="this.style.display='none'">
    </picture>

    ${localContextHTML}

    <!-- Sustainability & Local Impact (AEO Booster) -->
    <section style="padding: 3rem 0; background: #FEF2F2; border-top: 1px solid #FECACA; border-bottom: 1px solid #FECACA;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.5rem; font-weight: 800; margin-bottom: 1.5rem; text-align: center;">2025 Sustainability Impact: ${city.county} County</h2>
                <div class="impact-grid">
                    <div class="impact-card">
                        <span class="impact-val">${stats.diversionRate}</span>
                        <span class="impact-label">Waste Diversion</span>
                    </div>
                    <div class="impact-card">
                        <span class="impact-val">${stats.totalMSW}</span>
                        <span class="impact-label">Annual Tonnage</span>
                    </div>
                    <div class="impact-card">
                        <span class="impact-val">${stats.leaderStatus}</span>
                        <span class="impact-label">Local Status</span>
                    </div>
                </div>
                <p style="margin-top: 1.5rem; font-size: 0.9rem; color: #7f1d1d; line-height: 1.6; text-align: center; font-style: italic;">
                    "Our mission in ${city.name} is to ensure that <strong>${stats.diversionRate}</strong> of what we haul stays out of the landfill through our direct partnerships with local charities."
                </p>
            </div>
        </div>
    </section>

    <!-- What We Remove -->
    <section style="padding: 3rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    What We Pick Up
                </h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem;">
                    ${service.items.map(item => `
                    <div style="padding: 0.75rem 1rem; background: #f9fafb; border-radius: 0.5rem; font-weight: 500; border: 1px solid rgba(0,0,0,0.04);">
                        &#10003; ${item}
                    </div>`).join('')}
                    ${(city.localItems || []).map(item => `
                    <div style="padding: 0.75rem 1rem; background: #FEF2F2; border-radius: 0.5rem; font-weight: 500; border: 1px solid #FECACA;">
                        &#10003; ${item} <span style="font-size: 0.75rem; color: #DC2626; font-weight: 700;">${city.name}</span>
                    </div>`).join('')}
                </div>
            </div>
        </div>
    </section>

    <!-- How It Works -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    How ${service.name} Works in ${city.name}
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2.5rem; font-size: 1.05rem;">
                    ${getHowItWorksIntro(city, service)}
                </p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 2rem;">
                    <div style="text-align: center; padding: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626; margin-bottom: 1rem;">01</div>
                        <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.75rem;">Book Online in 3 Minutes</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">${getHowItWorksStep1(city, service)}</p>
                    </div>
                    <div style="text-align: center; padding: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626; margin-bottom: 1rem;">02</div>
                        <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.75rem;">We Match You Locally</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">${getHowItWorksStep2(city)}</p>
                    </div>
                    <div style="text-align: center; padding: 1.5rem;">
                        <div style="font-size: 3rem; font-weight: 800; color: #DC2626; margin-bottom: 1rem;">03</div>
                        <h3 style="font-size: 1.2rem; font-weight: 700; margin-bottom: 0.75rem;">We Haul, You Relax</h3>
                        <p style="color: #5c5c5c; line-height: 1.6;">${getHowItWorksStep3(city, service)}</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Pricing -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 700px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    ${service.name} Pricing in ${city.name}, FL
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    ${getPricingIntro(city, service)}
                </p>
                <div style="background: #FEF2F2; border: 1px solid #FECACA; border-radius: 0.75rem; padding: 1.25rem; margin-bottom: 2rem; text-align: center;">
                    <p style="font-size: 1.1rem; font-weight: 600; color: #DC2626;">
                        Average ${service.name.toLowerCase()} job in ${city.name}: $${city.avgJobCost}
                    </p>
                    <p style="font-size: 0.9rem; color: #5c5c5c; margin-top: 0.25rem;">
                        Based on ${city.jobsCompleted.toLocaleString()} completed jobs in ${city.name}
                    </p>
                </div>
                <div style="display: grid; gap: 0.75rem;">
                    ${pricing.map(p => `
                    <div class="pricing-row${p.popular ? ' popular' : ''}">
                        <div>
                            <strong>${p.label}</strong>${p.popular ? ' <span style="background: #DC2626; color: white; padding: 0.15rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; font-weight: 700;">MOST POPULAR</span>' : ''}<br>
                            <span style="font-size: 0.85rem; color: #8a8a8a;">${p.desc}</span>
                        </div>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #DC2626;">${p.price}</span>
                    </div>`).join('')}
                </div>
                <div style="text-align: center; margin-top: 2rem;">
                    <a href="https://app.goumuve.com/book" class="btn btn-primary btn-xl">Get Your Exact Price</a>
                </div>
            </div>
        </div>
    </section>

    <!-- Competitor Comparison -->
    ${service.competitorPricing ? `
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    ${service.name} in ${city.name}: How Umuve Compares
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    ${getComparisonIntro(city, service)}
                </p>
                <div style="overflow-x: auto;">
                    <table class="comparison-table">
                        <thead>
                            <tr>
                                <th>Feature</th>
                                <th class="col-umuve">Umuve</th>
                                <th class="col-competitor">1-800-GOT-JUNK</th>
                                <th class="col-competitor">Junk King</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Starting Price</td>
                                <td class="col-umuve"><strong>$${service.minCost}</strong> <span class="check">&#10003;</span></td>
                                <td class="col-competitor">$${service.competitorPricing.gotJunk.min}+</td>
                                <td class="col-competitor">$${service.competitorPricing.junkKing.min}+</td>
                            </tr>
                            <tr>
                                <td>Same-Day Service</td>
                                <td class="col-umuve"><strong>Yes</strong> <span class="check">&#10003;</span></td>
                                <td class="col-competitor">Call to schedule</td>
                                <td class="col-competitor">Call to schedule</td>
                            </tr>
                            <tr>
                                <td>Online Booking</td>
                                <td class="col-umuve"><strong>3 minutes</strong> <span class="check">&#10003;</span></td>
                                <td class="col-competitor">Phone required</td>
                                <td class="col-competitor">Phone required</td>
                            </tr>
                            <tr>
                                <td>Upfront Pricing</td>
                                <td class="col-umuve"><strong>Yes</strong> <span class="check">&#10003;</span></td>
                                <td class="col-competitor">On-site estimate</td>
                                <td class="col-competitor">On-site estimate</td>
                            </tr>
                            <tr>
                                <td>Eco-Friendly</td>
                                <td class="col-umuve"><strong>${service.ecoFriendly.split(' ')[0]} recycled</strong> <span class="check">&#10003;</span></td>
                                <td class="col-competitor">Varies</td>
                                <td class="col-competitor">Varies</td>
                            </tr>
                            <tr>
                                <td>Local Operators</td>
                                <td class="col-umuve"><strong>${city.operators} in ${city.name}</strong> <span class="check">&#10003;</span></td>
                                <td class="col-competitor">National crew</td>
                                <td class="col-competitor">Franchise crew</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div style="text-align: center; margin-top: 2rem;">
                    <a href="https://app.goumuve.com/book" class="btn btn-primary btn-xl">Get Your Umuve Quote</a>
                </div>
            </div>
        </div>
    </section>` : ''}

    <!-- Why City Residents Choose Umuve -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    Why ${city.name} Residents Choose Umuve for ${service.name}
                </h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem;">
                    ${whyChooseCards}
                </div>
            </div>
        </div>
    </section>

    <!-- Customer Reviews -->
    ${(city.reviews && city.reviews.length > 0) ? `
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    What ${city.name} Residents Say
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    ${city.rating} out of 5 stars from ${city.reviewCount} verified reviews
                </p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem;">
                    ${city.reviews.map(r => `
                    <div class="review-card">
                        <div class="review-stars">${'&#9733;'.repeat(r.rating)}${r.rating < 5 ? '&#9734;'.repeat(5 - r.rating) : ''}</div>
                        <p class="review-text">"${r.text}"</p>
                        <div>
                            <span class="review-author">${r.author}</span>
                            <span class="review-date">${new Date(r.date).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}</span>
                        </div>
                    </div>`).join('')}
                </div>
            </div>
        </div>
    </section>` : ''}

    <!-- FAQ -->
    <section style="padding: 4rem 0; background: #ffffff;">
        <div class="container">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 2rem;">
                    Frequently Asked Questions — ${service.name} in ${city.name}
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

    ${city.disposalRules ? `
    <!-- Local Disposal Rules -->
    <section style="padding: 2rem 0;">
        <div class="container">
            <div class="tip-box">
                <h3 style="font-size: 1rem; font-weight: 700; margin-bottom: 0.5rem;">${city.name} Disposal Rules to Know</h3>
                <p>${city.disposalRules}</p>
            </div>
        </div>
    </section>` : ''}

    ${neighborhoodsSection}

    <!-- Internal Links -->
    <section style="padding: 4rem 0; background: #f9fafb;">
        <div class="container">
            <div style="max-width: 900px; margin: 0 auto;">
                <h2 style="font-size: 1.75rem; font-weight: 800; text-align: center; margin-bottom: 0.75rem;">
                    Related Services
                </h2>
                <p style="text-align: center; color: #5c5c5c; margin-bottom: 2rem;">
                    Explore more junk removal services in ${city.name} and nearby cities:
                </p>
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: center; margin-bottom: 2rem;">
                    ${relatedLinks.map(link => `<a href="${link.url}" class="related-link">${link.text}</a>`).join('\n                    ')}
                </div>
                <div style="text-align: center; margin-top: 1rem;">
                    <a href="/junk-removal/${city.slug}-fl" class="related-link" style="font-weight: 700;">&#8592; All Junk Removal in ${city.name}, FL</a>
                    <a href="/services/${service.slug}" class="related-link" style="font-weight: 700;">${service.name} — All Cities &#8594;</a>
                </div>
            </div>
        </div>
    </section>

    <!-- Final CTA -->
    <section style="padding: 4rem 0; background: linear-gradient(135deg, #DC2626, #B91C1C); color: white; text-align: center;">
        <div class="container">
            <h2 style="font-family: Outfit; font-size: 2rem; font-weight: 800; margin-bottom: 1rem;">
                Ready for ${service.name} in ${city.name}?
            </h2>
            <p style="font-size: 1.1rem; margin-bottom: 2rem; opacity: 0.95; max-width: 600px; margin-left: auto; margin-right: auto;">
                ${getFinalCTA(city, service)}
            </p>
            <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                <a href="https://app.goumuve.com/book" style="background: white; color: #DC2626; padding: 1rem 2.5rem; font-weight: 700; border-radius: 0.5rem; text-decoration: none; display: inline-block; font-size: 1.1rem;">Book Online Now</a>
                <a href="tel:+15619441636" style="background: rgba(255,255,255,0.15); color: white; padding: 1rem 2.5rem; font-weight: 700; border-radius: 0.5rem; text-decoration: none; display: inline-block; font-size: 1.1rem; border: 2px solid rgba(255,255,255,0.3);">Call (561) 944-1636</a>
            </div>
        </div>
    </section>

    <!-- Regional Awareness (Marketing Skills) -->
    <section style="padding: 2rem 0; background: #ffffff; text-align: center;">
        <div class="container">
            <p style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; color: #8a8a8a; letter-spacing: 0.05em; margin-bottom: 1rem;">Share this ${city.name} City Report</p>
            <div style="display: flex; justify-content: center; gap: 1rem;">
                <a href="https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(pageUrl)}" target="_blank" style="width: 40px; height: 40px; border-radius: 50%; background: #1877F2; display: flex; align-items: center; justify-content: center; color: white; text-decoration: none;">f</a>
                <a href="https://twitter.com/intent/tweet?text=${encodeURIComponent('Check out the 2026 ' + service.name + ' rates for ' + city.name + ' via @umuve')}&url=${encodeURIComponent(pageUrl)}" target="_blank" style="width: 40px; height: 40px; border-radius: 50%; background: #000000; display: flex; align-items: center; justify-content: center; color: white; text-decoration: none;">𝕏</a>
                <a href="https://wa.me/?text=${encodeURIComponent('Check out the 2026 ' + service.name + ' rates for ' + city.name + ' via Umuve: ' + pageUrl)}" target="_blank" style="width: 40px; height: 40px; border-radius: 50%; background: #25D366; display: flex; align-items: center; justify-content: center; color: white; text-decoration: none;">w</a>
            </div>
        </div>
    </section>

    <!-- Expert Bio Section (E-E-A-T Booster) -->
    <section style="padding: 3rem 0; background: #f9fafb; border-top: 1px solid #e5e7eb;">
        <div class="container">
            <div class="expert-section" style="max-width: 800px; margin: 0 auto;">
                <div class="expert-avatar">
                    ${metadata.expert.name[0]}
                </div>
                <div class="expert-info">
                    <div class="expert-title">${metadata.expert.title}</div>
                    <h4>Expert Contributor: ${metadata.expert.name}</h4>
                    <p style="color: #5c5c5c; line-height: 1.6; font-size: 0.95rem;">${metadata.expert.bio}</p>
                </div>
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
                        ${allServices.slice(0, 5).map(s => `<a href="/services/${s.slug}" style="color: #8a8a8a; text-decoration: none; font-size: 0.85rem;">${s.name}</a>`).join('\n                        ')}
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
                <p style="color: #5c5c5c; font-size: 0.8rem;">&copy; 2026 Umuve Inc. Licensed & Insured. Serving Miami-Dade, Broward & Palm Beach Counties.</p>
            </div>
        </div>
    </footer>

    <!-- Before/After Section (hidden until real photos are added) -->
    <div id="before-after" style="display: none; padding: 3rem 0;">
        <!-- Will be populated when real before/after photos are added -->
    </div>

    <!-- Sticky CTA Bar -->
    <div class="sticky-cta">
        <a href="https://app.goumuve.com/book" class="book-btn">Book Your ${service.name} &mdash; From $${service.minCost}</a>
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
                    icon.textContent = '\u2212';
                } else {
                    a.style.display = 'none';
                    icon.textContent = '+';
                }
            });
        });
        // Hide all answers by default
        document.querySelectorAll('.faq-a').forEach(function(a) { a.style.display = 'none'; });
    </script>
</body>
</html>`;

    return html;
}

// --- Main execution ---
const pagesDir = path.join(__dirname, '../pages/junk-removal');
let totalGenerated = 0;

console.log(`Generating service×city pages (${cities.length} cities × ${services.length} services)...`);

cities.forEach(city => {
    // Create city subdirectory
    const cityDir = path.join(pagesDir, `${city.slug}-fl`);
    if (!fs.existsSync(cityDir)) {
        fs.mkdirSync(cityDir, { recursive: true });
    }

    services.forEach(service => {
        const html = generateServiceCityPage(service, city, services, cities);
        const filepath = path.join(cityDir, `${service.slug}.html`);
        fs.writeFileSync(filepath, html);
        totalGenerated++;
    });
});

console.log(`Generated ${totalGenerated} service×city pages across ${cities.length} city directories.`);
console.log(`Total new pages: ${totalGenerated}`);

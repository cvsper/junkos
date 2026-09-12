//
//  DumpModels.swift
//  Umuve Pro
//
//  Contract for GET /api/driver/dump/suggest — where to tip this load,
//  why, and what the runner-up options are.
//

import Foundation

struct DumpFacility: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let type: String
    let `operator`: String?
    let address: String
    let lat: Double
    let lon: Double
    let county: String
    let acceptsCategories: [String]
    let phone: String?
    let access: String?
    let notes: String?

    enum CodingKeys: String, CodingKey {
        case id, name, type, `operator`, address, lat, lon, county, phone, access, notes
        case acceptsCategories = "accepts_categories"
    }

    var typeLabel: String {
        switch type {
        case "transfer_station": return "Transfer station"
        case "landfill": return "Landfill"
        case "mrf": return "Recycling facility"
        case "c_and_d": return "C&D yard"
        case "wte": return "Waste-to-energy"
        default: return type.capitalized
        }
    }

    var countyLabel: String {
        switch county {
        case "palm-beach": return "Palm Beach"
        case "miami-dade": return "Miami-Dade"
        case "st-lucie": return "St. Lucie"
        case "indian-river": return "Indian River"
        default: return county.capitalized
        }
    }

    var accessLabel: String {
        switch access {
        case "account": return "Account customers only"
        case "permit": return "County hauler permit required"
        case "residents": return "Residents only"
        default: return "Walk-in — pay at the scale"
        }
    }
}

struct DumpOption: Codable, Identifiable {
    let facility: DumpFacility
    let miles: Double
    let minutes: Int
    let openNow: Bool
    let closesAt: String?
    let nextOpen: String?
    let ratePerTon: Double?
    let rateNote: String?
    let rateEstimated: Bool?
    let estTip: Double?
    let estDrive: Double?
    let estTotal: Double?
    let eligible: Bool
    let blockers: [String]
    let reasons: [String]
    let caveats: [String]

    var id: String { facility.id }

    enum CodingKeys: String, CodingKey {
        case facility, miles, minutes, eligible, blockers, reasons, caveats
        case openNow = "open_now"
        case closesAt = "closes_at"
        case nextOpen = "next_open"
        case ratePerTon = "rate_per_ton"
        case rateNote = "rate_note"
        case rateEstimated = "rate_estimated"
        case estTip = "est_tip"
        case estDrive = "est_drive"
        case estTotal = "est_total"
    }
}

struct DumpNotEligible: Codable, Identifiable {
    let name: String
    let miles: Double
    let blockers: [String]
    var id: String { name }
}

struct DumpAssumptions: Codable {
    let category: String
    let categoryLabel: String
    let tons: Double
    let originCounty: String?

    enum CodingKeys: String, CodingKey {
        case category, tons
        case categoryLabel = "category_label"
        case originCounty = "origin_county"
    }
}

struct DumpSuggestResponse: Codable {
    let suggested: DumpOption?
    let alternatives: [DumpOption]
    let notEligible: [DumpNotEligible]
    let assumptions: DumpAssumptions
    let generatedAt: String

    enum CodingKeys: String, CodingKey {
        case suggested, alternatives, assumptions
        case notEligible = "not_eligible"
        case generatedAt = "generated_at"
    }
}

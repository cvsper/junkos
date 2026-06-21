//
//  OfferModels.swift
//  Umuve Pro
//
//  Broadcast job offers (DISPATCH_MODE=broadcast). One offer per eligible
//  operator; first to accept wins. Listed via GET /api/driver/offers and
//  claimed via POST /api/offers/<accept_token>/accept.
//

import Foundation

struct DriverOffer: Codable, Identifiable {
    var id: String { offerId }
    let acceptToken: String
    let offerId: String
    let jobId: String
    let payoutAmount: Double?
    let distanceMiles: Double?
    let expiresAt: String?
    let address: String?
    let scheduledAt: String?
    let totalPrice: Double?

    enum CodingKeys: String, CodingKey {
        case acceptToken = "accept_token"
        case offerId = "offer_id"
        case jobId = "job_id"
        case payoutAmount = "payout_amount"
        case distanceMiles = "distance_miles"
        case expiresAt = "expires_at"
        case address
        case scheduledAt = "scheduled_at"
        case totalPrice = "total_price"
    }
}

struct DriverOffersResponse: Codable {
    let success: Bool
    let offers: [DriverOffer]
}

struct OfferAcceptResponse: Codable {
    let success: Bool
    let status: String?
    let message: String?
}

// MARK: - Payouts

struct PayoutEligibilityResponse: Codable {
    let eligible: Bool
    let availableAmount: Double

    enum CodingKeys: String, CodingKey {
        case eligible
        case availableAmount = "available_amount"
    }
}

struct InstantPayoutResponse: Codable {
    let success: Bool
    let amount: Double?
    let payoutId: String?

    enum CodingKeys: String, CodingKey {
        case success, amount
        case payoutId = "payout_id"
    }
}

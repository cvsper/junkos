//  Models.swift — Umuve Desk
//  Shapes mirror the desk's JSON exactly (backend/desk_admin.py, va_time.py,
//  inbound.py, desk_line.py). Optional wherever the server may omit a key.

import Foundation

struct DeskSession: Codable, Equatable {
    let token: String
    let name: String
    let fullName: String?
    let email: String?
    let role: String
    let isManager: Bool
    enum CodingKeys: String, CodingKey {
        case token, name, email, role
        case fullName = "full_name"
        case isManager = "is_manager"
    }
}

struct VoiceToken: Codable {
    let enabled: Bool
    let token: String?
    let ttl: Int?
    let identity: String?
    let deskNumber: String?
    let push: Bool?
    let pushReason: String?
    let reason: String?
    enum CodingKeys: String, CodingKey {
        case enabled, token, ttl, identity, push, reason
        case deskNumber = "desk_number"
        case pushReason = "push_reason"
    }
}

struct ClockState: Codable {
    let onClock: Bool
    let vaName: String?
    let todaySeconds: Int?
    let periodSeconds: Int?
    enum CodingKeys: String, CodingKey {
        case onClock = "on_clock"
        case vaName = "va_name"
        case todaySeconds = "today_seconds"
        case periodSeconds = "period_seconds"
    }
}

/// Who is calling. `kind` is "customer" | "prospect" | "unknown".
struct Whois: Codable {
    let kind: String
    let phone: String?
    let phoneDigits: String?
    let source: String?
    let banner: String?
    let customer: CallerSummary?
    let prospect: CallerSummary?
    let callback: Callback?
    let recentCalls: [InboundCallRow]?
    enum CodingKeys: String, CodingKey {
        case kind, phone, source, banner, customer, prospect, callback
        case phoneDigits = "phone_digits"
        case recentCalls = "recent_calls"
    }
    var displayName: String {
        customer?.name ?? prospect?.name ?? prospect?.company ?? "Unknown caller"
    }
}

struct CallerSummary: Codable {
    let id: String?
    let name: String?
    let company: String?
    let email: String?
    let address: String?
    let jobs: Int?
    let lastJob: String?
    let notes: String?
    enum CodingKeys: String, CodingKey {
        case id, name, company, email, address, jobs, notes
        case lastJob = "last_job"
    }
}

struct Callback: Codable, Identifiable {
    let id: String
    let phone: String?
    let name: String?
    let when: String?
    let note: String?
    let status: String?
}

struct InboundCallRow: Codable, Identifiable {
    let id: String
    let phone: String?
    let name: String?
    let disposition: String?
    let source: String?
    let seconds: Int?
    let createdAt: String?
    enum CodingKeys: String, CodingKey {
        case id, phone, name, disposition, source, seconds
        case createdAt = "created_at"
    }
}

struct RecentInbound: Codable {
    let calls: [InboundCallRow]
    let callbacks: [Callback]?
}

struct Quote: Codable {
    let total: Double?
    let lines: [QuoteLine]?
    let note: String?
    let error: String?
}

struct QuoteLine: Codable {
    let label: String?
    let amount: Double?
}

struct BookResult: Codable {
    let ok: Bool?
    let jobId: String?
    let message: String?
    let error: String?
    enum CodingKeys: String, CodingKey {
        case ok, message, error
        case jobId = "job_id"
    }
}

struct OKResult: Codable {
    let ok: Bool?
    let message: String?
    let error: String?
}

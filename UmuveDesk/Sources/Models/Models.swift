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
    let weekSeconds: Int?
    let periodSeconds: Int?
    let periodLabel: String?
    let shift: Shift?
    enum CodingKeys: String, CodingKey {
        case shift
        case onClock = "on_clock"
        case vaName = "va_name"
        case todaySeconds = "today_seconds"
        case weekSeconds = "week_seconds"
        case periodSeconds = "period_seconds"
        case periodLabel = "period_label"
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

// MARK: - the outbound desk

/// A JSON value we render without knowing its exact shape (kit sections vary by side).
enum JSONValue: Codable {
    case string(String), number(Double), bool(Bool), null
    case array([JSONValue]), object([String: JSONValue])
    init(from d: Decoder) throws {
        let c = try d.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let b = try? c.decode(Bool.self) { self = .bool(b) }
        else if let n = try? c.decode(Double.self) { self = .number(n) }
        else if let s = try? c.decode(String.self) { self = .string(s) }
        else if let a = try? c.decode([JSONValue].self) { self = .array(a) }
        else { self = .object(try c.decode([String: JSONValue].self)) }
    }
    func encode(to e: Encoder) throws {
        var c = e.singleValueContainer()
        switch self {
        case .string(let s): try c.encode(s); case .number(let n): try c.encode(n); case .bool(let b): try c.encode(b)
        case .null: try c.encodeNil(); case .array(let a): try c.encode(a); case .object(let o): try c.encode(o)
        }
    }
    var text: String? { if case .string(let s) = self { return s }; return nil }
    /// Flatten to display lines: strings as-is, objects as "key: value", arrays recursively.
    var lines: [String] {
        switch self {
        case .string(let s): return [s]
        case .number(let n): return [n == n.rounded() ? String(Int(n)) : String(n)]
        case .bool(let b): return [b ? "yes" : "no"]
        case .null: return []
        case .array(let a): return a.flatMap { $0.lines }
        case .object(let o):
            // a price row: {"label": "Sofa", "from": "$129"} reads as "Sofa — from $129"
            if let l = o["label"]?.text, let f = o["from"]?.text { return ["\(l) — from \(f)"] }
            return o.sorted { $0.key < $1.key }.map { k, v in
                let vl = v.lines.joined(separator: " "); return vl.isEmpty ? k : "\(k): \(vl)" }
        }
    }
}

struct Compliance: Codable {
    let dnc: Bool?
    let dncSource: String?
    let windowOpen: Bool?
    let windowNote: String?
    enum CodingKeys: String, CodingKey { case dnc; case dncSource = "dnc_source"; case windowOpen = "window_open"; case windowNote = "window_note" }
}

struct Prospect: Codable, Identifiable {
    let id: String
    let company: String?
    let contactName: String?
    let phone: String?
    let directPhone: String?
    let email: String?
    let city: String?
    let category: String?
    let tier: String?
    let side: String?
    let status: String?
    let attempts: Int?
    let lastOutcome: String?
    let lastNote: String?
    let lastCalledAt: String?
    let nextFollowupAt: String?
    let why: String?
    let angle: String?
    let angleGenerated: Bool?
    let opener: String?
    let tel: String?
    let directTel: String?
    let isFollowup: Bool?
    let stage: String?
    let tags: [String]?
    let compliance: Compliance?
    enum CodingKeys: String, CodingKey {
        case id, company, phone, email, city, category, tier, side, status, attempts, why, angle, opener, tel, stage, tags, compliance
        case contactName = "contact_name", directPhone = "direct_phone", lastOutcome = "last_outcome", lastNote = "last_note"
        case lastCalledAt = "last_called_at", nextFollowupAt = "next_followup_at", angleGenerated = "angle_generated"
        case directTel = "direct_tel", isFollowup = "is_followup"
    }
    var displayName: String { company ?? contactName ?? phone ?? "Prospect" }
    /// The number to dial: E.164 from the tel: link the desk built.
    var dialNumber: String? { (directTel ?? tel)?.replacingOccurrences(of: "tel:", with: "") }
}

struct DayStats: Codable {
    let callsToday: Int?
    let interestedToday: Int?
    let dueNow: Int?
    let fresh: Int?
    enum CodingKeys: String, CodingKey { case callsToday = "calls_today", interestedToday = "interested_today", dueNow = "due_now", fresh }
}

struct LeadWaiting: Codable, Identifiable {
    let id: String?
    let name: String?
    let phone: String?
    let source: String?
    let summary: String?
    var stableId: String { id ?? phone ?? UUID().uuidString }
}

struct NextCard: Codable {
    let card: Prospect?
    let stats: DayStats?
    let empty: Bool?
    let leadsFirst: Bool?
    let message: String?
    let waiting: Int?
    let paid: Int?
    let total: Int?
    let scheduled: Int?
    enum CodingKeys: String, CodingKey { case card, stats, empty, message, waiting, paid, total, scheduled; case leadsFirst = "leads_first" }
}

struct LogResult: Codable {
    let logged: Bool?
    let stats: DayStats?
    let texted: Bool?
    let textReason: String?
    let card: Prospect?
    let empty: Bool?
    let error: String?
    enum CodingKeys: String, CodingKey { case logged, stats, texted, card, empty, error; case textReason = "text_reason" }
}

struct QueueRow: Codable, Identifiable {
    let id: String
    let company: String?
    let city: String?
    let phone: String?
    let category: String?
    let tier: String?
    let status: String?
    let attempts: Int?
    let contactName: String?
    let lastOutcome: String?
    let dueAt: String?
    enum CodingKeys: String, CodingKey { case id, company, city, phone, category, tier, status, attempts; case contactName = "contact_name", lastOutcome = "last_outcome", dueAt = "due_at" }
}

struct QueueResponse: Codable {
    let due: [QueueRow]?
    let dueNow: [QueueRow]?
    let later: [QueueRow]?
    let fresh: [QueueRow]?
    let scheduled: [QueueRow]?
    let callbacks: [QueueRow]?
    let total: Int?
    enum CodingKeys: String, CodingKey { case due, later, fresh, scheduled, callbacks, total; case dueNow = "due_now" }
    var dueRows: [QueueRow] { dueNow ?? due ?? [] }
    var laterRows: [QueueRow] { later ?? scheduled ?? callbacks ?? [] }
}

struct SearchResults: Codable { let results: [QueueRow] }

struct KitTrack: Codable {
    let pitch: String?
    let close: String?
    let segment: String?
}

struct Kit: Codable {
    let side: String?
    let detectedSide: String?
    let track: KitTrack?
    let objections: JSONValue?
    let answers: JSONValue?
    let prices: JSONValue?
    let priceNote: String?
    let lookup: JSONValue?
    enum CodingKeys: String, CodingKey { case side, track, objections, answers, prices, lookup; case detectedSide = "detected_side", priceNote = "price_note" }
}

// MARK: - inbox

struct InboxItem: Codable, Identifiable {
    let phoneDigits: String
    let phone: String?
    let prospectId: String?
    let company: String?
    let city: String?
    let preview: String?
    let kind: String?
    let unread: Int?
    let at: String?
    var id: String { phoneDigits }
    enum CodingKeys: String, CodingKey { case phone, company, city, preview, kind, unread, at; case phoneDigits = "phone_digits", prospectId = "prospect_id" }
}

struct InboxResponse: Codable {
    let items: [InboxItem]
    let unread: Int?
    let deskNumber: String?
    enum CodingKeys: String, CodingKey { case items, unread; case deskNumber = "desk_number" }
}

struct ThreadMessage: Codable, Identifiable {
    let id: String
    let kind: String?
    let direction: String?
    let body: String?
    let status: String?
    let duration: Int?
    let vaName: String?
    let createdAt: String?
    enum CodingKeys: String, CodingKey { case id, kind, direction, body, status, duration; case vaName = "va_name", createdAt = "created_at" }
}

struct ThreadResponse: Codable {
    let prospectId: String?
    let messages: [ThreadMessage]
    let deskNumber: String?
    enum CodingKeys: String, CodingKey { case messages; case prospectId = "prospect_id", deskNumber = "desk_number" }
}

struct Templates: Codable { let intro: String?; let info: String?; let followup: String? }
struct UnreadCount: Codable { let unread: Int }

// MARK: - hours

struct Shift: Codable, Identifiable {
    let id: String
    let vaName: String?
    let startedAt: String?
    let endedAt: String?
    let open: Bool?
    let seconds: Int?
    let note: String?
    let unpaid: Bool?
    enum CodingKeys: String, CodingKey { case id, open, seconds, note, unpaid; case vaName = "va_name", startedAt = "started_at", endedAt = "ended_at" }
}

struct HoursReport: Codable {
    let shifts: [Shift]?
    let totals: JSONValue?
}

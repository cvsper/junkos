//  DeskAPI.swift — Umuve Desk
//  Every call the app makes. Async URLSession, JWT from the Keychain, and the
//  server's own error strings surfaced as-is: the desk already writes them for
//  a person to read.

import Foundation

enum DeskError: LocalizedError {
    case server(String)
    case unauthorized
    case network(Error)
    case decoding(Error)

    var errorDescription: String? {
        switch self {
        case .server(let m): return m
        case .unauthorized: return "Sign in to the desk first."
        case .network(let e): return "No connection — \(e.localizedDescription)"
        case .decoding(let e): return "The desk answered in a shape I didn't expect (\(e.localizedDescription))"
        }
    }
}

private struct ServerError: Decodable { let error: String }

actor DeskAPI {
    static let shared = DeskAPI()
    static let tokenKey = "desk.jwt"

    private let session: URLSession = {
        let c = URLSessionConfiguration.default
        c.timeoutIntervalForRequest = AppConfig.requestTimeout
        c.timeoutIntervalForResource = AppConfig.requestTimeout * 2
        return URLSession(configuration: c)
    }()

    // MARK: core

    private func post<T: Decodable>(_ path: String, _ body: [String: Any] = [:],
                                    authenticated: Bool = true) async throws -> T {
        var req = URLRequest(url: AppConfig.baseURL.appendingPathComponent(path))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if authenticated, let jwt = Keychain.load(Self.tokenKey) {
            req.setValue("Bearer \(jwt)", forHTTPHeaderField: "Authorization")
        }
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, resp): (Data, URLResponse)
        do { (data, resp) = try await session.data(for: req) } catch { throw DeskError.network(error) }
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code == 401 { throw DeskError.unauthorized }
        if code >= 400 {
            if let e = try? JSONDecoder().decode(ServerError.self, from: data) { throw DeskError.server(e.error) }
            throw DeskError.server("The desk returned \(code).")
        }
        do { return try JSONDecoder().decode(T.self, from: data) } catch { throw DeskError.decoding(error) }
    }

    // MARK: session

    func signIn(email: String, password: String) async throws -> DeskSession {
        let s: DeskSession = try await post("/api/desk/login",
                                            ["email": email, "password": password], authenticated: false)
        Keychain.save(s.token, for: Self.tokenKey)
        return s
    }

    func signOut() { Keychain.delete(Self.tokenKey) }
    nonisolated var isSignedIn: Bool { Keychain.load(Self.tokenKey) != nil }

    // MARK: voice + clock

    func voiceToken() async throws -> VoiceToken {
        try await post("/api/va/desk/token", ["platform": AppConfig.platform])
    }

    func clock(_ action: String) async throws -> ClockState {
        try await post("/api/va/time/clock", ["action": action])
    }

    func clockStatus() async throws -> ClockState {
        try await post("/api/va/time/status")
    }

    // MARK: the caller

    func whois(phone: String) async throws -> Whois {
        try await post("/api/va/inbound/whois", ["phone": phone])
    }

    func recent(days: Int = 7) async throws -> RecentInbound {
        try await post("/api/va/inbound/recent", ["days": days])
    }

    func quote(phone: String, items: [String], zip: String, name: String?) async throws -> Quote {
        try await post("/api/va/inbound/quote",
                       ["phone": phone, "items": items, "zip": zip, "name": name ?? ""])
    }

    func textQuote(phone: String, items: [String], zip: String, name: String?) async throws -> OKResult {
        try await post("/api/va/inbound/quote-text",
                       ["phone": phone, "items": items, "zip": zip, "name": name ?? ""])
    }

    func book(phone: String, name: String, address: String, zip: String,
              items: [String], price: Double?, notes: String?) async throws -> BookResult {
        var body: [String: Any] = ["phone": phone, "name": name, "address": address,
                                   "zip": zip, "items": items, "notes": notes ?? ""]
        if let price { body["price"] = price }
        return try await post("/api/va/inbound/book", body)
    }

    func callback(phone: String, name: String?, when: String?, note: String?) async throws -> OKResult {
        try await post("/api/va/inbound/callback",
                       ["phone": phone, "name": name ?? "", "when": when ?? "", "note": note ?? ""])
    }

    // MARK: the outbound desk (va_calls.py)

    func nextCard(skipLeads: Bool = false) async throws -> NextCard {
        try await post("/api/va/calls/next", skipLeads ? ["skip_leads": true] : [:])
    }

    func log(prospectId: String, outcome: String, note: String?, sendText: Bool) async throws -> LogResult {
        try await post("/api/va/calls/log", ["prospect_id": prospectId, "outcome": outcome,
                                             "note": note ?? "", "send_text": sendText])
    }

    func search(_ q: String) async throws -> [QueueRow] {
        let r: SearchResults = try await post("/api/va/calls/search", ["q": q]); return r.results
    }

    func prospect(_ id: String) async throws -> NextCard {
        try await post("/api/va/calls/get", ["prospect_id": id])
    }

    func kit(prospectId: String, side: String? = nil) async throws -> Kit {
        var b: [String: Any] = ["prospect_id": prospectId]; if let side { b["side"] = side }
        return try await post("/api/va/calls/kit", b)
    }

    /// `preset` is one of the desk's keys: tomorrow_am, tomorrow_pm, two_days, next_week.
    func scheduleCallback(prospectId: String, preset: String, note: String?) async throws -> OKResult {
        try await post("/api/va/calls/callback", ["prospect_id": prospectId, "preset": preset, "note": note ?? ""])
    }

    func sendInfo(prospectId: String, channel: String = "sms", to: String? = nil) async throws -> OKResult {
        var b: [String: Any] = ["prospect_id": prospectId, "channel": channel]; if let to { b["to"] = to }
        return try await post("/api/va/calls/send-info", b)
    }

    func queue() async throws -> QueueResponse { try await post("/api/va/calls/queue") }

    func addProspect(company: String, phone: String, city: String, category: String) async throws -> OKResult {
        try await post("/api/va/calls/add", ["company": company, "phone": phone, "city": city, "category": category])
    }

    // MARK: inbox (desk_line.py)

    func inbox() async throws -> InboxResponse { try await post("/api/va/desk/inbox") }
    func unread() async throws -> Int { let u: UnreadCount = try await post("/api/va/desk/unread"); return u.unread }
    func thread(prospectId: String) async throws -> ThreadResponse { try await post("/api/va/desk/thread", ["prospect_id": prospectId]) }
    func templates(prospectId: String) async throws -> Templates { try await post("/api/va/desk/templates", ["prospect_id": prospectId]) }
    func text(prospectId: String?, to: String?, body: String) async throws -> OKResult {
        var b: [String: Any] = ["body": body]
        if let prospectId { b["prospect_id"] = prospectId }; if let to { b["to"] = to }
        return try await post("/api/va/desk/text", b)
    }

    // MARK: hours (va_time.py)

    func hours(days: Int = 30) async throws -> HoursReport { try await post("/api/va/time/hours", ["days": days]) }

    func outcome(phone: String, _ outcome: String, note: String?) async throws -> OKResult {
        try await post("/api/va/inbound/outcome",
                       ["phone": phone, "outcome": outcome, "note": note ?? ""])
    }
}

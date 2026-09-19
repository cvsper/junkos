//  Demo.swift — Umuve Desk
//  DEBUG-only: launch with `--demo home` / `--demo call` / `--demo signin` to
//  seed the screens with realistic state, so the design can be reviewed on a
//  simulator without a signed-in desk or a live phone line.

import Foundation

#if DEBUG
enum DemoQueue { static var next: NextCard?; static var inbox: InboxResponse?; static var kit: Kit? }
enum Demo {
    static var mode: String? {
        let a = CommandLine.arguments
        guard let i = a.firstIndex(of: "--demo"), i + 1 < a.count else { return nil }
        return a[i + 1]
    }

    @MainActor static func apply(to model: AppModel, voice: VoiceManager) {
        guard let m = mode, m != "signin" else { return }
        model.session = DeskSession(token: "demo", name: "Tracy", fullName: "Tracy Young",
                                    email: "tracy@demo", role: "va", isManager: false)
        model.onClock = true
        voice.registered = true
        voice.pushReady = true
        let dec = JSONDecoder()
        model.recent = try? dec.decode(RecentInbound.self, from: Data("""
        {"calls":[
          {"id":"1","phone":"(561) 555-0143","name":"Dana Whitfield","disposition":"booked","source":"meta","seconds":214,"created_at":"2026-09-19T15:12:00Z"},
          {"id":"2","phone":"(954) 555-0188","name":null,"disposition":"missed","source":"google","seconds":0,"created_at":"2026-09-19T13:40:00Z"},
          {"id":"3","phone":"(561) 555-0102","name":"Marcus Bell","disposition":"callback","source":null,"seconds":66,"created_at":"2026-09-18T22:53:00Z"},
          {"id":"4","phone":"(772) 555-0111","name":null,"disposition":"maya","source":"meta","seconds":31,"created_at":"2026-09-18T18:06:00Z"}
        ],
        "callbacks":[{"id":"c1","phone":"(561) 555-0102","name":"Marcus Bell","when":"Today after 5","note":"Garage cleanout, wants a price","status":"open"}]}
        """.utf8))
        if m == "hours" {
            model.clock = try? dec.decode(ClockState.self, from: Data("""
            {"on_clock":true,"va_name":"Tracy","today_seconds":13320,"week_seconds":61200,"period_seconds":118800,"period_label":"Sep 16 – Sep 30",
             "shift":{"id":"s0","va_name":"Tracy","started_at":"\(ISO8601DateFormatter().string(from: Date().addingTimeInterval(-13320)))","open":true,"seconds":13320}}
            """.utf8))
        }
        if m == "queue" || m == "outcall" {
            let card = try? dec.decode(Prospect.self, from: Data("""
            {"id":"p1","company":"Palm Beach Property Partners","contact_name":"Renee Alvarez","phone":"(561) 555-0177","city":"Wellington","category":"property_management",
             "tier":"A","side":"demand","status":"fresh","attempts":1,"last_outcome":"voicemail","last_note":"Gatekeeper said Renee handles vendors, back after 2.",
             "why":"Manages 14 buildings in Wellington and Royal Palm.",
             "angle":"They manage 14 buildings and every move-out leaves a pile at the curb. One vendor on file beats calling around each time.",
             "opener":"Hi Renee, it's Tracy with Umuve — we do same-day junk removal for property managers across Palm Beach. Do you have a vendor for move-out cleanouts right now?",
             "tel":"tel:+15615550177","is_followup":true,"compliance":{"dnc":false,"window_open":true}}
            """.utf8))
            let stats = DayStats(callsToday: 18, interestedToday: 3, dueNow: 12, fresh: 29)
            DemoQueue.next = NextCard(card: card, stats: stats, empty: nil, leadsFirst: nil, message: nil, waiting: nil, paid: nil, total: 41, scheduled: 6)
            DemoQueue.kit = try? dec.decode(Kit.self, from: Data("""
            {"side":"demand","track":{"pitch":"We're the vendor that shows up the same day with a price locked before the truck rolls. Your residents text us a photo, we quote it, we haul it — you never chase a contractor again.","close":"Can I put a rate card on file with you so the next move-out is one text instead of three calls?","segment":"property"},
             "objections":["We already have a guy.","Send me something in writing.","How much?"],
             "answers":{"We already have a guy.":"Great — keep him. We're the backup for the Friday afternoon he can't make. No contract.","Send me something in writing.":"Texting you the rate card now — one page, all-in prices.","How much?":"Sofa's $129 all-in, a full move-out cleanout starts at $349. The price is set before anyone shows up."},
             "prices":[{"label":"Sofa","from":"$129"},{"label":"Mattress","from":"$127"},{"label":"Cleanout","from":"$349"}],
             "price_note":"All-in — no fuel or disposal add-ons."}
            """.utf8))
            if m == "outcall", let card {
                var c = VoiceManager.ActiveCall(id: UUID(), from: "+15615550177", outbound: true, prospect: card)
                c.connected = true; c.connectedAt = Date().addingTimeInterval(-63)
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { voice.activeCall = c }
            }
        }
        if m == "inbox" {
            DemoQueue.inbox = try? dec.decode(InboxResponse.self, from: Data("""
            {"unread":2,"items":[
              {"phone_digits":"5615550177","phone":"(561) 555-0177","prospect_id":"p1","company":"Palm Beach Property Partners","city":"Wellington","preview":"Yes send me the rate card, we have two move-outs Friday","kind":"sms","unread":1,"at":"\(ISO8601DateFormatter().string(from: Date().addingTimeInterval(-1500)))"},
              {"phone_digits":"9545550188","phone":"(954) 555-0188","prospect_id":null,"company":null,"city":null,"preview":"How much for a sectional and a treadmill in Coral Springs?","kind":"sms","unread":1,"at":"\(ISO8601DateFormatter().string(from: Date().addingTimeInterval(-7200)))"},
              {"phone_digits":"5615550143","phone":"(561) 555-0143","prospect_id":"p2","company":"Dana Whitfield","city":"West Palm Beach","preview":"Thanks, the guys were great","kind":"sms","unread":0,"at":"\(ISO8601DateFormatter().string(from: Date().addingTimeInterval(-90000)))"}
            ]}
            """.utf8))
            model.unread = 2
        }
        if m == "call" {
            var c = VoiceManager.ActiveCall(id: UUID(), from: "+15615550143")
            c.connected = true
            c.connectedAt = Date().addingTimeInterval(-42)
            c.whois = try? dec.decode(Whois.self, from: Data("""
            {"kind":"customer","phone":"(561) 555-0143","phone_digits":"5615550143","source":"meta",
             "banner":"Called from the Meta ad",
             "customer":{"id":"u1","name":"Dana Whitfield","address":"1200 S Olive Ave, West Palm Beach","jobs":2,"last_job":"Aug 30","notes":"Gate code 4471. Prefers mornings."},
             "recent_calls":[{"id":"r1","disposition":"booked"},{"id":"r2","disposition":"quoted"}]}
            """.utf8))
            // CallKit resets the provider on launch (simulator especially), which
            // rightly clears any call — so seed the demo call after that settles.
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { voice.activeCall = c }
        }
    }
}
#endif

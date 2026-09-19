//  Demo.swift — Umuve Desk
//  DEBUG-only: launch with `--demo home` / `--demo call` / `--demo signin` to
//  seed the screens with realistic state, so the design can be reviewed on a
//  simulator without a signed-in desk or a live phone line.

import Foundation

#if DEBUG
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

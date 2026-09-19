//  AppModel.swift — Umuve Desk
//  Session + clock state. The voice layer is VoiceManager; this is the desk.

import Foundation
import Combine

@MainActor
final class AppModel: ObservableObject {
    @Published var session: DeskSession?
    @Published var onClock = false
    @Published var recent: RecentInbound?
    @Published var busy = false
    @Published var notice: String?

    var signedIn: Bool { session != nil || DeskAPI.shared.isSignedIn }

    func boot() async {
        guard DeskAPI.shared.isSignedIn else { return }
        await refresh()
        await VoiceManager.shared.register()
    }

    func signIn(email: String, password: String) async {
        busy = true; defer { busy = false }
        do {
            session = try await DeskAPI.shared.signIn(email: email, password: password)
            notice = nil
            await refresh()
            await VoiceManager.shared.register()
        } catch { notice = error.localizedDescription }
    }

    func signOut() async {
        await VoiceManager.shared.unregister()
        await DeskAPI.shared.signOut()
        session = nil; onClock = false; recent = nil
    }

    func refresh() async {
        async let clock = try? DeskAPI.shared.clockStatus()
        async let rec = try? DeskAPI.shared.recent(days: 7)
        if let c = await clock { onClock = c.onClock }
        recent = await rec
    }

    /// The one control on Home. On the clock = the line rings to you.
    func setOnClock(_ on: Bool) async {
        busy = true; defer { busy = false }
        do {
            let s = try await DeskAPI.shared.clock(on ? "in" : "out")
            onClock = s.onClock
            notice = nil
        } catch { notice = error.localizedDescription }
    }
}

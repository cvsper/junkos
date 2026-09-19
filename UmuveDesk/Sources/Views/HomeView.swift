//  HomeView.swift — Umuve Desk
//
//  One true sentence about the line, one control, then the work: callbacks
//  owed, then who called. Not a dashboard. The number that matters most on
//  this desk — did we answer — is what the top of the screen says.

import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var voice: VoiceManager

    private var ringing: Bool { model.onClock && voice.registered }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .firstTextBaseline) {
                    Text("umuve").font(Type.display(18)).tracking(-0.4)
                    Spacer()
                    Button("Sign out") { Task { await model.signOut() } }
                        .font(Type.smallStrong).foregroundStyle(Color.muted)
                }
                .padding(.bottom, 30)

                // The state of the line is the product.
                Text(ringing ? "The line rings to you." : "The line is not ringing to you.")
                    .font(Type.display(36)).tracking(-1.3).lineSpacing(-2)
                    .foregroundStyle(ringing ? Color.ink : Color.stop)
                    .fixedSize(horizontal: false, vertical: true)
                Text(subline)
                    .font(Type.body).foregroundStyle(Color.muted).padding(.top, 10)
                    .fixedSize(horizontal: false, vertical: true)

                PillButton(title: model.onClock ? "Clock out" : "Clock in — start taking calls",
                           tone: model.onClock ? .quiet : .go, busy: model.busy) {
                    Task { await model.setOnClock(!model.onClock) }
                }
                .padding(.top, 24)

                if let n = model.notice {
                    Text(n).font(Type.small).foregroundStyle(Color.stop).padding(.top, 10)
                }

                if let cbs = model.recent?.callbacks, !cbs.isEmpty {
                    section("Callbacks you owe") {
                        ForEach(cbs) { cb in
                            row(name: cb.name ?? cb.phone ?? "—", detail: [cb.when, cb.note].compactMap { $0 }.joined(separator: " · "),
                                trailing: cb.phone)
                        }
                    }
                }

                section("Recent calls") {
                    if let calls = model.recent?.calls, !calls.isEmpty {
                        ForEach(calls.prefix(20)) { c in
                            row(name: c.name ?? c.phone ?? "Unknown",
                                detail: [c.source.map { "from \($0)" }, c.disposition, c.seconds.map { "\($0)s" }]
                                    .compactMap { $0 }.joined(separator: " · "),
                                trailing: c.createdAt.map(shortTime))
                        }
                    } else {
                        Text("Nothing yet. When the desk line rings, it lands here.")
                            .font(Type.body).foregroundStyle(Color.muted)
                    }
                }
            }
            .padding(.horizontal, 22).padding(.top, 12).padding(.bottom, 40)
        }
        .refreshable { await model.refresh() }
    }

    private var subline: String {
        if !voice.registered {
            return voice.lastError.map { "This phone isn't registered for calls yet — \($0)" }
                ?? "Registering this phone for calls…"
        }
        if !model.onClock { return "Clock in and the desk line rings this phone, even when it's locked." }
        if voice.pushReady == false, let r = voice.pushReason { return "Calls only ring while the app is open: \(r)" }
        return "Customer calls to the desk line ring here first, like a normal phone call."
    }

    @ViewBuilder
    private func section<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(Type.title).padding(.top, 34).padding(.bottom, 10)
            VStack(spacing: 0) { content() }.glass(6)
        }
    }

    private func row(name: String, detail: String, trailing: String?) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(name).font(Type.bodyStrong).foregroundStyle(Color.ink)
                if !detail.isEmpty { Text(detail).font(Type.small).foregroundStyle(Color.muted) }
            }
            Spacer(minLength: 8)
            if let t = trailing { Text(t).font(Type.small).foregroundStyle(Color.faint) }
        }
        .padding(.horizontal, 12).padding(.vertical, 12)
        .overlay(alignment: .bottom) { Rectangle().fill(Color.line).frame(height: 1).padding(.horizontal, 12) }
    }

    private func shortTime(_ iso: String) -> String {
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let d = f.date(from: iso) ?? { f.formatOptions = [.withInternetDateTime]; return f.date(from: iso) }()
        guard let d else { return "" }
        let out = DateFormatter(); out.dateFormat = Calendar.current.isDateInToday(d) ? "h:mm a" : "EEE h:mm a"
        return out.string(from: d)
    }
}

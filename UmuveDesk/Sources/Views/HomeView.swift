//  HomeView.swift — Umuve Desk
//
//  One true sentence about the line, one control, then the work: callbacks
//  owed, then who called. Colour does the labelling — a dot per call says
//  what happened to it, so the eye reads the list before the words do.

import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var voice: VoiceManager

    private var ringing: Bool { model.onClock && voice.registered }

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    BrandRow(subtitle: "desk")
                    Spacer()
                    Button { Task { await model.signOut() } } label: {
                        Text(model.session?.name ?? "Signed in").font(Type.smallMedium).foregroundStyle(Color.muted)
                            .padding(.horizontal, 12).padding(.vertical, 7)
                            .background(Color.white.opacity(0.6), in: Capsule())
                    }.buttonStyle(.plain)
                }
                .padding(.bottom, 34)

                Text(ringing ? "The line rings to you." : "The line is not ringing to you.")
                    .font(Type.display(38)).tracking(-1.5).lineSpacing(-3)
                    .foregroundStyle(ringing ? Color.ink : Color.stop)
                    .fixedSize(horizontal: false, vertical: true)

                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Dot(color: ringing ? .go : .stop, size: 8, glow: ringing).alignmentGuide(.firstTextBaseline) { $0[.bottom] - 1 }
                    Text(statusLine).font(Type.smallMedium).foregroundStyle(Color.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(.top, 12)

                PillButton(title: model.onClock ? "Clock out" : "Clock in — start taking calls",
                           tone: model.onClock ? .quiet : .go, busy: model.busy) {
                    Task { await model.setOnClock(!model.onClock) }
                }
                .padding(.top, 22)

                if let n = model.notice {
                    Text(n).font(Type.small).foregroundStyle(Color.stop).padding(.top, 10)
                }

                if let cbs = model.recent?.callbacks, !cbs.isEmpty {
                    SectionTitle(text: "Callbacks you owe", count: cbs.count)
                    VStack(spacing: 0) {
                        ForEach(Array(cbs.enumerated()), id: \.element.id) { i, cb in
                            CallRow(tint: .warn, name: cb.name ?? cb.phone ?? "—",
                                    parts: [cb.when, cb.note].compactMap { $0 }, trailing: cb.phone, last: i == cbs.count - 1)
                        }
                    }.glass(4)
                }

                SectionTitle(text: "Recent calls")
                if let calls = model.recent?.calls, !calls.isEmpty {
                    VStack(spacing: 0) {
                        ForEach(Array(calls.prefix(20).enumerated()), id: \.element.id) { i, c in
                            CallRow(tint: .forDisposition(c.disposition), name: c.name ?? c.phone ?? "Unknown",
                                    parts: [c.source.map { "from \($0)" }, c.disposition?.replacingOccurrences(of: "_", with: " "),
                                            c.seconds.map { $0 > 0 ? "\($0)s" : nil } ?? nil].compactMap { $0 },
                                    trailing: shortTime(c.createdAt), last: i == min(calls.count, 20) - 1)
                        }
                    }.glass(4)
                } else {
                    Text("Nothing yet. When the desk line rings, it lands here.")
                        .font(Type.body).foregroundStyle(Color.muted).frame(maxWidth: .infinity, alignment: .leading).glass()
                }
            }
            .padding(.horizontal, 20).padding(.top, 10).padding(.bottom, 40)
        }
        .refreshable { await model.refresh() }
    }

    private var statusLine: String {
        if !voice.registered {
            return voice.lastError.map { "This phone isn't registered for calls — \($0)" } ?? "Registering this phone for calls…"
        }
        if !model.onClock { return "Clock in and the desk line rings this phone, even when it's locked." }
        if voice.pushReady == false, let r = voice.pushReason { return "Rings only while the app is open — \(r)" }
        return "On the clock. Customer calls ring here first, like a normal call."
    }
}

/// One call, one line: a dot for what happened, who, the details, when.
struct CallRow: View {
    let tint: Color
    let name: String
    let parts: [String]
    let trailing: String?
    var last = false

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Dot(color: tint, size: 9).padding(.top, 7)
            VStack(alignment: .leading, spacing: 3) {
                Text(name).font(Type.bodyStrong).foregroundStyle(Color.ink)
                if !parts.isEmpty {
                    // one line of detail that truncates once at the end, not per part
                    Text(parts.joined(separator: "   ·   ")).font(Type.small).foregroundStyle(Color.muted)
                        .lineLimit(2).fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 8)
            if let t = trailing, !t.isEmpty { Text(t).font(Type.small).foregroundStyle(Color.faint).padding(.top, 2) }
        }
        .padding(.horizontal, 14).padding(.vertical, 13)
        .overlay(alignment: .bottom) { if !last { Rectangle().fill(Color.line).frame(height: 1).padding(.leading, 35).padding(.trailing, 14) } }
    }
}

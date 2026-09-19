//  ProspectCallView.swift — Umuve Desk
//  On an outbound call to a prospect: who they are, the pitch, the answers to
//  the objections you'll hear, and Hang up. The outcome sheet follows.

import SwiftUI

struct ProspectCallView: View {
    @EnvironmentObject private var voice: VoiceManager
    let call: VoiceManager.ActiveCall
    @State private var kit: Kit?
    @State private var showObjections = false

    private var p: Prospect? { call.prospect }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                HStack(spacing: 8) {
                    Dot(color: call.connected ? .go : .faint, size: 8, glow: call.connected)
                    if call.connected, let at = call.connectedAt {
                        TimelineView(.periodic(from: at, by: 1)) { ctx in
                            Text(elapsed(from: at, to: ctx.date)).font(Type.smallStrong).foregroundStyle(Color.ink).monospacedDigit()
                        }
                    } else { Text("Calling…").font(Type.smallStrong).foregroundStyle(Color.muted) }
                }
                .padding(.horizontal, 12).padding(.vertical, 7).background(Color.white.opacity(0.6), in: Capsule())
                Spacer()
                Button { voice.toggleMute() } label: {
                    Text(call.muted ? "Unmute" : "Mute").font(Type.smallStrong).foregroundStyle(call.muted ? .white : Color.ink)
                        .padding(.horizontal, 14).padding(.vertical, 7).background(call.muted ? Color.dark : Color.white.opacity(0.6), in: Capsule())
                }.buttonStyle(.plain)
            }
            .padding(.bottom, 24)

            Text(p?.displayName ?? call.from).font(Type.display(34)).tracking(-1.4).lineSpacing(-2)
                .foregroundStyle(Color.ink).fixedSize(horizontal: false, vertical: true)
            Text([p?.contactName, p?.city, p?.phone].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: "  "))
                .font(Type.bodyMedium).foregroundStyle(Color.muted).padding(.top, 6)

            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 14) {
                    if let a = p?.angle, !a.isEmpty {
                        Text(a).font(.custom("Outfit-SemiBold", size: 18)).tracking(-0.3).foregroundStyle(Color.ink).fixedSize(horizontal: false, vertical: true)
                    }
                    if let t = kit?.track {
                        VStack(alignment: .leading, spacing: 10) {
                            if let pitch = t.pitch { block("Pitch", pitch) }
                            if let close = t.close { block("Close", close) }
                        }.glass(16)
                    }
                    if let obj = kit?.objections, !obj.lines.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Button { withAnimation(.snappy) { showObjections.toggle() } } label: {
                                HStack { Text("When they push back").font(Type.heading(17)).foregroundStyle(Color.ink); Spacer()
                                    Image(systemName: showObjections ? "chevron.up" : "chevron.down").font(.system(size: 13, weight: .bold)).foregroundStyle(Color.faint) }
                            }.buttonStyle(.plain)
                            if showObjections {
                                ForEach(Array(obj.lines.enumerated()), id: \.offset) { _, l in
                                    Text(l).font(Type.body).foregroundStyle(Color.ink).fixedSize(horizontal: false, vertical: true)
                                }
                                if let ans = kit?.answers, !ans.lines.isEmpty {
                                    Rectangle().fill(Color.line).frame(height: 1)
                                    ForEach(Array(ans.lines.enumerated()), id: \.offset) { _, l in
                                        Text(l).font(Type.body).foregroundStyle(Color.muted).fixedSize(horizontal: false, vertical: true)
                                    }
                                }
                            }
                        }.glass(16)
                    }
                    if let pr = kit?.prices, !pr.lines.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Prices").font(Type.heading(17)).foregroundStyle(Color.ink)
                            ForEach(Array(pr.lines.enumerated()), id: \.offset) { _, l in Text(l).font(Type.body).foregroundStyle(Color.ink) }
                            if let n = kit?.priceNote { Text(n).font(Type.small).foregroundStyle(Color.muted) }
                        }.glass(16)
                    }
                }
                .padding(.top, 18).padding(.bottom, 12)
            }

            PillButton(title: "Hang up", tone: .stop) { voice.hangUp() }
        }
        .padding(.horizontal, 20).padding(.top, 10).padding(.bottom, 18)
        .task {
            #if DEBUG
            if let k = DemoQueue.kit { kit = k; return }
            #endif
            if let id = p?.id { kit = try? await DeskAPI.shared.kit(prospectId: id, side: p?.side) }
        }
    }
    private func block(_ title: String, _ body: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(Type.small).foregroundStyle(Color.faint)
            Text(body).font(Type.body).foregroundStyle(Color.ink).lineSpacing(3).fixedSize(horizontal: false, vertical: true)
        }
    }
    private func elapsed(from: Date, to: Date) -> String { let s = max(0, Int(to.timeIntervalSince(from))); return String(format: "%d:%02d", s / 60, s % 60) }
}

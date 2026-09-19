//  TabShell.swift — Umuve Desk
//  A floating glass bar instead of the stock tab bar, so the desk's material
//  runs edge to edge. Inbox carries a red dot when something needs you.

import SwiftUI

enum Tab: String, CaseIterable, Identifiable {
    case line, queue, inbox, hours
    var id: String { rawValue }
    var title: String { switch self { case .line: "Line"; case .queue: "Queue"; case .inbox: "Inbox"; case .hours: "Hours" } }
    var symbol: String { switch self { case .line: "phone.arrow.down.left"; case .queue: "list.bullet.rectangle"; case .inbox: "bubble.left.and.text.bubble.right"; case .hours: "clock" } }
}

struct TabShell: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var voice: VoiceManager
    @State private var tab: Tab = {
        #if DEBUG
        switch Demo.mode { case "queue": return .queue; case "inbox": return .inbox; case "hours": return .hours; default: return .line }
        #else
        return .line
        #endif
    }()
    @State private var outcomeFor: Prospect?

    var body: some View {
        ZStack(alignment: .bottom) {
            Group {
                switch tab {
                case .line: HomeView()
                case .queue: QueueView()
                case .inbox: InboxView()
                case .hours: HoursView()
                }
            }
            .safeAreaPadding(.bottom, 84)

            HStack(spacing: 4) {
                ForEach(Tab.allCases) { t in
                    Button { tab = t } label: {
                        VStack(spacing: 4) {
                            ZStack(alignment: .topTrailing) {
                                Image(systemName: t.symbol).font(.system(size: 19, weight: .semibold))
                                if t == .inbox, model.unread > 0 { Dot(color: .stop, size: 7).offset(x: 6, y: -3) }
                            }
                            Text(t.title).font(Type.chip)
                        }
                        .foregroundStyle(tab == t ? Color.ink : Color.faint)
                        .frame(maxWidth: .infinity).frame(height: 56)
                        .background(tab == t ? Color.white.opacity(0.7) : .clear, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                    }.buttonStyle(.plain)
                }
            }
            .padding(5)
            .glass(0, radius: 24)
            .padding(.horizontal, 16).padding(.bottom, 6)
        }
        // an outbound call just ended: ask how it went, whichever tab is up
        .onChange(of: voice.pendingOutcomeFor?.id) { _, _ in
            if let p = voice.pendingOutcomeFor { outcomeFor = p; voice.pendingOutcomeFor = nil }
        }
        .sheet(item: $outcomeFor) { p in
            OutcomeSheet(prospect: p) { _ in outcomeFor = nil; NotificationCenter.default.post(name: .queueAdvanced, object: nil) }
                .presentationDetents([.large])
        }
    }
}

extension Notification.Name { static let queueAdvanced = Notification.Name("umuve.queueAdvanced") }

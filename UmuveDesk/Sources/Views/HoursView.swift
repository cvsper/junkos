//  HoursView.swift — Umuve Desk
//  Time on the clock. The big number is the content, not decoration.

import SwiftUI

struct HoursView: View {
    @EnvironmentObject private var model: AppModel
    @State private var report: HoursReport?

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 0) {
                HStack { BrandRow(subtitle: "hours"); Spacer() }.padding(.bottom, 30)

                if model.onClock, let start = model.clock?.shift?.startedAt, let d = parse(start) {
                    TimelineView(.periodic(from: d, by: 60)) { ctx in
                        Text(hms(Int(ctx.date.timeIntervalSince(d)) + 0)).font(Type.display(60)).tracking(-2.6).foregroundStyle(Color.ink).monospacedDigit()
                    }
                    HStack(spacing: 8) { Dot(color: .go, size: 8, glow: true); Text("On the clock since \(shortTime(start))").font(Type.smallMedium).foregroundStyle(Color.muted) }.padding(.top, 8)
                } else {
                    Text(hms(model.clock?.todaySeconds ?? 0)).font(Type.display(60)).tracking(-2.6).foregroundStyle(Color.ink).monospacedDigit()
                    HStack(spacing: 8) { Dot(color: .faint, size: 8); Text("Today. Not on the clock right now.").font(Type.smallMedium).foregroundStyle(Color.muted) }.padding(.top, 8)
                }

                PillButton(title: model.onClock ? "Clock out" : "Clock in", tone: model.onClock ? .quiet : .go, busy: model.busy) {
                    Task { await model.setOnClock(!model.onClock); report = try? await DeskAPI.shared.hours() }
                }.padding(.top, 22)

                VStack(spacing: 0) {
                    stat("This week", hms(model.clock?.weekSeconds ?? 0))
                    Rectangle().fill(Color.line).frame(height: 1).padding(.horizontal, 14)
                    stat(model.clock?.periodLabel ?? "This pay period", hms(model.clock?.periodSeconds ?? 0))
                }.glass(4).padding(.top, 26)

                SectionTitle(text: "Shifts")
                if let shifts = report?.shifts, !shifts.isEmpty {
                    VStack(spacing: 0) {
                        ForEach(Array(shifts.prefix(30).enumerated()), id: \.element.id) { i, s in
                            CallRow(tint: s.open == true ? .go : (s.unpaid == true ? .stop : .faint),
                                    name: dayLabel(s.startedAt), parts: [rangeLabel(s), s.note].compactMap { $0 }.filter { !$0.isEmpty },
                                    trailing: hms(s.seconds ?? 0), last: i == min(shifts.count, 30) - 1)
                        }
                    }.glass(4)
                } else {
                    Text("No shifts yet. Clock in and this fills up.").font(Type.body).foregroundStyle(Color.muted).frame(maxWidth: .infinity, alignment: .leading).glass()
                }
            }
            .padding(.horizontal, 20).padding(.top, 10).padding(.bottom, 30)
        }
        .refreshable { await model.refresh(); report = try? await DeskAPI.shared.hours() }
        .task { report = try? await DeskAPI.shared.hours() }
    }
    private func stat(_ k: String, _ v: String) -> some View {
        HStack { Text(k).font(Type.body).foregroundStyle(Color.muted); Spacer(); Text(v).font(Type.bodyStrong).foregroundStyle(Color.ink).monospacedDigit() }
            .padding(.horizontal, 14).padding(.vertical, 13)
    }
    private func hms(_ s: Int) -> String { String(format: "%d:%02d", s / 3600, (s % 3600) / 60) }
    private func parse(_ iso: String) -> Date? {
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: iso) { return d }; f.formatOptions = [.withInternetDateTime]; if let d = f.date(from: iso) { return d }
        let g = DateFormatter(); g.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"; g.timeZone = TimeZone(identifier: "UTC"); return g.date(from: iso)
    }
    private func dayLabel(_ iso: String?) -> String {
        guard let iso, let d = parse(iso) else { return "Shift" }
        let f = DateFormatter(); f.dateFormat = Calendar.current.isDateInToday(d) ? "'Today'" : "EEE MMM d"; return f.string(from: d)
    }
    private func rangeLabel(_ s: Shift) -> String {
        let a = shortTime(s.startedAt); let b = s.open == true ? "now" : shortTime(s.endedAt)
        return a.isEmpty ? "" : "\(a) – \(b)"
    }
}

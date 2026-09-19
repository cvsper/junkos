//  QueueView.swift — Umuve Desk
//
//  The outbound desk: one prospect at a time. The angle — the one line that
//  makes this call different from a cold call — is the loudest thing on the
//  card. The opener sits under it in the VA's own voice.

import SwiftUI

struct QueueView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var voice: VoiceManager
    @State private var next: NextCard?
    @State private var loading = true
    @State private var notice: String?
    @State private var showList = false
    @State private var showCallback = false
    @State private var manualOutcome: Prospect?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                BrandRow(subtitle: "queue")
                Spacer()
                Button { showList = true } label: {
                    Image(systemName: "line.3.horizontal").font(.system(size: 18, weight: .semibold)).foregroundStyle(Color.ink)
                        .frame(width: 40, height: 40).background(Color.white.opacity(0.6), in: Circle())
                }.buttonStyle(.plain)
            }
            .padding(.bottom, 18)

            if let s = next?.stats {
                Text(statsLine(s)).font(Type.smallMedium).foregroundStyle(Color.muted).padding(.bottom, 14)
            }

            if loading {
                Spacer(); HStack { Spacer(); ProgressView().tint(Color.ink); Spacer() }; Spacer()
            } else if let n = next, n.leadsFirst == true {
                LeadsFirst(next: n) { Task { await load(skipLeads: true) } }
            } else if let p = next?.card {
                ScrollView(showsIndicators: false) { ProspectCard(prospect: p).padding(.bottom, 8) }
                if let n = notice { Text(n).font(Type.small).foregroundStyle(Color.stop).padding(.vertical, 6) }
                HStack(spacing: 8) {
                    quiet("Text info") { Task { await textInfo(p) } }
                    quiet("Call back…") { showCallback = true }
                    quiet("Log…") { manualOutcome = p }
                }
                PillButton(title: "Call \(p.displayName)", tone: .go, busy: false) { voice.dial(p) }
                    .disabled(p.compliance?.dnc == true).opacity(p.compliance?.dnc == true ? 0.45 : 1)
                    .padding(.top, 10)
            } else {
                Spacer()
                VStack(alignment: .leading, spacing: 8) {
                    Text("The list is done.").font(Type.display(32)).tracking(-1.2).foregroundStyle(Color.ink)
                    Text(next?.scheduled.map { "\($0) callbacks are scheduled for later. Pull to refresh, or load a list from the browser desk." }
                         ?? "Nothing is due right now. Pull to refresh.").font(Type.body).foregroundStyle(Color.muted)
                }
                Spacer()
            }
        }
        .padding(.horizontal, 20).padding(.top, 10).padding(.bottom, 16)
        .task { await load() }
        .refreshable { await load() }
        .onReceive(NotificationCenter.default.publisher(for: .queueAdvanced)) { _ in Task { await load() } }
        .sheet(isPresented: $showList) { QueueListSheet { id in showList = false; Task { await open(id) } } }
        .sheet(isPresented: $showCallback) {
            if let p = next?.card { CallbackSheet(prospect: p) { showCallback = false; Task { await load() } } }
        }
        .sheet(item: $manualOutcome) { p in
            OutcomeSheet(prospect: p) { r in manualOutcome = nil; apply(r) }.presentationDetents([.large])
        }
    }

    private func statsLine(_ s: DayStats) -> String {
        let calls = s.callsToday ?? 0, int = s.interestedToday ?? 0, q = (s.dueNow ?? 0) + (s.fresh ?? 0)
        return "\(calls) call\(calls == 1 ? "" : "s") today, \(int) interested. \(q) waiting."
    }
    private func load(skipLeads: Bool = false) async {
        loading = next == nil
        defer { loading = false }
        #if DEBUG
        if let d = DemoQueue.next { next = d; return }
        #endif
        do { next = try await DeskAPI.shared.nextCard(skipLeads: skipLeads); notice = nil }
        catch { notice = error.localizedDescription }
    }
    private func open(_ id: String) async {
        do { let n = try await DeskAPI.shared.prospect(id); next = NextCard(card: n.card, stats: next?.stats, empty: nil, leadsFirst: nil, message: nil, waiting: nil, paid: nil, total: nil, scheduled: nil) }
        catch { notice = error.localizedDescription }
    }
    private func apply(_ r: LogResult) {
        next = NextCard(card: r.card, stats: r.stats ?? next?.stats, empty: r.empty, leadsFirst: nil, message: nil, waiting: nil, paid: nil, total: nil, scheduled: nil)
    }
    private func textInfo(_ p: Prospect) async {
        do { let r = try await DeskAPI.shared.sendInfo(prospectId: p.id); notice = r.error ?? nil; if r.error == nil { notice = "Info texted." } }
        catch { notice = error.localizedDescription }
    }
    private func quiet(_ t: String, _ a: @escaping () -> Void) -> some View {
        Button(action: a) {
            Text(t).font(Type.smallStrong).foregroundStyle(Color.ink).frame(maxWidth: .infinity).frame(minHeight: 44)
                .background(Color.white.opacity(0.7), in: Capsule()).overlay(Capsule().strokeBorder(Color.white.opacity(0.9)))
        }.buttonStyle(.plain)
    }
}

struct ProspectCard: View {
    let prospect: Prospect
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(prospect.displayName).font(Type.display(30)).tracking(-1.2).lineSpacing(-2)
                .foregroundStyle(Color.ink).fixedSize(horizontal: false, vertical: true)
            Text([prospect.contactName, prospect.city].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: "  "))
                .font(Type.bodyMedium).foregroundStyle(Color.muted).padding(.top, 4)

            HStack(spacing: 6) {
                if let c = prospect.category, !c.isEmpty { Chip(text: c.replacingOccurrences(of: "_", with: " ").capitalized, tint: .info) }
                if let t = prospect.tier, !t.isEmpty { Chip(text: "Tier \(t)", tint: .faint) }
                if prospect.isFollowup == true { Chip(text: "Follow-up", tint: .warn) }
                if let a = prospect.attempts, a > 0 { Chip(text: "\(a) tr\(a == 1 ? "y" : "ies")", tint: .faint) }
            }
            .padding(.top, 12)

            if let c = prospect.compliance {
                if c.dnc == true {
                    warn("On the do-not-call list" + (c.dncSource.map { " (\($0))" } ?? "") + ". Don't dial.")
                } else if c.windowOpen == false, let n = c.windowNote {
                    warn(n)
                }
            }

            if let angle = prospect.angle, !angle.isEmpty {
                Text(angle).font(.custom("Outfit-SemiBold", size: 19)).tracking(-0.4).lineSpacing(2)
                    .foregroundStyle(Color.ink).fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 20)
            }

            if let o = prospect.opener, !o.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Open with").font(Type.small).foregroundStyle(Color.faint)
                    Text(o).font(Type.body).foregroundStyle(Color.ink).lineSpacing(3).fixedSize(horizontal: false, vertical: true)
                }
                .glass(16).padding(.top, 16)
            }

            if let n = prospect.lastNote, !n.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Last time").font(Type.small).foregroundStyle(Color.faint)
                    Text(n).font(Type.body).foregroundStyle(Color.ink).fixedSize(horizontal: false, vertical: true)
                }
                .padding(.top, 16)
            }
        }
    }
    private func warn(_ s: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Rectangle().fill(Color.stop).frame(width: 3).clipShape(Capsule())
            Text(s).font(Type.smallStrong).foregroundStyle(Color.stop).fixedSize(horizontal: false, vertical: true)
        }
        .padding(.top, 14)
    }
}

struct LeadsFirst: View {
    let next: NextCard
    let skip: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("\(next.waiting ?? 0) lead\((next.waiting ?? 0) == 1 ? " is" : "s are") waiting.")
                .font(Type.display(32)).tracking(-1.2).foregroundStyle(Color.ink)
            Text(next.message ?? "They asked us. Work those on the Line tab before the list.").font(Type.body).foregroundStyle(Color.muted)
            Spacer()
            PillButton(title: "Skip to the list", tone: .quiet, action: skip)
        }
    }
}

/// Log an outcome. Greens win, ambers try again, greys close it.
struct OutcomeSheet: View {
    let prospect: Prospect
    let done: (LogResult) -> Void
    @State private var outcome: String?
    @State private var sendText = true
    @State private var note = ""
    @State private var busy = false
    @State private var error: String?

    private let rows: [[(String, String, Color)]] = [
        [("interested", "Interested", .go), ("sent_link", "Sent the link", .go)],
        [("vendor_listed", "Listed as vendor", .go), ("converted", "Converted", .go)],
        [("voicemail", "Voicemail", .warn), ("no_answer", "No answer", .warn)],
        [("not_interested", "Not interested", .faint), ("bad_number", "Bad number", .faint)],
        [("skip", "Skip for now", .faint)],
    ]

    var body: some View {
        ZStack {
            Canvas()
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text("How did it go?").font(Type.display(30)).tracking(-1.2).foregroundStyle(Color.ink)
                    Text(prospect.displayName).font(Type.bodyMedium).foregroundStyle(Color.muted)
                    VStack(spacing: 8) {
                        ForEach(0..<rows.count, id: \.self) { i in
                            HStack(spacing: 8) {
                                ForEach(rows[i], id: \.0) { key, label, tint in
                                    Button { outcome = key; sendText = ["interested", "sent_link", "voicemail"].contains(key) } label: {
                                        HStack(spacing: 8) { Dot(color: tint, size: 7); Text(label).font(Type.bodyStrong) }
                                            .frame(maxWidth: .infinity).frame(minHeight: 50)
                                            .foregroundStyle(outcome == key ? .white : Color.ink)
                                            .background(outcome == key ? Color.dark : Color.white.opacity(0.7), in: Capsule())
                                            .overlay(Capsule().strokeBorder(Color.white.opacity(0.9)))
                                    }.buttonStyle(.plain)
                                }
                            }
                        }
                    }
                    .padding(.top, 8)
                    Toggle(isOn: $sendText) { Text("Send the follow-up text").font(Type.bodyMedium).foregroundStyle(Color.ink) }
                        .tint(.go).padding(.top, 6)
                    TextField("Note for next time", text: $note, axis: .vertical).lineLimit(2...4).textFieldStyle(DeskField())
                    if let e = error { HStack(spacing: 8) { Dot(color: .stop, size: 6); Text(e).font(Type.small).foregroundStyle(Color.stop) } }
                }
                .glass(16).padding(20)
            }
        }
        .safeAreaInset(edge: .bottom) {
            PillButton(title: outcome == nil ? "Pick an outcome" : "Log it and load the next", tone: .go, busy: busy) { Task { await submit() } }
                .disabled(outcome == nil).opacity(outcome == nil ? 0.5 : 1)
                .padding(.horizontal, 20).padding(.vertical, 12)
        }
    }
    private func submit() async {
        guard let o = outcome else { return }
        busy = true; defer { busy = false }
        do {
            let r = try await DeskAPI.shared.log(prospectId: prospect.id, outcome: o, note: note, sendText: sendText)
            if let e = r.error { error = e } else { done(r) }
        } catch { self.error = error.localizedDescription }
    }
}

struct CallbackSheet: View {
    let prospect: Prospect
    let done: () -> Void
    @State private var note = ""
    @State private var busy = false
    @State private var error: String?
    private let presets = [("tomorrow_am", "Tomorrow morning"), ("tomorrow_pm", "Tomorrow afternoon"), ("two_days", "In two days"), ("next_week", "Next week")]
    var body: some View {
        ZStack {
            Canvas()
            VStack(alignment: .leading, spacing: 12) {
                Text("Call back when?").font(Type.display(30)).tracking(-1.2).foregroundStyle(Color.ink)
                Text(prospect.displayName).font(Type.bodyMedium).foregroundStyle(Color.muted)
                TextField("What to bring up", text: $note).textFieldStyle(DeskField()).padding(.top, 6)
                ForEach(presets, id: \.0) { key, label in
                    PillButton(title: label, tone: .quiet, busy: busy) { Task { await pick(key) } }
                }
                if let e = error { Text(e).font(Type.small).foregroundStyle(Color.stop) }
                Spacer()
            }
            .padding(20)
        }
        .presentationDetents([.medium, .large])
    }
    private func pick(_ preset: String) async {
        busy = true; defer { busy = false }
        do { let r = try await DeskAPI.shared.scheduleCallback(prospectId: prospect.id, preset: preset, note: note); if let e = r.error { error = e } else { done() } }
        catch { self.error = error.localizedDescription }
    }
}

struct QueueListSheet: View {
    let open: (String) -> Void
    @State private var q = ""
    @State private var results: [QueueRow] = []
    @State private var queue: QueueResponse?
    @State private var seg = 0
    var body: some View {
        ZStack {
            Canvas()
            VStack(alignment: .leading, spacing: 12) {
                Text("The list").font(Type.display(30)).tracking(-1.2).foregroundStyle(Color.ink)
                TextField("Find a business, city, or number", text: $q).textFieldStyle(DeskField())
                    .autocorrectionDisabled().onChange(of: q) { _, v in Task { results = (try? await DeskAPI.shared.search(v)) ?? [] } }
                if q.isEmpty {
                    HStack(spacing: 4) {
                        ForEach(Array(["Due now", "Later"].enumerated()), id: \.offset) { i, t in
                            Button { seg = i } label: {
                                Text(t).font(Type.smallStrong).foregroundStyle(seg == i ? .white : Color.ink)
                                    .padding(.horizontal, 14).padding(.vertical, 8)
                                    .background(seg == i ? Color.dark : Color.white.opacity(0.7), in: Capsule())
                            }.buttonStyle(.plain)
                        }
                    }
                }
                ScrollView(showsIndicators: false) {
                    let rows = q.isEmpty ? (seg == 0 ? queue?.dueRows ?? [] : queue?.laterRows ?? []) : results
                    if rows.isEmpty {
                        Text(q.isEmpty ? "Nothing here right now." : "No matches.").font(Type.body).foregroundStyle(Color.muted).padding(.top, 20)
                    } else {
                        VStack(spacing: 0) {
                            ForEach(Array(rows.enumerated()), id: \.element.id) { i, r in
                                Button { open(r.id) } label: {
                                    CallRow(tint: .forDisposition(r.lastOutcome), name: r.company ?? r.phone ?? "—",
                                            parts: [r.city, r.category?.replacingOccurrences(of: "_", with: " "), r.lastOutcome?.replacingOccurrences(of: "_", with: " ")].compactMap { $0 }.filter { !$0.isEmpty },
                                            trailing: shortTime(r.dueAt), last: i == rows.count - 1)
                                }.buttonStyle(.plain)
                            }
                        }.glass(4)
                    }
                }
            }
            .padding(20)
        }
        .task { queue = try? await DeskAPI.shared.queue() }
    }
}

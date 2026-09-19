//  CallView.swift — Umuve Desk
//
//  What's under your thumb once you've answered. The caller's name at display
//  size, one line of what the desk knows, the facts, and the four things you
//  can do — Book in green, in the thumb zone.

import SwiftUI

struct CallView: View {
    @EnvironmentObject private var voice: VoiceManager
    let call: VoiceManager.ActiveCall
    @State private var sheet: Sheet?
    @State private var toast: String?

    enum Sheet: Identifiable { case quote, book, callback, notFit; var id: Int { hashValue } }
    private var phone: String { call.whois?.phone ?? call.from }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                HStack(spacing: 8) {
                    Dot(color: call.connected ? .go : .faint, size: 8, glow: call.connected)
                    if call.connected, let at = call.connectedAt {
                        TimelineView(.periodic(from: at, by: 1)) { ctx in
                            Text(elapsed(from: at, to: ctx.date)).font(Type.smallStrong).foregroundStyle(Color.ink).monospacedDigit()
                        }
                    } else {
                        Text("Connecting…").font(Type.smallStrong).foregroundStyle(Color.muted)
                    }
                }
                .padding(.horizontal, 12).padding(.vertical, 7)
                .background(Color.white.opacity(0.6), in: Capsule())
                Spacer()
                Button { voice.toggleMute() } label: {
                    Text(call.muted ? "Unmute" : "Mute").font(Type.smallStrong).foregroundStyle(call.muted ? .white : Color.ink)
                        .padding(.horizontal, 14).padding(.vertical, 7)
                        .background(call.muted ? Color.dark : Color.white.opacity(0.6), in: Capsule())
                }.buttonStyle(.plain)
            }
            .padding(.bottom, 28)

            Text(call.whois?.displayName ?? "Unknown caller")
                .font(Type.display(40)).tracking(-1.6).lineSpacing(-3)
                .foregroundStyle(Color.ink).fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 10) {
                Text(knownLine).font(Type.bodyMedium).foregroundStyle(Color.muted)
                if let src = call.whois?.source, !src.isEmpty { Chip(text: sourceLabel(src), tint: .stop) }
            }
            .padding(.top, 8)

            if let w = call.whois, !facts(w).isEmpty {
                VStack(spacing: 0) {
                    ForEach(Array(facts(w).enumerated()), id: \.offset) { i, f in
                        HStack(alignment: .top, spacing: 12) {
                            Text(f.0).font(Type.small).foregroundStyle(Color.faint).frame(width: 66, alignment: .leading).padding(.top, 2)
                            Text(f.1).font(Type.bodyMedium).foregroundStyle(Color.ink).fixedSize(horizontal: false, vertical: true)
                            Spacer(minLength: 0)
                        }
                        .padding(.horizontal, 14).padding(.vertical, 11)
                        .overlay(alignment: .bottom) { if i < facts(w).count - 1 { Rectangle().fill(Color.line).frame(height: 1).padding(.horizontal, 14) } }
                    }
                }
                .glass(4).padding(.top, 20)
            }

            Spacer(minLength: 16)

            if let t = toast {
                HStack(spacing: 8) { Dot(color: .go, size: 6); Text(t).font(Type.smallStrong).foregroundStyle(Color.go) }.padding(.bottom, 12)
            }

            HStack(spacing: 8) {
                small("Quote") { sheet = .quote }
                small("Callback") { sheet = .callback }
                small("Not a fit") { sheet = .notFit }
            }
            PillButton(title: "Book this job", tone: .go) { sheet = .book }.padding(.top, 10)
            PillButton(title: "Hang up", tone: .stop) { voice.hangUp() }.padding(.top, 10)
        }
        .padding(.horizontal, 20).padding(.top, 10).padding(.bottom, 18)
        .sheet(item: $sheet) { which in
            ActionSheetView(kind: which, phone: phone, name: call.whois?.displayName) { msg in toast = msg; sheet = nil }
                .presentationDetents([.large])
        }
    }

    private var knownLine: String {
        guard let w = call.whois else { return "Looking them up… \(call.from)" }
        switch w.kind {
        case "customer": return "Customer  \(w.phone ?? call.from)"
        case "prospect": return "In the desk queue  \(w.phone ?? call.from)"
        default: return "New caller  \(w.phone ?? call.from)"
        }
    }
    private func sourceLabel(_ s: String) -> String {
        switch s.lowercased() { case "meta": "Meta ad"; case "google": "Google LSA"; case "thumbtack": "Thumbtack"; default: s.capitalized }
    }
    private func facts(_ w: Whois) -> [(String, String)] {
        var out: [(String, String)] = []
        if let c = w.customer {
            if let a = c.address, !a.isEmpty { out.append(("Where", a)) }
            if let j = c.jobs, j > 0 { out.append(("History", "\(j) job\(j == 1 ? "" : "s") with us" + (c.lastJob.map { ", last \($0)" } ?? ""))) }
            if let n = c.notes, !n.isEmpty { out.append(("Notes", n)) }
        }
        if let p = w.prospect {
            if let co = p.company, !co.isEmpty { out.append(("Company", co)) }
            if let n = p.notes, !n.isEmpty { out.append(("Notes", n)) }
        }
        if let cb = w.callback { out.append(("Asked", "Call back" + (cb.when.map { " \($0)" } ?? ""))) }
        if let prior = w.recentCalls, !prior.isEmpty {
            out.append(("Calls", "\(prior.count) before" + (prior.first?.disposition.map { ", last \($0.replacingOccurrences(of: "_", with: " "))" } ?? "")))
        }
        return out
    }
    private func elapsed(from: Date, to: Date) -> String {
        let s = max(0, Int(to.timeIntervalSince(from))); return String(format: "%d:%02d", s / 60, s % 60)
    }
    private func small(_ title: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title).font(Type.bodyStrong).foregroundStyle(Color.ink)
                .frame(maxWidth: .infinity).frame(minHeight: 48)
                .background(Color.white.opacity(0.72), in: Capsule())
                .overlay(Capsule().strokeBorder(Color.white.opacity(0.9), lineWidth: 1))
                .shadow(color: Color(hex: 0x181A22).opacity(0.08), radius: 14, y: 8)
        }.buttonStyle(.plain)
    }
}

/// Quote / Book / Callback / Not a fit — one sheet, the fields each needs.
struct ActionSheetView: View {
    let kind: CallView.Sheet
    let phone: String
    let name: String?
    let done: (String) -> Void

    @State private var customer = ""
    @State private var address = ""
    @State private var zip = ""
    @State private var items = ""
    @State private var when = ""
    @State private var note = ""
    @State private var price: Double?
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ZStack {
                Canvas()
                ScrollView {
                    VStack(alignment: .leading, spacing: 10) {
                        Text(title).font(Type.display(30)).tracking(-1.2).foregroundStyle(Color.ink)
                        Text(phone).font(Type.bodyMedium).foregroundStyle(Color.muted).padding(.bottom, 8)
                        Group {
                            switch kind {
                            case .quote:
                                field("Items, comma separated (sofa, mattress, 6 boxes)", $items)
                                field("ZIP", $zip).keyboardType(.numberPad)
                                if let p = price {
                                    Text("$\(p, specifier: "%.0f")").font(Type.display(48)).tracking(-2).foregroundStyle(Color.go).padding(.top, 10)
                                    Text("All-in. Say it, then text it so they have it.").font(Type.small).foregroundStyle(Color.muted)
                                }
                            case .book:
                                field("Customer name", $customer); field("Pickup address", $address)
                                field("ZIP", $zip).keyboardType(.numberPad); field("Items, comma separated", $items)
                                field("Notes for the hauler (gate code, floor, etc.)", $note)
                            case .callback:
                                field("Name", $customer); field("When (tomorrow 10am, after 5, …)", $when); field("What they want", $note)
                            case .notFit:
                                field("Why (out of area, wrong service, spam)", $note)
                            }
                        }
                        .textFieldStyle(DeskField())
                        if let e = error {
                            HStack(spacing: 8) { Dot(color: .stop, size: 6); Text(e).font(Type.small).foregroundStyle(Color.stop) }
                        }
                    }
                    .glass(14)
                    .padding(20)
                }
            }
            .safeAreaInset(edge: .bottom) {
                Group {
                    if kind == .quote {
                        PillButton(title: price == nil ? "Get the price" : "Text them this price", tone: price == nil ? .dark : .go, busy: busy) { Task { await quote(text: price != nil) } }
                    } else {
                        PillButton(title: cta, tone: kind == .book ? .go : .dark, busy: busy) { Task { await submit() } }
                    }
                }
                .padding(.horizontal, 20).padding(.vertical, 12)
            }
        }
        .onAppear { customer = name ?? "" }
    }

    private var title: String {
        switch kind { case .quote: "Price it"; case .book: "Book the job"; case .callback: "Call them back"; case .notFit: "Not a fit" }
    }
    private var cta: String {
        switch kind { case .quote: "Get the price"; case .book: "Book it and text the pay link"; case .callback: "Set the callback"; case .notFit: "Close it out" }
    }
    private var itemList: [String] { items.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty } }
    private func field(_ placeholder: String, _ text: Binding<String>) -> some View { TextField(placeholder, text: text).autocorrectionDisabled() }

    private func quote(text: Bool) async {
        busy = true; defer { busy = false }; error = nil
        do {
            if text {
                let r = try await DeskAPI.shared.textQuote(phone: phone, items: itemList, zip: zip, name: customer)
                if let e = r.error { error = e } else { done("Price texted to \(phone).") }
            } else {
                let q = try await DeskAPI.shared.quote(phone: phone, items: itemList, zip: zip, name: customer)
                if let e = q.error { error = e } else { price = q.total }
            }
        } catch { self.error = error.localizedDescription }
    }

    private func submit() async {
        busy = true; defer { busy = false }; error = nil
        do {
            switch kind {
            case .book:
                let r = try await DeskAPI.shared.book(phone: phone, name: customer, address: address, zip: zip, items: itemList, price: nil, notes: note)
                if let e = r.error { error = e } else { done(r.message ?? "Booked. The pay link is on its way.") }
            case .callback:
                let r = try await DeskAPI.shared.callback(phone: phone, name: customer, when: when, note: note)
                if let e = r.error { error = e } else { done(r.message ?? "Callback set.") }
            case .notFit:
                let r = try await DeskAPI.shared.outcome(phone: phone, "not_fit", note: note)
                if let e = r.error { error = e } else { done("Closed out.") }
            case .quote: break
            }
        } catch { self.error = error.localizedDescription }
    }
}

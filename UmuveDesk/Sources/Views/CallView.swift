//  CallView.swift — Umuve Desk
//
//  What's under your thumb once you've answered. The caller's name at display
//  size, one line of what the desk knows, prior calls, and the four things you
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
            HStack {
                Circle().fill(call.connected ? Color.go : Color.faint).frame(width: 9, height: 9)
                Text(call.connected ? "On the line" : "Connecting…").font(Type.smallStrong).foregroundStyle(Color.muted)
                Spacer()
                Button(call.muted ? "Unmute" : "Mute") { voice.toggleMute() }
                    .font(Type.smallStrong).foregroundStyle(Color.ink)
            }
            .padding(.bottom, 26)

            Text(call.whois?.displayName ?? "Unknown caller")
                .font(Type.display(40)).tracking(-1.4).lineSpacing(-2)
                .foregroundStyle(Color.ink).fixedSize(horizontal: false, vertical: true)
            Text(knownLine).font(Type.body).foregroundStyle(Color.muted).padding(.top, 8)

            if let w = call.whois {
                VStack(alignment: .leading, spacing: 0) {
                    if let b = w.banner, !b.isEmpty { fact(b) }
                    if let c = w.customer {
                        if let a = c.address, !a.isEmpty { fact(a) }
                        if let j = c.jobs, j > 0 { fact("\(j) job\(j == 1 ? "" : "s") with us" + (c.lastJob.map { " · last \($0)" } ?? "")) }
                        if let n = c.notes, !n.isEmpty { fact(n) }
                    }
                    if let p = w.prospect {
                        if let co = p.company, !co.isEmpty { fact(co) }
                        if let n = p.notes, !n.isEmpty { fact(n) }
                    }
                    if let cb = w.callback { fact("Asked for a callback" + (cb.when.map { " · \($0)" } ?? "")) }
                    if let prior = w.recentCalls, !prior.isEmpty {
                        fact("Called \(prior.count) time\(prior.count == 1 ? "" : "s") before" +
                             (prior.first?.disposition.map { " · last: \($0)" } ?? ""))
                    }
                }
                .glass(6).padding(.top, 20)
            }

            Spacer(minLength: 20)

            if let t = toast { Text(t).font(Type.smallStrong).foregroundStyle(Color.go).padding(.bottom, 10) }

            HStack(spacing: 10) {
                small("Quote") { sheet = .quote }
                small("Callback") { sheet = .callback }
                small("Not a fit") { sheet = .notFit }
            }
            PillButton(title: "Book this job", tone: .go) { sheet = .book }.padding(.top, 10)
            PillButton(title: "Hang up", tone: .stop) { voice.hangUp() }.padding(.top, 10)
        }
        .padding(.horizontal, 22).padding(.top, 12).padding(.bottom, 20)
        .sheet(item: $sheet) { which in
            ActionSheetView(kind: which, phone: phone, name: call.whois?.displayName) { msg in
                toast = msg; sheet = nil
            }
            .presentationDetents([.large])
        }
    }

    private var knownLine: String {
        guard let w = call.whois else { return "Looking them up… \(call.from)" }
        switch w.kind {
        case "customer": return "Customer · \(w.phone ?? call.from)"
        case "prospect": return "In the desk queue · \(w.phone ?? call.from)"
        default: return (w.source.map { "New caller from \($0) · " } ?? "New caller · ") + (w.phone ?? call.from)
        }
    }

    private func fact(_ s: String) -> some View {
        Text(s).font(Type.body).foregroundStyle(Color.ink)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 12).padding(.vertical, 11)
            .overlay(alignment: .bottom) { Rectangle().fill(Color.line).frame(height: 1).padding(.horizontal, 12) }
    }

    private func small(_ title: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title).font(Type.bodyStrong).foregroundStyle(Color.ink)
                .frame(maxWidth: .infinity).frame(minHeight: 50)
                .background(Color.raise, in: Capsule())
                .overlay(Capsule().stroke(Color.ink.opacity(0.16)))
        }
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
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text(title).font(Type.display(30)).tracking(-1).padding(.bottom, 6)
                    Text(phone).font(Type.body).foregroundStyle(Color.muted)

                    switch kind {
                    case .quote:
                        field("Items, comma separated (sofa, mattress, 6 boxes)", $items)
                        field("ZIP", $zip).keyboardType(.numberPad)
                        if let p = price {
                            Text("$\(p, specifier: "%.0f")").font(Type.display(46)).tracking(-1.6).foregroundStyle(Color.go).padding(.top, 8)
                            Text("All-in. Say it, then text it so they have it.").font(Type.small).foregroundStyle(Color.muted)
                        }
                    case .book:
                        field("Customer name", $customer)
                        field("Pickup address", $address)
                        field("ZIP", $zip).keyboardType(.numberPad)
                        field("Items, comma separated", $items)
                        field("Notes for the hauler (gate code, floor, etc.)", $note)
                    case .callback:
                        field("Name", $customer)
                        field("When (tomorrow 10am, after 5, …)", $when)
                        field("What they want", $note)
                    case .notFit:
                        field("Why (out of area, wrong service, spam)", $note)
                    }

                    if let e = error { Text(e).font(Type.small).foregroundStyle(Color.stop) }
                }
                .textFieldStyle(DeskField())
                .padding(22)
            }
            .background(Color.canvas)
            .safeAreaInset(edge: .bottom) {
                VStack(spacing: 10) {
                    if kind == .quote {
                        PillButton(title: price == nil ? "Get the price" : "Text them this price", tone: price == nil ? .dark : .go, busy: busy) { Task { await quote(text: price != nil) } }
                    } else {
                        PillButton(title: cta, tone: kind == .book ? .go : .dark, busy: busy) { Task { await submit() } }
                    }
                }
                .padding(.horizontal, 22).padding(.vertical, 12).background(Color.canvas)
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

    private func field(_ placeholder: String, _ text: Binding<String>) -> some View {
        TextField(placeholder, text: text).autocorrectionDisabled()
    }

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
                let r = try await DeskAPI.shared.book(phone: phone, name: customer, address: address, zip: zip,
                                                      items: itemList, price: nil, notes: note)
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

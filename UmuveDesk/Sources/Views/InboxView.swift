//  InboxView.swift — Umuve Desk
//  Texts on the desk line. A red dot is a reply nobody has read yet.

import SwiftUI

struct InboxView: View {
    @EnvironmentObject private var model: AppModel
    @State private var inbox: InboxResponse?
    @State private var loading = true

    var body: some View {
        NavigationStack {
            ZStack {
                Canvas()
                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 0) {
                        HStack { BrandRow(subtitle: "inbox"); Spacer()
                            if let u = inbox?.unread, u > 0 { Chip(text: "\(u) unread", tint: .stop) } }
                            .padding(.bottom, 22)
                        if loading {
                            HStack { Spacer(); ProgressView().tint(Color.ink); Spacer() }.padding(.top, 40)
                        } else if let items = inbox?.items, !items.isEmpty {
                            VStack(spacing: 0) {
                                ForEach(Array(items.enumerated()), id: \.element.id) { i, it in
                                    NavigationLink { ThreadView(item: it) } label: {
                                        CallRow(tint: (it.unread ?? 0) > 0 ? .stop : (it.kind == "call" ? .info : .faint),
                                                name: it.company ?? it.phone ?? it.phoneDigits,
                                                parts: [it.preview].compactMap { $0 }, trailing: shortTime(it.at), last: i == items.count - 1)
                                    }.buttonStyle(.plain)
                                }
                            }.glass(4)
                        } else {
                            Text("No texts yet. Replies to anything the desk sends land here.")
                                .font(Type.body).foregroundStyle(Color.muted).frame(maxWidth: .infinity, alignment: .leading).glass()
                        }
                    }
                    .padding(.horizontal, 20).padding(.top, 10).padding(.bottom, 30)
                }
                .refreshable { await load() }
            }
            .toolbar(.hidden, for: .navigationBar)
        }
        .task { await load() }
    }
    private func load() async {
        loading = inbox == nil; defer { loading = false }
        #if DEBUG
        if let d = DemoQueue.inbox { inbox = d; return }
        #endif
        inbox = try? await DeskAPI.shared.inbox()
        if let u = inbox?.unread { model.unread = u }
    }
}

struct ThreadView: View {
    let item: InboxItem
    @Environment(\.dismiss) private var dismiss
    @State private var thread: ThreadResponse?
    @State private var templates: Templates?
    @State private var draft = ""
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        ZStack {
            Canvas()
            VStack(spacing: 0) {
                HStack(spacing: 12) {
                    Button { dismiss() } label: {
                        Image(systemName: "chevron.left").font(.system(size: 16, weight: .bold)).foregroundStyle(Color.ink)
                            .frame(width: 38, height: 38).background(Color.white.opacity(0.6), in: Circle())
                    }.buttonStyle(.plain)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(item.company ?? item.phone ?? item.phoneDigits).font(Type.heading(19)).tracking(-0.4).foregroundStyle(Color.ink)
                        Text([item.city, item.phone].compactMap { $0 }.joined(separator: "  ")).font(Type.small).foregroundStyle(Color.muted)
                    }
                    Spacer()
                }
                .padding(.horizontal, 20).padding(.top, 10).padding(.bottom, 12)

                ScrollViewReader { proxy in
                    ScrollView(showsIndicators: false) {
                        VStack(spacing: 8) {
                            ForEach(thread?.messages ?? []) { m in Bubble(m: m).id(m.id) }
                        }
                        .padding(.horizontal, 20).padding(.bottom, 12)
                    }
                    .onChange(of: thread?.messages.count) { _, _ in if let l = thread?.messages.last { proxy.scrollTo(l.id, anchor: .bottom) } }
                }

                VStack(spacing: 8) {
                    if let t = templates {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 6) {
                                ForEach([("Intro", t.intro), ("Info", t.info), ("Follow-up", t.followup)], id: \.0) { label, text in
                                    if let text, !text.isEmpty {
                                        Button { draft = text } label: { Chip(text: label, tint: .info) }.buttonStyle(.plain)
                                    }
                                }
                            }
                        }
                    }
                    HStack(alignment: .bottom, spacing: 8) {
                        TextField("Text \(item.company ?? "them")", text: $draft, axis: .vertical).lineLimit(1...5).textFieldStyle(DeskField())
                        Button { Task { await send() } } label: {
                            Image(systemName: "arrow.up").font(.system(size: 17, weight: .bold)).foregroundStyle(.white)
                                .frame(width: 48, height: 48).background(draft.isEmpty ? Color.faint : Color.go, in: Circle())
                        }.buttonStyle(.plain).disabled(draft.isEmpty || busy)
                    }
                    if let e = error { Text(e).font(Type.small).foregroundStyle(Color.stop) }
                }
                .padding(.horizontal, 20).padding(.vertical, 10)
                .background(.ultraThinMaterial)
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .task {
            if let pid = item.prospectId {
                thread = try? await DeskAPI.shared.thread(prospectId: pid)
                templates = try? await DeskAPI.shared.templates(prospectId: pid)
            }
        }
    }
    private func send() async {
        busy = true; defer { busy = false }
        let body = draft
        do {
            let r = try await DeskAPI.shared.text(prospectId: item.prospectId, to: item.prospectId == nil ? item.phoneDigits : nil, body: body)
            if let e = r.error { error = e } else { draft = ""; if let pid = item.prospectId { thread = try? await DeskAPI.shared.thread(prospectId: pid) } }
        } catch { self.error = error.localizedDescription }
    }
}

struct Bubble: View {
    let m: ThreadMessage
    private var mine: Bool { m.direction == "out" }
    var body: some View {
        if m.kind == "call" {
            HStack { Spacer()
                HStack(spacing: 6) { Dot(color: .info, size: 6); Text(callLine).font(Type.small).foregroundStyle(Color.muted) }
                Spacer() }.padding(.vertical, 4)
        } else {
            HStack {
                if mine { Spacer(minLength: 60) }
                VStack(alignment: mine ? .trailing : .leading, spacing: 3) {
                    Text(m.body ?? "").font(Type.body).foregroundStyle(mine ? .white : Color.ink).lineSpacing(2)
                        .padding(.horizontal, 14).padding(.vertical, 10)
                        .background(mine ? Color.dark : Color.white.opacity(0.78), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                    Text([shortTime(m.createdAt), mine ? m.status : nil].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: "  "))
                        .font(.custom("DMSans-Regular", size: 11.5)).foregroundStyle(Color.faint)
                }
                if !mine { Spacer(minLength: 60) }
            }
        }
    }
    private var callLine: String {
        let dir = m.direction == "out" ? "Called them" : "They called"
        return m.duration.map { "\(dir), \($0)s" } ?? dir
    }
}

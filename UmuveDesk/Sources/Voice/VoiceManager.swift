//  VoiceManager.swift — Umuve Desk
//
//  The whole reason the app exists. PushKit wakes us for a call while the
//  phone is locked; we hand the payload to Twilio, which gives us a CallInvite;
//  we report it to CallKit so iOS shows a real full-screen incoming call; the
//  person answers on that screen; CallKit tells us; we accept the invite.
//
//  Order matters on iOS: every VoIP push MUST be reported to CallKit before
//  the push handler returns, or the system kills the app. Twilio's
//  callInviteReceived fires synchronously inside handleNotification, so the
//  report happens inside it.

import Foundation
import Combine
import CallKit
import PushKit
import AVFAudio
import TwilioVoice

@MainActor
final class VoiceManager: NSObject, ObservableObject {
    static let shared = VoiceManager()

    // What the screens read.
    @Published var registered = false           // Twilio knows this device
    @Published var pushReady = false            // token carried a push credential
    @Published var pushReason: String?          // why not, in the server's words
    @Published var activeCall: ActiveCall?      // nil when idle
    @Published var lastError: String?

    struct ActiveCall: Identifiable {
        let id: UUID
        let from: String                        // E.164 or digits from Twilio
        var outbound = false
        var prospect: Prospect?                 // set when we dialed the desk queue
        var connected = false
        var connectedAt: Date?
        var muted = false
        var whois: Whois?
    }
    /// The last outbound call that ended, so the queue can ask for its outcome.
    @Published var pendingOutcomeFor: Prospect?
    var vaName: String = ""

    private let audioDevice = DefaultAudioDevice()
    private let provider: CXProvider
    private let callController = CXCallController()
    private var registry: PKPushRegistry?
    private var deviceToken: Data?
    private var accessToken: String?
    private var refreshTimer: Timer?

    private var invites: [UUID: CallInvite] = [:]
    private var calls: [UUID: Call] = [:]

    private override init() {
        let cfg = CXProviderConfiguration()
        cfg.supportsVideo = false
        cfg.maximumCallGroups = 1
        cfg.maximumCallsPerCallGroup = 1
        cfg.supportedHandleTypes = [.phoneNumber]
        cfg.includesCallsInRecents = true
        provider = CXProvider(configuration: cfg)
        super.init()
        provider.setDelegate(self, queue: nil)
        TwilioVoiceSDK.audioDevice = audioDevice
    }

    // MARK: lifecycle

    /// Call once at launch. PushKit registration is cheap and must exist
    /// before the first sign-in so the token is ready when we need it.
    func start() {
        guard registry == nil else { return }
        let r = PKPushRegistry(queue: .main)
        r.delegate = self
        r.desiredPushTypes = [.voIP]
        registry = r
    }

    /// Fetch a voice token and register this device. Safe to call repeatedly;
    /// it is also what the refresh timer calls.
    func register() async {
        do {
            let t = try await DeskAPI.shared.voiceToken()
            pushReady = t.push ?? false
            pushReason = t.pushReason ?? (t.enabled ? nil : t.reason)
            guard t.enabled, let jwt = t.token else {
                registered = false
                lastError = t.reason
                return
            }
            accessToken = jwt
            scheduleRefresh(ttl: t.ttl ?? 3600)
            try await registerIfReady()
        } catch {
            lastError = error.localizedDescription
            registered = false
        }
    }

    func unregister() async {
        refreshTimer?.invalidate()
        guard let jwt = accessToken, let dev = deviceToken else { registered = false; return }
        try? await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
            TwilioVoiceSDK.unregister(accessToken: jwt, deviceToken: dev) { e in
                e.map { c.resume(throwing: $0) } ?? c.resume()
            }
        }
        registered = false
    }

    private func registerIfReady() async throws {
        guard let jwt = accessToken, let dev = deviceToken else { return }
        try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
            TwilioVoiceSDK.register(accessToken: jwt, deviceToken: dev) { e in
                e.map { c.resume(throwing: $0) } ?? c.resume()
            }
        }
        registered = true
        lastError = nil
    }

    private func scheduleRefresh(ttl: Int) {
        refreshTimer?.invalidate()
        // Refresh at 80% of the TTL so a call never lands on a dead token.
        let after = max(60, Double(ttl) * 0.8)
        refreshTimer = Timer.scheduledTimer(withTimeInterval: after, repeats: false) { [weak self] _ in
            Task { await self?.register() }
        }
    }

    // MARK: outbound — the desk queue dials through CallKit so it's a real call

    func dial(_ prospect: Prospect) {
        guard let number = prospect.dialNumber, accessToken != nil, activeCall == nil else {
            lastError = accessToken == nil ? "Not registered for calls yet." : (activeCall != nil ? "Already on a call." : "No number for this prospect."); return
        }
        let id = UUID()
        activeCall = ActiveCall(id: id, from: number, outbound: true, prospect: prospect)
        let action = CXStartCallAction(call: id, handle: CXHandle(type: .phoneNumber, value: number))
        action.isVideo = false
        callController.request(CXTransaction(action: action)) { [weak self] e in
            if let e { Task { @MainActor in self?.lastError = e.localizedDescription; self?.endedCall(id) } }
        }
    }

    // MARK: in-call controls

    func hangUp() {
        guard let id = activeCall?.id else { return }
        callController.request(CXTransaction(action: CXEndCallAction(call: id))) { _ in }
    }

    func toggleMute() {
        guard var c = activeCall else { return }
        c.muted.toggle()
        calls[c.id]?.isMuted = c.muted
        activeCall = c
    }

    /// Put the caller's name on the CallKit screen once the desk knows who it is.
    private func resolveCaller(_ id: UUID, from: String) {
        Task {
            guard let w = try? await DeskAPI.shared.whois(phone: from) else { return }
            if var c = activeCall, c.id == id { c.whois = w; activeCall = c }
            let update = CXCallUpdate()
            update.localizedCallerName = w.displayName == "Unknown caller"
                ? (w.phone ?? from) : "\(w.displayName) · \(w.phone ?? from)"
            provider.reportCall(with: id, updated: update)
        }
    }

    private func endedCall(_ id: UUID) {
        invites[id] = nil
        calls[id] = nil
        if let c = activeCall, c.id == id {
            if c.outbound, let p = c.prospect { pendingOutcomeFor = p }
            activeCall = nil
        }
    }
}

// MARK: - PushKit

extension VoiceManager: PKPushRegistryDelegate {
    nonisolated func pushRegistry(_ registry: PKPushRegistry, didUpdate credentials: PKPushCredentials, for type: PKPushType) {
        guard type == .voIP else { return }
        Task { @MainActor in
            self.deviceToken = credentials.token
            try? await self.registerIfReady()
        }
    }

    nonisolated func pushRegistry(_ registry: PKPushRegistry, didInvalidatePushTokenFor type: PKPushType) {
        Task { @MainActor in self.deviceToken = nil; self.registered = false }
    }

    nonisolated func pushRegistry(_ registry: PKPushRegistry, didReceiveIncomingPushWith payload: PKPushPayload,
                                  for type: PKPushType, completion: @escaping () -> Void) {
        guard type == .voIP else { completion(); return }
        // handleNotification calls callInviteReceived synchronously on this
        // thread, which reports to CallKit — satisfying iOS before we return.
        MainActor.assumeIsolated {
            _ = TwilioVoiceSDK.handleNotification(payload.dictionaryPayload, delegate: self, delegateQueue: nil)
        }
        completion()
    }
}

// MARK: - Twilio notifications

extension VoiceManager: NotificationDelegate {
    nonisolated func callInviteReceived(callInvite: CallInvite) {
        MainActor.assumeIsolated {
            let id = UUID()
            let from = callInvite.from ?? "Unknown"
            invites[id] = callInvite
            activeCall = ActiveCall(id: id, from: from)

            let update = CXCallUpdate()
            update.remoteHandle = CXHandle(type: .phoneNumber, value: from)
            update.localizedCallerName = from
            update.hasVideo = false
            provider.reportNewIncomingCall(with: id, update: update) { [weak self] error in
                if let error { Task { @MainActor in self?.lastError = error.localizedDescription; self?.endedCall(id) } }
            }
            resolveCaller(id, from: from)
        }
    }

    nonisolated func cancelledCallInviteReceived(cancelledCallInvite: CancelledCallInvite, error: Error) {
        MainActor.assumeIsolated {
            // The caller hung up (or someone else on the desk answered first).
            for (id, inv) in invites where inv.callSid == cancelledCallInvite.callSid {
                provider.reportCall(with: id, endedAt: Date(), reason: .remoteEnded)
                endedCall(id)
            }
        }
    }
}

// MARK: - CallKit

extension VoiceManager: CXProviderDelegate {
    nonisolated func providerDidReset(_ provider: CXProvider) {
        MainActor.assumeIsolated {
            audioDevice.isEnabled = false
            calls.values.forEach { $0.disconnect() }
            calls.removeAll(); invites.removeAll(); activeCall = nil
        }
    }

    nonisolated func provider(_ provider: CXProvider, perform action: CXAnswerCallAction) {
        MainActor.assumeIsolated {
            guard let invite = invites[action.callUUID] else { action.fail(); return }
            audioDevice.isEnabled = false
            audioDevice.block()
            let options = AcceptOptions(callInvite: invite) { b in b.uuid = action.callUUID }
            let call = invite.accept(options: options, delegate: self)
            calls[action.callUUID] = call
            invites[action.callUUID] = nil
            action.fulfill()
        }
    }

    nonisolated func provider(_ provider: CXProvider, perform action: CXStartCallAction) {
        MainActor.assumeIsolated {
            guard let jwt = accessToken, let ac = activeCall, ac.id == action.callUUID else { action.fail(); return }
            audioDevice.isEnabled = false
            audioDevice.block()
            let opts = ConnectOptions(accessToken: jwt) { b in
                // Same params the browser desk sends the TwiML app (desk_line.twilio_voice)
                var p = ["To": ac.from, "va_name": self.vaName]
                if let pid = ac.prospect?.id { p["prospect_id"] = pid }
                b.params = p
                b.uuid = action.callUUID
            }
            calls[action.callUUID] = TwilioVoiceSDK.connect(options: opts, delegate: self)
            provider.reportOutgoingCall(with: action.callUUID, startedConnectingAt: Date())
            action.fulfill()
        }
    }

    nonisolated func provider(_ provider: CXProvider, perform action: CXEndCallAction) {
        MainActor.assumeIsolated {
            if let inv = invites[action.callUUID] { inv.reject() }
            calls[action.callUUID]?.disconnect()
            endedCall(action.callUUID)
            action.fulfill()
        }
    }

    nonisolated func provider(_ provider: CXProvider, perform action: CXSetMutedCallAction) {
        MainActor.assumeIsolated {
            calls[action.callUUID]?.isMuted = action.isMuted
            if var c = activeCall, c.id == action.callUUID { c.muted = action.isMuted; activeCall = c }
            action.fulfill()
        }
    }

    nonisolated func provider(_ provider: CXProvider, didActivate audioSession: AVAudioSession) {
        MainActor.assumeIsolated { audioDevice.isEnabled = true }
    }

    nonisolated func provider(_ provider: CXProvider, didDeactivate audioSession: AVAudioSession) {
        MainActor.assumeIsolated { audioDevice.isEnabled = false }
    }
}

// MARK: - Twilio call

extension VoiceManager: CallDelegate {
    nonisolated func callDidConnect(call: Call) {
        MainActor.assumeIsolated {
            if var c = activeCall, calls[c.id] === call {
                c.connected = true; c.connectedAt = Date(); activeCall = c
                if c.outbound { provider.reportOutgoingCall(with: c.id, connectedAt: Date()) }
            }
        }
    }
    nonisolated func callDidFailToConnect(call: Call, error: Error) {
        MainActor.assumeIsolated {
            lastError = error.localizedDescription
            if let id = calls.first(where: { $0.value === call })?.key {
                provider.reportCall(with: id, endedAt: Date(), reason: .failed); endedCall(id)
            }
        }
    }
    nonisolated func callDidDisconnect(call: Call, error: Error?) {
        MainActor.assumeIsolated {
            if let id = calls.first(where: { $0.value === call })?.key {
                provider.reportCall(with: id, endedAt: Date(), reason: error == nil ? .remoteEnded : .failed)
                endedCall(id)
            }
        }
    }
    nonisolated func callDidStartRinging(call: Call) {}
    nonisolated func callDidReconnect(call: Call) {}
    nonisolated func callIsReconnecting(call: Call, error: Error) {}
}

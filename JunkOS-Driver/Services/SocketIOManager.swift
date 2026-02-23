//
//  SocketIOManager.swift
//  Umuve Pro
//
//  Socket.IO manager for real-time GPS streaming and job alerts.
//  Depends on SocketIO SPM package (socket.io-client-swift).
//

import Foundation
import SocketIO

extension Notification.Name {
    static let jobWasAccepted = Notification.Name("jobWasAccepted")
    static let newJobAvailable = Notification.Name("newJobAvailable")
}

@Observable
final class SocketIOManager {
    static let shared = SocketIOManager()

    private var manager: SocketManager?
    private var socket: SocketIOClient?

    var isConnected = false
    var newJobAlert: DriverJob?
    var assignedJobId: String?

    private var pendingDriverId: String?

    private init() {}

    // MARK: - Connection

    func connect(token: String, contractorId: String? = nil) {
        pendingDriverId = contractorId

        let url = URL(string: AppConfig.shared.socketURL)!
        manager = SocketManager(socketURL: url, config: [
            .log(true),  // Enable logging to debug connection
            .compress,
            .connectParams(["token": token]),
            // Use polling first, upgrade to WebSocket (more reliable than forceWebsockets)
            .reconnects(true),
            .reconnectAttempts(-1),  // Infinite reconnection attempts
            .reconnectWait(1),       // Faster reconnection: 1 second (was 2)
            .reconnectWaitMax(5),    // Cap max wait at 5 seconds
            .extraHeaders(["X-Client-Type": "ios-driver"])  // Help backend identify mobile clients
        ])

        socket = manager?.defaultSocket

        socket?.on(clientEvent: .connect) { [weak self] _, _ in
            print("🟢 SocketIO: Connected!")
            self?.isConnected = true

            // Join driver room after connection is established
            if let driverId = self?.pendingDriverId {
                self?.socket?.emit("join", ["room": "driver:\(driverId)"])
                print("🔵 SocketIO: Joined driver room: driver:\(driverId)")
            } else {
                print("⚠️ SocketIO: No pendingDriverId - cannot join room")
            }
        }

        socket?.on(clientEvent: .disconnect) { [weak self] data, _ in
            print("🔴 SocketIO: Disconnected! Reason: \(data)")
            self?.isConnected = false
        }

        socket?.on(clientEvent: .reconnect) { data, _ in
            print("🔄 SocketIO: Reconnecting... Attempt: \(data)")
        }

        socket?.on(clientEvent: .reconnectAttempt) { data, _ in
            print("🔄 SocketIO: Reconnect attempt: \(data)")
        }

        socket?.on(clientEvent: .error) { data, _ in
            print("❌ SocketIO Error: \(data)")
        }

        socket?.on(clientEvent: .statusChange) { data, _ in
            print("📊 SocketIO Status Change: \(data)")
        }

        socket?.on("job:new") { [weak self] data, _ in
            guard let dict = data.first as? [String: Any],
                  let jsonData = try? JSONSerialization.data(withJSONObject: dict),
                  let job = try? JSONDecoder().decode(DriverJob.self, from: jsonData) else { return }
            self?.newJobAlert = job
            // Also post to NotificationCenter for JobFeedView
            DispatchQueue.main.async {
                NotificationCenter.default.post(
                    name: .newJobAvailable,
                    object: nil,
                    userInfo: ["job": job]
                )
            }
        }

        // Listen for direct job assignments (auto-assigned or admin-assigned)
        socket?.on("job:assigned") { [weak self] data, _ in
            guard let dict = data.first as? [String: Any],
                  let jobId = dict["job_id"] as? String else { return }
            self?.assignedJobId = jobId

            // Notify UI to refresh active jobs
            DispatchQueue.main.async {
                NotificationCenter.default.post(
                    name: NSNotification.Name("socket:job:assigned"),
                    object: nil,
                    userInfo: ["job_id": jobId]
                )
            }
            print("🟢 SocketIO: Job assigned - \(jobId)")
        }

        // Listen for job acceptance by other drivers (remove from feed)
        socket?.on("job:accepted") { data, _ in
            guard let dict = data.first as? [String: Any],
                  let jobId = dict["job_id"] as? String else { return }
            DispatchQueue.main.async {
                NotificationCenter.default.post(
                    name: .jobWasAccepted,
                    object: nil,
                    userInfo: ["job_id": jobId]
                )
            }
        }

        // Listen for room join confirmation from backend
        socket?.on("joined") { [weak self] data, _ in
            guard let dict = data.first as? [String: Any],
                  let room = dict["room"] as? String else { return }
            print("✅ SocketIO: Successfully joined room: \(room)")
            self?.isConnected = true
        }

        // Listen for volume adjustment approval
        socket?.on("volume:approved") { data, _ in
            NotificationCenter.default.post(
                name: NSNotification.Name("socket:volume:approved"),
                object: nil,
                userInfo: data.first as? [String: Any]
            )
        }

        // Listen for volume adjustment decline
        socket?.on("volume:declined") { data, _ in
            NotificationCenter.default.post(
                name: NSNotification.Name("socket:volume:declined"),
                object: nil,
                userInfo: data.first as? [String: Any]
            )
        }

        socket?.connect()
    }

    func disconnect() {
        socket?.disconnect()
        manager = nil
        socket = nil
        isConnected = false
    }

    // MARK: - GPS Streaming

    func emitLocation(lat: Double, lng: Double, contractorId: String? = nil, jobId: String? = nil) {
        var data: [String: Any] = ["lat": lat, "lng": lng]
        if let contractorId { data["contractor_id"] = contractorId }
        if let jobId { data["job_id"] = jobId }
        socket?.emit("driver:location", data)
    }

    // MARK: - Room Management

    func joinDriverRoom(driverId: String) {
        print("🔵 SocketIO: Manually joining driver room: driver:\(driverId)")
        socket?.emit("join", ["room": "driver:\(driverId)"])
        pendingDriverId = driverId // Update in case we reconnect
    }

    func leaveDriverRoom(driverId: String) {
        socket?.emit("leave", ["room": "driver:\(driverId)"])
    }
}

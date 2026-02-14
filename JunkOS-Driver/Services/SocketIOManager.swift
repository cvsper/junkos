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

    private init() {}

    // MARK: - Connection

    func connect(token: String) {
        let url = URL(string: AppConfig.shared.socketURL)!
        manager = SocketManager(socketURL: url, config: [
            .log(false),
            .compress,
            .connectParams(["token": token]),
            .forceWebsockets(true),
        ])

        socket = manager?.defaultSocket

        socket?.on(clientEvent: .connect) { [weak self] _, _ in
            self?.isConnected = true
        }

        socket?.on(clientEvent: .disconnect) { [weak self] _, _ in
            self?.isConnected = false
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
        }

        // Listen for job acceptance by other drivers (remove from feed)
        socket?.on("job:accepted") { [weak self] data, _ in
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
        socket?.emit("join", ["room": "driver:\(driverId)"])
    }

    func leaveDriverRoom(driverId: String) {
        socket?.emit("leave", ["room": "driver:\(driverId)"])
    }
}

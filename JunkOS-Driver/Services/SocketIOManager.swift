//
//  SocketIOManager.swift
//  JunkOS Driver
//
//  Socket.IO manager for real-time GPS streaming and job alerts.
//  Depends on SocketIO SPM package (socket.io-client-swift).
//

import Foundation
import SocketIO

@Observable
final class SocketIOManager {
    static let shared = SocketIOManager()

    private var manager: SocketManager?
    private var socket: SocketIOClient?

    var isConnected = false
    var newJobAlert: DriverJob?

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

    func emitLocation(lat: Double, lng: Double) {
        socket?.emit("driver:location", ["lat": lat, "lng": lng])
    }

    // MARK: - Room Management

    func joinDriverRoom(driverId: String) {
        socket?.emit("join", ["room": "driver:\(driverId)"])
    }

    func leaveDriverRoom(driverId: String) {
        socket?.emit("leave", ["room": "driver:\(driverId)"])
    }
}

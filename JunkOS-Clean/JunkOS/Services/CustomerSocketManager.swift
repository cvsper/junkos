//
//  CustomerSocketManager.swift
//  Umuve
//
//  Socket.IO manager for customer app - listens for driver location updates
//  and job status changes during active jobs.
//

import Foundation
import SocketIO

class CustomerSocketManager: ObservableObject {
    static let shared = CustomerSocketManager()

    private var manager: SocketManager?
    private var socket: SocketIOClient?

    @Published var isConnected = false
    @Published var driverLatitude: Double?
    @Published var driverLongitude: Double?

    private init() {}

    // MARK: - Connection

    func connect(token: String) {
        let url = URL(string: Config.shared.socketURL)!
        manager = SocketManager(socketURL: url, config: [
            .log(false),
            .compress,
            .connectParams(["token": token]),
            .forceWebsockets(true),
        ])

        socket = manager?.defaultSocket

        socket?.on(clientEvent: .connect) { [weak self] _, _ in
            DispatchQueue.main.async {
                self?.isConnected = true
            }
        }

        socket?.on(clientEvent: .disconnect) { [weak self] _, _ in
            DispatchQueue.main.async {
                self?.isConnected = false
            }
        }

        // Listen for driver location updates
        socket?.on("driver:location") { [weak self] data, _ in
            guard let dict = data.first as? [String: Any],
                  let lat = dict["lat"] as? Double,
                  let lng = dict["lng"] as? Double else { return }

            DispatchQueue.main.async {
                self?.driverLatitude = lat
                self?.driverLongitude = lng

                // Post notification for views to update
                NotificationCenter.default.post(
                    name: NSNotification.Name("driverLocationUpdated"),
                    object: nil
                )
            }
        }

        // Listen for job status changes
        socket?.on("job:status") { data, _ in
            guard let dict = data.first as? [String: Any] else { return }

            DispatchQueue.main.async {
                NotificationCenter.default.post(
                    name: NSNotification.Name("jobStatusUpdated"),
                    object: nil,
                    userInfo: dict
                )
            }
        }

        socket?.connect()
    }

    func disconnect() {
        socket?.disconnect()
        manager = nil
        socket = nil

        DispatchQueue.main.async {
            self.isConnected = false
            self.driverLatitude = nil
            self.driverLongitude = nil
        }
    }

    // MARK: - Room Management

    func joinJobRoom(jobId: String) {
        socket?.emit("customer:join", ["job_id": jobId])
    }

    func leaveJobRoom(jobId: String) {
        socket?.emit("customer:leave", ["job_id": jobId])
    }
}

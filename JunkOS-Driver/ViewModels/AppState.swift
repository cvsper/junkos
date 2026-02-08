//
//  AppState.swift
//  JunkOS Driver
//
//  Root observable state for the entire app.
//  Tracks auth, online status, active job, contractor profile.
//

import Foundation

@Observable
final class AppState {
    // Auth
    let auth = AuthenticationManager()

    // Contractor
    var contractorProfile: ContractorProfile?
    var isRegistered: Bool { contractorProfile != nil }
    var isApproved: Bool { contractorProfile?.approval == .approved }

    // Online status
    var isOnline = false

    // Active job
    var activeJob: DriverJob?

    // Location
    let locationManager = LocationManager()

    // Socket
    let socket = SocketIOManager.shared

    // Navigation
    var showingSplash = true

    private let api = DriverAPIClient.shared

    // MARK: - Load Profile

    func loadContractorProfile() async {
        do {
            let response = try await api.getContractorProfile()
            contractorProfile = response.contractor
            isOnline = response.contractor.isOnline
        } catch {
            contractorProfile = nil
        }
    }

    // MARK: - Online Toggle

    var toggleError: String?

    func toggleOnline() async {
        guard contractorProfile != nil else {
            toggleError = "Complete contractor registration first."
            return
        }
        let newState = !isOnline
        do {
            let response = try await api.updateAvailability(isOnline: newState)
            isOnline = response.contractor.isOnline
            contractorProfile = response.contractor
            toggleError = nil

            if isOnline {
                startLocationTracking()
            } else {
                stopLocationTracking()
            }
        } catch {
            toggleError = error.localizedDescription
            // Toggle locally for demo even if API fails
            isOnline = newState
            if isOnline {
                startLocationTracking()
            } else {
                stopLocationTracking()
            }
        }
    }

    // MARK: - Location Tracking

    func startLocationTracking() {
        locationManager.requestPermission()
        locationManager.startTracking()

        guard let token = KeychainHelper.loadString(forKey: "authToken") else { return }
        socket.connect(token: token)

        if let contractorId = contractorProfile?.id {
            socket.joinDriverRoom(driverId: contractorId)
        }

        locationManager.onLocationUpdate = { [weak self] location in
            let lat = location.coordinate.latitude
            let lng = location.coordinate.longitude

            // Emit via socket for real-time
            self?.socket.emitLocation(lat: lat, lng: lng)

            // Also update via REST periodically
            Task {
                _ = try? await DriverAPIClient.shared.updateLocation(lat: lat, lng: lng)
            }
        }
    }

    func stopLocationTracking() {
        locationManager.stopTracking()
        locationManager.onLocationUpdate = nil

        if let contractorId = contractorProfile?.id {
            socket.leaveDriverRoom(driverId: contractorId)
        }
        socket.disconnect()
    }
}

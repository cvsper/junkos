//
//  AppState.swift
//  Umuve Pro
//
//  Root observable state for the entire app.
//  Tracks auth, online status, active job, contractor profile.
//

import Foundation

enum SelectedRole: String {
    case contractor
    case operator_
}

@Observable
final class AppState {
    // Auth
    let auth = AuthenticationManager()

    // Role selection (before registration)
    var selectedRole: SelectedRole?

    // Contractor
    var contractorProfile: ContractorProfile?
    var isRegistered: Bool { contractorProfile != nil }
    var isApproved: Bool { contractorProfile?.approval == .approved }
    var isOperator: Bool { contractorProfile?.isOperator == true }
    var hasCompletedStripeConnect: Bool { contractorProfile?.stripeConnectId != nil }

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
    private var isProfileLoadInFlight = false
    private var lastProfileLoadAt: Date?
    private let minProfileReloadInterval: TimeInterval = 5

    // MARK: - Load Profile

    func loadContractorProfile(retries: Int = 2, force: Bool = false) async {
        if isProfileLoadInFlight {
            return
        }

        if !force,
           let lastProfileLoadAt,
           Date().timeIntervalSince(lastProfileLoadAt) < minProfileReloadInterval {
            return
        }

        isProfileLoadInFlight = true
        defer {
            isProfileLoadInFlight = false
            lastProfileLoadAt = Date()
        }

        // No auth token means profile fetch will always fail; skip network call.
        guard KeychainHelper.loadString(forKey: "authToken") != nil else {
            contractorProfile = nil
            isOnline = false
            return
        }

        var attempts = 0
        var lastError: Error?

        while attempts <= retries {
            do {
                let response = try await api.getContractorProfile()
                contractorProfile = response.contractor
                isOnline = response.contractor.isOnline

                // Keep runtime tracking/socket state aligned when online.
                // Avoid forcing disconnects from periodic profile refreshes;
                // explicit offline/logout/background paths handle teardown.
                if isOnline {
                    startLocationTracking()
                }

                // Re-register push token now that we have an auth context
                registerPushTokenIfNeeded()
                print("✅ Profile loaded successfully")

                // Load active job after profile loads
                await loadActiveJob()
                return
            } catch {
                lastError = error
                attempts += 1

                // Only clear profile on auth errors, not on network/server errors
                if let apiError = error as? APIError,
                   case .unauthorized = apiError {
                    contractorProfile = nil
                    auth.logout()
                    print("❌ Auth error - logged out")
                    return
                }

                // For network errors, retry with delay
                if attempts <= retries {
                    print("⚠️ Profile load attempt \(attempts) failed, retrying in \(attempts * 3)s...")
                    try? await Task.sleep(nanoseconds: UInt64(attempts * 3_000_000_000))
                }
            }
        }

        // All retries exhausted
        if let error = lastError {
            print("❌ Failed to load profile after \(retries + 1) attempts: \(error.localizedDescription)")
        }
    }

    // MARK: - Load Active Job

    func loadActiveJob() async {
        do {
            let response = try await api.getCurrentJob()
            activeJob = response.job
            if let job = response.job {
                print("✅ Active job loaded: \(job.id) - \(job.jobStatus.displayName)")
            } else {
                print("ℹ️ No active job")
            }
        } catch {
            print("⚠️ Failed to load active job: \(error.localizedDescription)")
            // Don't clear activeJob on error - might be temporary network issue
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
                // CRITICAL: Load profile first to ensure we have contractor ID
                await loadContractorProfile()
                startLocationTracking()
            } else {
                stopLocationTracking()
            }
        } catch {
            toggleError = error.localizedDescription
            // Keep local state aligned with backend when availability update fails.
        }
    }

    // MARK: - Location Tracking

    func startLocationTracking() {
        locationManager.requestPermission()
        locationManager.startTracking()

        guard let token = KeychainHelper.loadString(forKey: "authToken") else { return }

        // Connect to socket - it will auto-join room after handshake completes
        socket.connect(token: token, contractorId: contractorProfile?.id)

        locationManager.onLocationUpdate = { [weak self] location in
            let lat = location.coordinate.latitude
            let lng = location.coordinate.longitude

            // Emit via socket for real-time (include contractor_id and active job_id)
            self?.socket.emitLocation(
                lat: lat,
                lng: lng,
                contractorId: self?.contractorProfile?.id,
                jobId: self?.activeJob?.id
            )

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

    // MARK: - Push Notifications

    /// Re-register push token with backend after login or profile load
    func registerPushTokenIfNeeded() {
        NotificationManager.shared.reRegisterTokenIfNeeded()
    }

    // MARK: - Job Alerts

    /// Consume the latest socket job alert (returns it and clears the socket state).
    func consumeJobAlert() -> DriverJob? {
        guard let job = socket.newJobAlert else { return nil }
        socket.newJobAlert = nil
        return job
    }

    /// Consume a direct job assignment ID (auto-assigned or admin-assigned).
    func consumeAssignment() -> String? {
        guard let jobId = socket.assignedJobId else { return nil }
        socket.assignedJobId = nil
        return jobId
    }
}

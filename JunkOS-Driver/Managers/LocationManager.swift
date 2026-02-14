//
//  LocationManager.swift
//  Umuve Pro
//
//  Continuous GPS location updates for background tracking.
//  Streams location to the backend via Socket.IO and REST.
//

import CoreLocation
import SwiftUI

@Observable
final class LocationManager: NSObject, CLLocationManagerDelegate {
    private let clManager = CLLocationManager()

    var currentLocation: CLLocation?
    var authorizationStatus: CLAuthorizationStatus = .notDetermined
    var isTracking = false

    /// Callback fired every time a new location arrives while tracking.
    var onLocationUpdate: ((CLLocation) -> Void)?

    // MARK: - Active Job Streaming

    var activeJobId: String?
    var contractorId: String?
    private var lastEmitTime: Date?
    private let emitInterval: TimeInterval = 5.0

    override init() {
        super.init()
        clManager.delegate = self
        clManager.desiredAccuracy = kCLLocationAccuracyNearestTenMeters
        clManager.distanceFilter = 20
        authorizationStatus = clManager.authorizationStatus
    }

    // MARK: - Authorization

    func requestPermission() {
        switch clManager.authorizationStatus {
        case .notDetermined:
            clManager.requestWhenInUseAuthorization()
        case .authorizedWhenInUse:
            clManager.requestAlwaysAuthorization()
        default:
            break
        }
    }

    // MARK: - Tracking

    func startTracking() {
        guard !isTracking else { return }

        // Only enable background location if we have "always" authorization
        // and the background modes entitlement is present
        if clManager.authorizationStatus == .authorizedAlways {
            if Bundle.main.backgroundModes.contains("location") {
                clManager.allowsBackgroundLocationUpdates = true
                clManager.showsBackgroundLocationIndicator = true
            }
        }
        clManager.pausesLocationUpdatesAutomatically = false
        clManager.startUpdatingLocation()
        isTracking = true
    }

    func stopTracking() {
        clManager.stopUpdatingLocation()
        isTracking = false
    }

    /// Start tracking with active job context for Socket.IO streaming
    func startActiveJobTracking(jobId: String, contractorId: String) {
        self.activeJobId = jobId
        self.contractorId = contractorId
        startTracking()
    }

    /// Stop active job tracking and clear streaming context
    func stopActiveJobTracking() {
        self.activeJobId = nil
        self.contractorId = nil
        self.lastEmitTime = nil
        stopTracking()
    }

    // MARK: - One-shot

    func requestLocation() {
        clManager.requestLocation()
    }

    // MARK: - CLLocationManagerDelegate

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        authorizationStatus = manager.authorizationStatus
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last else { return }
        currentLocation = loc
        onLocationUpdate?(loc)

        // Throttled Socket.IO emission during active jobs
        if let activeJobId = activeJobId,
           let contractorId = contractorId {
            let now = Date()
            let shouldEmit = lastEmitTime == nil || now.timeIntervalSince(lastEmitTime!) >= emitInterval
            if shouldEmit {
                SocketIOManager.shared.emitLocation(
                    lat: loc.coordinate.latitude,
                    lng: loc.coordinate.longitude,
                    contractorId: contractorId,
                    jobId: activeJobId
                )
                lastEmitTime = now
            }
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        // Silently handle — not critical enough to surface to user.
    }
}

// MARK: - Bundle Background Modes Helper

private extension Bundle {
    var backgroundModes: [String] {
        (infoDictionary?["UIBackgroundModes"] as? [String]) ?? []
    }
}

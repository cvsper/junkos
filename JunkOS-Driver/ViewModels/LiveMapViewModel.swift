//
//  LiveMapViewModel.swift
//  JunkOS Driver
//
//  Map state management: job polling, routing, alert countdown.
//

import Foundation
import MapKit
import SwiftUI

@Observable
final class LiveMapViewModel {
    // MARK: - Map State

    var cameraPosition: MapCameraPosition = .userLocation(fallback: .automatic)
    var nearbyJobs: [DriverJob] = []
    var selectedJob: DriverJob?

    // MARK: - Job Alert

    var incomingJobAlert: DriverJob?
    var alertCountdown: Int = 30

    // MARK: - Accepted Job

    var acceptedJob: DriverJob?
    var route: MKRoute?
    var routeETA: String?

    // MARK: - UI State

    var isLoadingJobs = false
    var errorMessage: String?
    var isUpdatingStatus = false

    // MARK: - Stats (for bottom strip)

    var todayEarnings: Double = 0
    var todayJobsCount: Int = 0

    // MARK: - Private

    private let api = DriverAPIClient.shared
    private var pollingTimer: Timer?
    private var countdownTimer: Timer?

    // MARK: - Lifecycle

    func startPolling() {
        fetchJobs()
        pollingTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            self?.fetchJobs()
        }
    }

    func stopPolling() {
        pollingTimer?.invalidate()
        pollingTimer = nil
        stopCountdown()
    }

    // MARK: - Job Fetching

    private func fetchJobs() {
        Task { @MainActor in
            do {
                let response = try await api.getAvailableJobs()
                nearbyJobs = response.jobs
            } catch {
                // Silently fail — jobs will refresh next cycle
            }
        }
    }

    // MARK: - Incoming Job Alert

    func showJobAlert(_ job: DriverJob) {
        // Don't show if we already have an active job
        guard acceptedJob == nil else { return }
        incomingJobAlert = job
        alertCountdown = 30
        HapticManager.shared.heavyTap()
        startCountdown()
    }

    private func startCountdown() {
        stopCountdown()
        countdownTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            guard let self else { return }
            if self.alertCountdown > 0 {
                self.alertCountdown -= 1
            } else {
                self.declineJob()
            }
        }
    }

    private func stopCountdown() {
        countdownTimer?.invalidate()
        countdownTimer = nil
    }

    // MARK: - Accept / Decline

    func acceptJob() {
        guard let job = incomingJobAlert else { return }
        stopCountdown()
        let jobId = job.id

        Task { @MainActor in
            do {
                let response = try await api.acceptJob(jobId: jobId)
                acceptedJob = response.job
                incomingJobAlert = nil
                HapticManager.shared.success()
                // Calculate route
                if let lat = response.job.lat, let lng = response.job.lng {
                    await calculateRoute(to: CLLocationCoordinate2D(latitude: lat, longitude: lng))
                }
            } catch {
                errorMessage = error.localizedDescription
                HapticManager.shared.error()
                incomingJobAlert = nil
            }
        }
    }

    func declineJob() {
        stopCountdown()
        incomingJobAlert = nil
    }

    // MARK: - Route Calculation

    func calculateRoute(to destination: CLLocationCoordinate2D) async {
        let request = MKDirections.Request()
        request.source = MKMapItem.forCurrentLocation()
        request.destination = MKMapItem(placemark: MKPlacemark(coordinate: destination))
        request.transportType = .automobile

        do {
            let directions = MKDirections(request: request)
            let response = try await directions.calculate()
            if let firstRoute = response.routes.first {
                route = firstRoute
                let minutes = Int(firstRoute.expectedTravelTime / 60)
                routeETA = "\(minutes) min"
                // Adjust camera to show route
                cameraPosition = .rect(firstRoute.polyline.boundingMapRect)
            }
        } catch {
            routeETA = nil
        }
    }

    // MARK: - Job Status Updates

    func markEnRoute() async {
        guard let job = acceptedJob else { return }
        isUpdatingStatus = true
        do {
            let response = try await api.updateJobStatus(jobId: job.id, status: "en_route")
            acceptedJob = response.job
            HapticManager.shared.success()
        } catch {
            errorMessage = error.localizedDescription
            HapticManager.shared.error()
        }
        isUpdatingStatus = false
    }

    func markArrived() async {
        guard let job = acceptedJob else { return }
        isUpdatingStatus = true
        do {
            let response = try await api.updateJobStatus(jobId: job.id, status: "arrived")
            acceptedJob = response.job
            HapticManager.shared.success()
        } catch {
            errorMessage = error.localizedDescription
            HapticManager.shared.error()
        }
        isUpdatingStatus = false
    }

    func markStarted() async {
        guard let job = acceptedJob else { return }
        isUpdatingStatus = true
        do {
            let response = try await api.updateJobStatus(jobId: job.id, status: "started")
            acceptedJob = response.job
            HapticManager.shared.success()
        } catch {
            errorMessage = error.localizedDescription
            HapticManager.shared.error()
        }
        isUpdatingStatus = false
    }

    func markCompleted() async {
        guard let job = acceptedJob else { return }
        isUpdatingStatus = true
        do {
            let response = try await api.updateJobStatus(jobId: job.id, status: "completed")
            acceptedJob = response.job
            acceptedJob = nil
            route = nil
            routeETA = nil
            HapticManager.shared.success()
        } catch {
            errorMessage = error.localizedDescription
            HapticManager.shared.error()
        }
        isUpdatingStatus = false
    }

    // MARK: - Navigation

    func openInAppleMaps() {
        guard let job = acceptedJob, let lat = job.lat, let lng = job.lng else { return }
        let coordinate = CLLocationCoordinate2D(latitude: lat, longitude: lng)
        let placemark = MKPlacemark(coordinate: coordinate)
        let mapItem = MKMapItem(placemark: placemark)
        mapItem.name = job.shortAddress
        mapItem.openInMaps(launchOptions: [
            MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeDriving
        ])
    }

    // MARK: - Cleanup

    func clearAcceptedJob() {
        acceptedJob = nil
        route = nil
        routeETA = nil
    }
}

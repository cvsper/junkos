//
//  LiveMapViewModel.swift
//  Umuve Pro
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

    // MARK: - In-App Navigation

    var isNavigating = false
    var navigationSteps: [MKRoute.Step] = []
    var currentStepIndex = 0
    var isFollowingNavigationCamera = true
    var currentStep: MKRoute.Step? {
        guard currentStepIndex < navigationSteps.count else { return nil }
        return navigationSteps[currentStepIndex]
    }

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
    private var recenterTimer: Timer?
    private var hasLoggedApprovalWarning = false

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
        recenterTimer?.invalidate()
        recenterTimer = nil
    }

    // MARK: - Job Fetching

    private func fetchJobs() {
        Task { @MainActor in
            do {
                let response = try await api.getAvailableJobs()
                nearbyJobs = response.jobs
                hasLoggedApprovalWarning = false
                print("📋 LiveMapViewModel: Fetched \(response.jobs.count) available jobs")
            } catch {
                if let apiError = error as? APIError,
                   case let .server(message) = apiError,
                   message.localizedCaseInsensitiveContains("not approved") {
                    nearbyJobs = []
                    if !hasLoggedApprovalWarning {
                        print("ℹ️ LiveMapViewModel: Contractor not approved yet; skipping job polling")
                        hasLoggedApprovalWarning = true
                    }
                    return
                }
                print("❌ LiveMapViewModel: Failed to fetch jobs - \(error.localizedDescription)")
                if let apiError = error as? APIError {
                    print("   API Error details: \(apiError)")
                }
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
        guard let job = incomingJobAlert else {
            stopCountdown()
            incomingJobAlert = nil
            return
        }
        stopCountdown()
        let jobId = job.id

        // If this was an assigned job (not just a nearby alert), call decline API
        if job.status == "assigned" || job.driverId != nil {
            Task { @MainActor in
                _ = try? await api.declineJob(jobId: jobId)
            }
        }

        incomingJobAlert = nil
    }

    /// Handle a direct job assignment from the backend (auto or admin assigned).
    func handleAssignment(jobId: String) {
        Task { @MainActor in
            do {
                // Fetch the job details
                let response = try await api.getAvailableJobs()
                if let job = response.jobs.first(where: { $0.id == jobId }) {
                    showJobAlert(job)
                }
            } catch {
                errorMessage = "Failed to load assigned job"
            }
        }
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
            // Auto-start navigation when marking en route
            startNavigation()
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
            stopNavigation()
            HapticManager.shared.success()
        } catch {
            errorMessage = error.localizedDescription
            HapticManager.shared.error()
        }
        isUpdatingStatus = false
    }

    // MARK: - Navigation

    func startNavigation() {
        isNavigating = true
        if let route {
            navigationSteps = route.steps
            currentStepIndex = navigationSteps.firstIndex(where: { !$0.instructions.isEmpty }) ?? 0
        } else {
            navigationSteps = []
            currentStepIndex = 0
        }
        isFollowingNavigationCamera = true
        HapticManager.shared.lightTap()
    }

    func stopNavigation() {
        isNavigating = false
        navigationSteps = []
        currentStepIndex = 0
        isFollowingNavigationCamera = true
        recenterTimer?.invalidate()
        recenterTimer = nil
        cameraPosition = .userLocation(fallback: .automatic)
    }

    func advanceToNextStep() {
        if currentStepIndex < navigationSteps.count - 1 {
            currentStepIndex += 1
            HapticManager.shared.lightTap()
        }
    }

    func updateNavigationCamera(using location: CLLocation) {
        guard isNavigating, isFollowingNavigationCamera else { return }
        cameraPosition = .camera(makeNavigationCamera(for: location))
    }

    func userInteractedWithMap() {
        guard isNavigating else { return }
        isFollowingNavigationCamera = false
        recenterTimer?.invalidate()
        recenterTimer = Timer.scheduledTimer(withTimeInterval: 4, repeats: false) { [weak self] _ in
            self?.isFollowingNavigationCamera = true
        }
    }

    /// Called when driver location updates during navigation.
    /// Auto-advances to next step when driver is within threshold of step endpoint.
    func updateNavigationLocation(_ location: CLLocation) {
        guard isNavigating, let step = currentStep else { return }
        updateNavigationCamera(using: location)

        // Get the endpoint of the current step (where the next instruction begins)
        let stepPolyline = step.polyline
        let stepEndCoordinate = stepPolyline.points()[stepPolyline.pointCount - 1].coordinate
        let stepEndLocation = CLLocation(latitude: stepEndCoordinate.latitude, longitude: stepEndCoordinate.longitude)

        // Calculate distance to end of this step
        let distanceToStepEnd = location.distance(from: stepEndLocation)

        // Auto-advance when within 50 meters of the step endpoint
        let advanceThreshold: CLLocationDistance = 50.0
        if distanceToStepEnd < advanceThreshold {
            advanceToNextStep()
        }
    }

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
        stopNavigation()
    }

    private func makeNavigationCamera(for location: CLLocation) -> MapCamera {
        let heading = navigationHeading(for: location)
        let centerCoordinate = coordinate(
            from: location.coordinate,
            distanceMeters: 140,
            headingDegrees: heading
        )

        return MapCamera(
            centerCoordinate: centerCoordinate,
            distance: 700,
            heading: heading,
            pitch: 60
        )
    }

    private func navigationHeading(for location: CLLocation) -> CLLocationDirection {
        let course = location.course
        if course.isFinite, course >= 0 {
            return course
        }

        if let step = currentStep, step.polyline.pointCount > 1 {
            let points = step.polyline.points()
            let start = points[0].coordinate
            let end = points[min(1, step.polyline.pointCount - 1)].coordinate
            return bearing(from: start, to: end)
        }

        return 0
    }

    private func coordinate(
        from coordinate: CLLocationCoordinate2D,
        distanceMeters: CLLocationDistance,
        headingDegrees: CLLocationDirection
    ) -> CLLocationCoordinate2D {
        let earthRadius = 6_378_137.0
        let distanceRadians = distanceMeters / earthRadius
        let headingRadians = headingDegrees * .pi / 180
        let latitudeRadians = coordinate.latitude * .pi / 180
        let longitudeRadians = coordinate.longitude * .pi / 180

        let targetLatitude = asin(
            sin(latitudeRadians) * cos(distanceRadians) +
            cos(latitudeRadians) * sin(distanceRadians) * cos(headingRadians)
        )
        let targetLongitude = longitudeRadians + atan2(
            sin(headingRadians) * sin(distanceRadians) * cos(latitudeRadians),
            cos(distanceRadians) - sin(latitudeRadians) * sin(targetLatitude)
        )

        return CLLocationCoordinate2D(
            latitude: targetLatitude * 180 / .pi,
            longitude: targetLongitude * 180 / .pi
        )
    }

    private func bearing(from start: CLLocationCoordinate2D, to end: CLLocationCoordinate2D) -> CLLocationDirection {
        let startLatitude = start.latitude * .pi / 180
        let startLongitude = start.longitude * .pi / 180
        let endLatitude = end.latitude * .pi / 180
        let endLongitude = end.longitude * .pi / 180

        let deltaLongitude = endLongitude - startLongitude
        let y = sin(deltaLongitude) * cos(endLatitude)
        let x = cos(startLatitude) * sin(endLatitude) -
            sin(startLatitude) * cos(endLatitude) * cos(deltaLongitude)
        let radians = atan2(y, x)
        let degrees = radians * 180 / .pi

        return degrees >= 0 ? degrees : degrees + 360
    }
}

//
//  LiveMapView.swift
//  Umuve Pro
//
//  Full-screen MapKit view: driver annotation, job markers,
//  route polyline, overlays for job alerts and active jobs.
//

import SwiftUI
import MapKit

struct LiveMapView: View {
    @Bindable var appState: AppState
    @State private var mapVM = LiveMapViewModel()
    @State private var navigationCoordinator = NavigationCoordinator()
    // Once the driver arrives, hand off to the canonical ActiveJobView
    // (before/after photos + completion + rating). One job lifecycle, not two.
    @State private var showJobFlow = false

    private var driverCoordinate: CLLocationCoordinate2D {
        appState.locationManager.currentLocation?.coordinate
            ?? CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194)
    }

    private var truckIcon: String {
        guard let truckTypeStr = appState.contractorProfile?.truckType,
              let truckType = TruckType(rawValue: truckTypeStr) else {
            return "truck.pickup.side"
        }
        return truckType.icon
    }

    var body: some View {
        ZStack {
            // MARK: - Full-Screen Map
            Map(position: $mapVM.cameraPosition) {
                // Driver annotation
                Annotation("You", coordinate: driverCoordinate) {
                    DriverAnnotationView(
                        truckIcon: truckIcon,
                        heading: appState.locationManager.currentLocation?.course ?? 0
                    )
                }

                // Nearby job markers
                ForEach(mapVM.nearbyJobs) { job in
                    if let lat = job.lat, let lng = job.lng {
                        Marker(job.formattedPrice, coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lng))
                            .tint(Color.driverPrimary)
                    }
                }

                // Route polyline for accepted job
                if let route = mapVM.route {
                    MapPolyline(route)
                        .stroke(Color.driverPrimary, lineWidth: 5)
                }
            }
            .mapControls {
                MapUserLocationButton()
                MapCompass()
            }
            .mapStyle(.standard(pointsOfInterest: .excludingAll))
            .ignoresSafeArea(edges: .top)
            .simultaneousGesture(
                DragGesture(minimumDistance: 2)
                    .onChanged { _ in
                        mapVM.userInteractedWithMap()
                    }
            )
            .simultaneousGesture(
                MagnificationGesture()
                    .onChanged { _ in
                        mapVM.userInteractedWithMap()
                    }
            )

            // MARK: - Top Overlays
            VStack(spacing: 0) {
                // Connection status + Go Offline
                HStack {
                    // Connection indicator
                    HStack(spacing: DriverSpacing.xxs) {
                        Circle()
                            .fill(appState.socket.isConnected ? Color.driverSuccess : Color.driverWarning)
                            .frame(width: 8, height: 8)

                        Text(appState.socket.isConnected ? "Connected" : "Connecting...")
                            .font(DriverTypography.caption)
                            .foregroundStyle(Color.driverText)
                    }
                    .padding(.horizontal, DriverSpacing.sm)
                    .padding(.vertical, DriverSpacing.xxs)
                    .background(.ultraThinMaterial)
                    .clipShape(Capsule())

                    Spacer()

                    // Go Offline button
                    Button {
                        Task { await appState.toggleOnline() }
                    } label: {
                        HStack(spacing: DriverSpacing.xxs) {
                            Circle()
                                .fill(Color.driverPrimary)
                                .frame(width: 8, height: 8)
                            Text("Online")
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverText)
                        }
                        .padding(.horizontal, DriverSpacing.sm)
                        .padding(.vertical, DriverSpacing.xxs)
                        .background(.ultraThinMaterial)
                        .clipShape(Capsule())
                    }
                }
                .padding(.horizontal, DriverSpacing.md)
                .padding(.top, DriverSpacing.xs)

                Spacer()

                // MARK: - Bottom Overlays

                // Job alert (incoming)
                if let alertJob = mapVM.incomingJobAlert {
                    JobAlertOverlay(
                        job: alertJob,
                        countdown: mapVM.alertCountdown,
                        onAccept: { mapVM.acceptJob() },
                        onDecline: { mapVM.declineJob() }
                    )
                    .padding(.bottom, DriverSpacing.xs)
                }

                // Navigation overlay (when navigation is active)
                if mapVM.isNavigating {
                    NavigationOverlay(
                        step: mapVM.currentStep,
                        eta: mapVM.routeETA,
                        onNext: { mapVM.advanceToNextStep() },
                        onStop: { mapVM.stopNavigation() }
                    )
                    .padding(.top, DriverSpacing.md)
                }

                // Active job overlay (when not navigating)
                if let acceptedJob = mapVM.acceptedJob, mapVM.incomingJobAlert == nil && !mapVM.isNavigating {
                    ActiveJobMapOverlay(
                        job: acceptedJob,
                        eta: mapVM.routeETA,
                        isUpdating: mapVM.isUpdatingStatus,
                        isNavigating: mapVM.isNavigating,
                        onStartNavigation: {
                            Task { await startNavigation(for: acceptedJob) }
                        },
                        onStatusUpdate: {
                            await handleStatusUpdate(for: acceptedJob)
                        }
                    )
                    .padding(.bottom, DriverSpacing.xs)
                }

                // Quick stats strip (when no alerts or active job)
                if mapVM.incomingJobAlert == nil && mapVM.acceptedJob == nil {
                    HStack(spacing: DriverSpacing.lg) {
                        HStack(spacing: DriverSpacing.xxs) {
                            Image(systemName: "dollarsign.circle.fill")
                                .foregroundStyle(Color.driverPrimary)
                            Text(String(format: "$%.0f", mapVM.todayEarnings))
                                .font(DriverTypography.headline)
                                .foregroundStyle(Color.driverText)
                            Text("today")
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverTextSecondary)
                        }

                        Divider().frame(height: 20)

                        HStack(spacing: DriverSpacing.xxs) {
                            Image(systemName: "briefcase.fill")
                                .foregroundStyle(Color.driverInfo)
                            Text("\(mapVM.todayJobsCount)")
                                .font(DriverTypography.headline)
                                .foregroundStyle(Color.driverText)
                            Text("jobs")
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverTextSecondary)
                        }

                        Spacer()

                        // Job count nearby
                        HStack(spacing: DriverSpacing.xxs) {
                            Image(systemName: "mappin.and.ellipse")
                                .foregroundStyle(Color.driverPrimary)
                            Text("\(mapVM.nearbyJobs.count) nearby")
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverTextSecondary)
                        }
                    }
                    .padding(.horizontal, DriverSpacing.md)
                    .padding(.vertical, DriverSpacing.sm)
                    .background(.ultraThinMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
                    .padding(.horizontal, DriverSpacing.md)
                    .padding(.bottom, DriverSpacing.sm)
                }
            }
        }
        .animation(.spring(response: 0.4), value: mapVM.incomingJobAlert?.id)
        .animation(.spring(response: 0.4), value: mapVM.acceptedJob?.id)
        .fullScreenCover(
            isPresented: Binding(
                get: { navigationCoordinator.shouldPresentNavigation },
                set: { isPresented in
                    if !isPresented {
                        navigationCoordinator.stopNavigation()
                        mapVM.stopNavigation()
                    }
                }
            )
        ) {
            DriverNavigationContainerView(coordinator: navigationCoordinator)
                .ignoresSafeArea()
        }
        // Canonical active-job flow (arrived → photos → started → photos → complete → rating).
        // Presented on arrival; the map keeps the route/navigation phase below it.
        .fullScreenCover(isPresented: $showJobFlow) {
            if let job = mapVM.acceptedJob ?? appState.activeJob {
                NavigationStack {
                    ActiveJobView(appState: appState, jobId: job.id)
                }
            }
        }
        .onAppear {
            mapVM.startPolling()
            mapVM.loadTodayStats()

            // CRITICAL: Sync existing active job when going online
            // If driver already has an active job, show it on map immediately
            if let existingJob = appState.activeJob {
                mapVM.acceptedJob = existingJob
                // Already arrived/working? Resume the canonical flow, not the map overlay.
                if existingJob.jobStatus == .arrived || existingJob.jobStatus == .started {
                    showJobFlow = true
                }
                // Calculate route to job location
                if let lat = existingJob.lat, let lng = existingJob.lng {
                    Task {
                        await mapVM.calculateRoute(to: CLLocationCoordinate2D(latitude: lat, longitude: lng))
                        // Auto-start navigation if already en route
                        if existingJob.status == "en_route" && !mapVM.isNavigating {
                            await startNavigation(for: existingJob)
                        }
                    }
                }
            }
        }
        .onDisappear {
            mapVM.stopPolling()
        }
        .onChange(of: appState.socket.newJobAlert?.id) { _, newId in
            guard newId != nil, let job = appState.consumeJobAlert() else { return }
            mapVM.showJobAlert(job)
        }
        .onChange(of: appState.socket.assignedJobId) { _, newId in
            guard let jobId = appState.consumeAssignment() else { return }
            mapVM.handleAssignment(jobId: jobId)
        }
        .onChange(of: appState.activeJob?.id) { _, newJobId in
            // When active job changes (accepted from Jobs tab), calculate route
            guard let job = appState.activeJob else {
                // Job cleared (e.g. completion "Back to Dashboard") - tear down everything
                mapVM.clearAcceptedJob()
                showJobFlow = false
                return
            }
            // Sync with map view model
            mapVM.acceptedJob = job
            // Calculate route to job location
            if let lat = job.lat, let lng = job.lng {
                Task {
                    await mapVM.calculateRoute(to: CLLocationCoordinate2D(latitude: lat, longitude: lng))
                    // Check if should auto-start navigation
                    if job.status == "en_route" && !mapVM.isNavigating {
                        await startNavigation(for: job)
                    }
                }
            }
        }
        .onChange(of: appState.activeJob?.status) { oldStatus, newStatus in
            // Auto-start navigation when status changes to en_route
            if newStatus == "en_route", !mapVM.isNavigating, mapVM.route != nil,
               let activeJob = appState.activeJob {
                Task { await startNavigation(for: activeJob) }
            }
            // Hand off to the canonical flow once arrived/working.
            if newStatus == "arrived" || newStatus == "started" {
                showJobFlow = true
            }
        }
        .onChange(of: mapVM.isNavigating) { _, isNavigating in
            guard isNavigating,
                  let location = appState.locationManager.currentLocation else { return }
            mapVM.updateNavigationCamera(using: location)
        }
        .onChange(of: appState.locationManager.currentLocation) { _, newLocation in
            guard let location = newLocation else { return }

            if mapVM.isNavigating {
                mapVM.updateNavigationLocation(location)
            }
        }
    }

    private func handleStatusUpdate(for job: DriverJob) async {
        switch job.jobStatus {
        case .accepted:
            await mapVM.markEnRoute()
        case .enRoute:
            // Mark arrived, then hand off to the canonical ActiveJobView for the
            // photo-gated start/complete + rating flow. No photoless map path.
            await mapVM.markArrived()
            appState.activeJob = mapVM.acceptedJob
            showJobFlow = true
        case .arrived, .started:
            // Already past navigation — drive everything through ActiveJobView.
            appState.activeJob = mapVM.acceptedJob
            showJobFlow = true
        default:
            break
        }
    }

    @MainActor
    private func startNavigation(for job: DriverJob) async {
        mapVM.startNavigation()

        guard navigationCoordinator.isMapboxRuntimeAvailable else {
            return
        }

        do {
            try navigationCoordinator.prepareNavigation(
                for: job,
                currentLocation: appState.locationManager.currentLocation?.coordinate
            )
        } catch {
            mapVM.errorMessage = error.localizedDescription
            navigationCoordinator.lastErrorMessage = error.localizedDescription
        }
    }
}

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

            // MARK: - Top Overlays
            VStack(spacing: 0) {
                // Connection status + Go Offline
                HStack {
                    // Connection indicator
                    HStack(spacing: DriverSpacing.xxs) {
                        Circle()
                            .fill(appState.socket.isConnected ? Color.driverSuccess : Color.driverWarning)
                            .frame(width: 8, height: 8)

                        Text(appState.socket.isConnected ? "Connected" : "Reconnecting...")
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

                // Active job overlay
                if let acceptedJob = mapVM.acceptedJob, mapVM.incomingJobAlert == nil {
                    ActiveJobMapOverlay(
                        job: acceptedJob,
                        eta: mapVM.routeETA,
                        isUpdating: mapVM.isUpdatingStatus,
                        onNavigate: { mapVM.openInAppleMaps() },
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
        .onAppear {
            mapVM.startPolling()
            mapVM.todayJobsCount = appState.contractorProfile?.totalJobs ?? 0
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
    }

    private func handleStatusUpdate(for job: DriverJob) async {
        switch job.jobStatus {
        case .accepted:
            await mapVM.markEnRoute()
        case .enRoute:
            await mapVM.markArrived()
        case .arrived:
            await mapVM.markStarted()
        case .started:
            await mapVM.markCompleted()
        default:
            break
        }
    }
}

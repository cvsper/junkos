//
//  JobTrackingView.swift
//  Umuve
//
//  Real-time driver tracking map view with Socket.IO integration.
//  Displays driver location as a car annotation on MapKit.
//

import SwiftUI
import MapKit

// MARK: - Driver Annotation

struct DriverAnnotation: Identifiable {
    let id = UUID()
    var coordinate: CLLocationCoordinate2D
}

// MARK: - Job Tracking View

struct JobTrackingView: View {
    let jobId: String
    let jobAddress: String
    let driverName: String?

    @State private var region = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194),
        span: MKCoordinateSpan(latitudeDelta: 0.02, longitudeDelta: 0.02)
    )
    @State private var driverAnnotation: DriverAnnotation?
    @State private var hasReceivedFirstLocation = false
    @State private var jobStatus: String = "en_route"

    var annotations: [DriverAnnotation] {
        if let annotation = driverAnnotation {
            return [annotation]
        }
        return []
    }

    var body: some View {
        VStack(spacing: 0) {
            // Status banner
            statusBanner
                .padding(.horizontal, UmuveSpacing.normal)
                .padding(.top, UmuveSpacing.normal)

            // Map view
            ZStack {
                Map(coordinateRegion: $region, annotationItems: annotations) { annotation in
                    MapAnnotation(coordinate: annotation.coordinate) {
                        ZStack {
                            Circle()
                                .fill(Color.umuvePrimary.opacity(0.2))
                                .frame(width: 44, height: 44)

                            Circle()
                                .fill(Color.umuvePrimary)
                                .frame(width: 36, height: 36)

                            Image(systemName: "car.fill")
                                .font(.system(size: 16))
                                .foregroundColor(.white)
                        }
                    }
                }
                .edgesIgnoringSafeArea(.horizontal)

                // Loading overlay
                if !hasReceivedFirstLocation {
                    VStack(spacing: UmuveSpacing.medium) {
                        ProgressView()
                            .tint(.umuvePrimary)
                            .scaleEffect(1.2)
                        Text("Waiting for driver location...")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveTextMuted)
                    }
                    .padding(UmuveSpacing.xlarge)
                    .background(
                        RoundedRectangle(cornerRadius: UmuveRadius.lg)
                            .fill(Color.white)
                            .shadow(color: .black.opacity(0.1), radius: 10, x: 0, y: 4)
                    )
                }

                // Re-center button
                if hasReceivedFirstLocation {
                    VStack {
                        Spacer()
                        HStack {
                            Spacer()
                            Button(action: recenterOnDriver) {
                                Image(systemName: "location.fill")
                                    .font(.system(size: 18))
                                    .foregroundColor(.white)
                                    .padding(UmuveSpacing.medium)
                                    .background(Circle().fill(Color.umuvePrimary))
                                    .shadow(color: .black.opacity(0.2), radius: 4, x: 0, y: 2)
                            }
                            .padding(.trailing, UmuveSpacing.normal)
                            .padding(.bottom, 100)
                        }
                    }
                }
            }

            // Bottom card
            bottomCard
                .padding(UmuveSpacing.normal)
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .navigationTitle("Track Driver")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            connectAndJoinRoom()
        }
        .onDisappear {
            leaveRoom()
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("driverLocationUpdated"))) { _ in
            updateDriverLocation()
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("jobStatusUpdated"))) { notification in
            updateJobStatus(from: notification)
        }
    }

    // MARK: - Status Banner

    private var statusBanner: some View {
        HStack(spacing: UmuveSpacing.small) {
            Circle()
                .fill(statusColor)
                .frame(width: 8, height: 8)

            Text(statusText)
                .font(UmuveTypography.bodyFont.weight(.medium))
                .foregroundColor(.umuveText)

            Spacer()
        }
        .padding(.horizontal, UmuveSpacing.normal)
        .padding(.vertical, UmuveSpacing.medium)
        .background(
            Capsule()
                .fill(statusColor.opacity(0.1))
        )
    }

    private var statusColor: Color {
        switch jobStatus {
        case "en_route":
            return .umuveInfo
        case "arrived":
            return .umuveWarning
        case "in_progress":
            return .umuvePrimary
        case "completed":
            return .umuveSuccess
        default:
            return .umuveTextMuted
        }
    }

    private var statusText: String {
        switch jobStatus {
        case "en_route":
            return "Driver en route"
        case "arrived":
            return "Driver arrived"
        case "in_progress":
            return "Job in progress"
        case "completed":
            return "Job completed"
        default:
            return "Tracking driver"
        }
    }

    // MARK: - Bottom Card

    private var bottomCard: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.medium) {
            if let driverName = driverName {
                HStack(spacing: UmuveSpacing.small) {
                    Image(systemName: "person.circle.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.umuvePrimary)
                    Text(driverName)
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)
                }
            }

            Divider()

            HStack(spacing: UmuveSpacing.small) {
                Image(systemName: "mappin.circle.fill")
                    .font(.system(size: 16))
                    .foregroundColor(.umuveTextMuted)
                Text(jobAddress)
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveText)
                    .lineLimit(2)
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }

    // MARK: - Socket.IO Lifecycle

    private func connectAndJoinRoom() {
        // Connect Socket.IO if not already connected
        if !CustomerSocketManager.shared.isConnected {
            if let token = KeychainHelper.loadString(forKey: "authToken") {
                CustomerSocketManager.shared.connect(token: token)
            }
        }

        // Join the job room
        CustomerSocketManager.shared.joinJobRoom(jobId: jobId)
    }

    private func leaveRoom() {
        CustomerSocketManager.shared.leaveJobRoom(jobId: jobId)
    }

    // MARK: - Location Updates

    private func updateDriverLocation() {
        guard let lat = CustomerSocketManager.shared.driverLatitude,
              let lng = CustomerSocketManager.shared.driverLongitude else {
            return
        }

        let coordinate = CLLocationCoordinate2D(latitude: lat, longitude: lng)

        // Update annotation
        driverAnnotation = DriverAnnotation(coordinate: coordinate)

        // Center map on first location
        if !hasReceivedFirstLocation {
            region.center = coordinate
            hasReceivedFirstLocation = true
        }
    }

    private func recenterOnDriver() {
        if let annotation = driverAnnotation {
            withAnimation {
                region.center = annotation.coordinate
            }
        }
    }

    // MARK: - Status Updates

    private func updateJobStatus(from notification: Notification) {
        guard let userInfo = notification.userInfo,
              let status = userInfo["status"] as? String else {
            return
        }
        jobStatus = status
    }
}

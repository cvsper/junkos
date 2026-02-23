//
//  NavigateToJobView.swift
//  Umuve Pro
//
//  Shows address and opens Maps. Buttons: Navigate, Mark En Route, Mark Arrived.
//

import SwiftUI
import MapKit

struct NavigateToJobView: View {
    let job: DriverJob
    @Bindable var viewModel: ActiveJobViewModel

    var body: some View {
        VStack(spacing: DriverSpacing.lg) {
            Spacer()

            // Map preview with NavigationLink
            if let lat = job.lat, let lng = job.lng {
                NavigationLink(destination: LiveMapView(jobId: job.id)) {
                    VStack(spacing: DriverSpacing.md) {
                        Map(initialPosition: .region(MKCoordinateRegion(
                            center: CLLocationCoordinate2D(latitude: lat, longitude: lng),
                            span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
                        ))) {
                            Marker(job.shortAddress, coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lng))
                                .tint(Color.driverPrimary)
                        }
                        .frame(height: 200)
                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
                        .allowsHitTesting(false) // Disable map interaction, make whole area tappable

                        // Address info
                        VStack(spacing: DriverSpacing.xs) {
                            HStack {
                                Text(job.shortAddress)
                                    .font(DriverTypography.title3)
                                    .foregroundStyle(Color.driverText)

                                Image(systemName: "chevron.right")
                                    .font(.caption)
                                    .foregroundStyle(Color.driverTextSecondary)
                            }

                            Text(job.address)
                                .font(DriverTypography.footnote)
                                .foregroundStyle(Color.driverTextSecondary)
                                .multilineTextAlignment(.center)

                            if job.jobStatus == .enRoute {
                                Text("Tap to view full map")
                                    .font(.caption2)
                                    .foregroundStyle(Color.driverPrimary)
                            }
                        }
                    }
                }
                .buttonStyle(.plain)
                .padding(.horizontal, DriverSpacing.xl)
            }

            Spacer()

            // Buttons
            VStack(spacing: DriverSpacing.sm) {
                // Open in Maps
                Button {
                    openInMaps()
                } label: {
                    Label("Navigate in Maps", systemImage: "map.fill")
                }
                .buttonStyle(DriverSecondaryButtonStyle())

                // Status button
                Button {
                    Task {
                        if job.jobStatus == .accepted {
                            await viewModel.markEnRoute()
                        } else if job.jobStatus == .enRoute {
                            await viewModel.markArrived()
                        }
                    }
                } label: {
                    if viewModel.isUpdating {
                        ProgressView().tint(.white)
                    } else {
                        Text(job.jobStatus == .accepted ? "Mark En Route" : "Mark Arrived")
                    }
                }
                .buttonStyle(DriverPrimaryButtonStyle())
                .disabled(viewModel.isUpdating)
            }
            .padding(.horizontal, DriverSpacing.xl)
            .padding(.bottom, DriverSpacing.xxl)
        }
    }

    private func openInMaps() {
        guard let lat = job.lat, let lng = job.lng else { return }
        let coordinate = CLLocationCoordinate2D(latitude: lat, longitude: lng)
        let placemark = MKPlacemark(coordinate: coordinate)
        let mapItem = MKMapItem(placemark: placemark)
        mapItem.name = job.shortAddress
        mapItem.openInMaps(launchOptions: [MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeDriving])
    }
}

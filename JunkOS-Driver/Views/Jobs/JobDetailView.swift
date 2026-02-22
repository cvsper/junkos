//
//  JobDetailView.swift
//  Umuve Pro
//
//  Full job info with Accept button and map preview.
//

import SwiftUI
import MapKit

struct JobDetailView: View {
    @Bindable var appState: AppState
    let jobId: String
    var jobs: [DriverJob] = []
    @State private var viewModel = JobDetailViewModel()
    @Environment(\.dismiss) private var dismiss

    private var job: DriverJob? {
        viewModel.job ?? jobs.first(where: { $0.id == jobId })
    }

    var body: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            if let job {
                ScrollView {
                    VStack(spacing: DriverSpacing.lg) {
                        // Map preview
                        if let lat = job.lat, let lng = job.lng {
                            Map(initialPosition: .region(MKCoordinateRegion(
                                center: CLLocationCoordinate2D(latitude: lat, longitude: lng),
                                span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
                            ))) {
                                Marker(job.shortAddress, coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lng))
                                    .tint(Color.driverPrimary)
                            }
                            .frame(height: 200)
                            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
                            .padding(.horizontal, DriverSpacing.xl)
                        }

                        // Address card
                        VStack(alignment: .leading, spacing: DriverSpacing.sm) {
                            Label("Pickup Address", systemImage: "mappin.circle.fill")
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverTextSecondary)

                            Text(job.address)
                                .font(DriverTypography.headline)
                                .foregroundStyle(Color.driverText)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .driverCard()
                        .padding(.horizontal, DriverSpacing.xl)

                        // Details card
                        VStack(spacing: DriverSpacing.md) {
                            DetailRow(label: "Estimated Pay", value: job.formattedPrice, icon: "dollarsign.circle")
                            DetailRow(label: "Distance", value: job.formattedDistance, icon: "location")

                            if let items = job.items, !items.isEmpty {
                                DetailRow(label: "Items", value: job.itemNames.joined(separator: ", "), icon: "cube.box")
                            }

                            if let notes = job.notes, !notes.isEmpty {
                                DetailRow(label: "Notes", value: notes, icon: "note.text")
                            }

                            if let date = job.scheduledDate {
                                DetailRow(label: "Scheduled", value: date.formatted(date: .abbreviated, time: .shortened), icon: "calendar")
                            }
                        }
                        .driverCard()
                        .padding(.horizontal, DriverSpacing.xl)

                        // Error
                        if let error = viewModel.errorMessage {
                            Text(error)
                                .font(DriverTypography.footnote)
                                .foregroundStyle(Color.driverError)
                                .padding(.horizontal, DriverSpacing.xl)
                        }

                        // Accept button (show for all jobs except already accepted/completed ones)
                        if ![.accepted, .enRoute, .arrived, .started, .completed, .cancelled].contains(job.jobStatus) {
                            Button {
                                Task {
                                    await viewModel.acceptJob(jobId: job.id)
                                    if viewModel.didAccept, let acceptedJob = viewModel.job {
                                        appState.activeJob = acceptedJob
                                        // Post notification to switch to Home tab and show route
                                        NotificationCenter.default.post(
                                            name: .jobWasAccepted,
                                            object: nil,
                                            userInfo: ["job_id": acceptedJob.id]
                                        )
                                        dismiss()
                                    }
                                }
                            } label: {
                                if viewModel.isAccepting {
                                    ProgressView().tint(.white)
                                } else {
                                    Text("Accept Job")
                                }
                            }
                            .buttonStyle(DriverPrimaryButtonStyle())
                            .disabled(viewModel.isAccepting)
                            .padding(.horizontal, DriverSpacing.xl)
                        }
                    }
                    .padding(.top, DriverSpacing.md)
                    .padding(.bottom, DriverSpacing.xxxl)
                }
            } else {
                ProgressView().tint(Color.driverPrimary)
            }
        }
        .navigationTitle("Job Details")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if let job = job {
                print("🔍 JobDetailView: Job status = \(job.status), jobStatus enum = \(job.jobStatus), driverId = \(job.driverId ?? "nil")")
            }
        }
    }
}

// MARK: - Detail Row

private struct DetailRow: View {
    let label: String
    let value: String
    let icon: String

    var body: some View {
        HStack(alignment: .top) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundStyle(Color.driverPrimary)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: DriverSpacing.xxxs) {
                Text(label)
                    .font(DriverTypography.caption)
                    .foregroundStyle(Color.driverTextSecondary)

                Text(value)
                    .font(DriverTypography.body)
                    .foregroundStyle(Color.driverText)
            }

            Spacer()
        }
    }
}

//
//  ActiveJobView.swift
//  Umuve Pro
//
//  Container that switches content based on job status.
//

import SwiftUI

struct ActiveJobView: View {
    @Bindable var appState: AppState
    let jobId: String
    @State private var viewModel = ActiveJobViewModel()

    var body: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            if let job = viewModel.job {
                VStack(spacing: 0) {
                    // Stepper
                    JobStatusStepperView(currentStatus: job.jobStatus)
                        .padding(.horizontal, DriverSpacing.xl)
                        .padding(.top, DriverSpacing.md)

                    // Error
                    if let error = viewModel.errorMessage {
                        Text(error)
                            .font(DriverTypography.footnote)
                            .foregroundStyle(Color.driverError)
                            .padding(.horizontal, DriverSpacing.xl)
                            .padding(.top, DriverSpacing.xs)
                    }

                    // Content based on status
                    Group {
                        switch job.jobStatus {
                        case .accepted:
                            NavigateToJobView(job: job, viewModel: viewModel, appState: appState)
                        case .enRoute:
                            NavigateToJobView(job: job, viewModel: viewModel, appState: appState)
                        case .arrived:
                            VStack(spacing: DriverSpacing.md) {
                                BeforePhotosView(viewModel: viewModel)

                                NavigationLink(destination: VolumeAdjustmentView(
                                    jobId: job.id,
                                    originalEstimate: job.volumeEstimate
                                )) {
                                    Label("Adjust Volume", systemImage: "arrow.up.arrow.down.circle")
                                        .font(DriverTypography.body)
                                        .foregroundStyle(Color.driverPrimary)
                                        .frame(maxWidth: .infinity)
                                        .padding(DriverSpacing.md)
                                        .background(Color.driverPrimary.opacity(0.1))
                                        .clipShape(RoundedRectangle(cornerRadius: 12))
                                }
                                .padding(.horizontal, DriverSpacing.xl)
                            }
                        case .started:
                            AfterPhotosView(viewModel: viewModel)
                        case .completed:
                            JobCompletionView(job: job, appState: appState)
                        default:
                            EmptyView()
                        }
                    }
                    .transition(.asymmetric(
                        insertion: .move(edge: .trailing).combined(with: .opacity),
                        removal: .move(edge: .leading).combined(with: .opacity)
                    ))
                    .animation(AnimationConstants.smoothSpring, value: job.jobStatus)
                }
            } else {
                ProgressView().tint(Color.driverPrimary)
            }
        }
        .navigationTitle("Active Job")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            viewModel.job = appState.activeJob
        }
        .onChange(of: viewModel.job?.status) { _, newStatus in
            // Sync job status changes back to appState so LiveMapView can react
            if let job = viewModel.job {
                appState.activeJob = job
            }
        }
    }
}

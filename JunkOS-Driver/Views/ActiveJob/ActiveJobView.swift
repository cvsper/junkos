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
                            NavigateToJobView(job: job, viewModel: viewModel)
                        case .enRoute:
                            NavigateToJobView(job: job, viewModel: viewModel)
                        case .arrived:
                            BeforePhotosView(viewModel: viewModel)
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
    }
}

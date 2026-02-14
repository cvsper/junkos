//
//  JobFeedView.swift
//  Umuve Pro
//
//  Available jobs list with pull-to-refresh.
//

import SwiftUI

struct JobFeedView: View {
    @Bindable var appState: AppState
    @State private var viewModel = JobFeedViewModel()

    var body: some View {
        NavigationStack {
            ZStack {
                Color.driverBackground.ignoresSafeArea()

                if viewModel.jobs.isEmpty && !viewModel.isLoading {
                    EmptyStateView(
                        icon: "briefcase",
                        title: "No Jobs Nearby",
                        message: appState.isOnline
                            ? "No pending jobs in your area right now. Pull down to refresh."
                            : "Go online to see available jobs near you."
                    )
                } else {
                    ScrollView {
                        LazyVStack(spacing: DriverSpacing.sm) {
                            ForEach(viewModel.jobs) { job in
                                NavigationLink(value: AppRoute.jobDetail(jobId: job.id)) {
                                    JobCardView(job: job)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(.horizontal, DriverSpacing.xl)
                        .padding(.top, DriverSpacing.md)
                        .padding(.bottom, DriverSpacing.xxxl)
                    }
                    .refreshable {
                        await viewModel.refresh()
                    }
                }

                if viewModel.isLoading && viewModel.jobs.isEmpty {
                    ProgressView()
                        .tint(Color.driverPrimary)
                }
            }
            .navigationTitle("Available Jobs")
            .navigationBarTitleDisplayMode(.large)
            .task {
                await viewModel.loadJobs()
            }
            .navigationDestination(for: AppRoute.self) { route in
                switch route {
                case .jobDetail(let jobId):
                    JobDetailView(appState: appState, jobId: jobId, jobs: viewModel.jobs)
                default:
                    EmptyView()
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .jobWasAccepted)) { notification in
                if let jobId = notification.userInfo?["job_id"] as? String {
                    withAnimation(.easeOut(duration: 0.3)) {
                        viewModel.removeJob(id: jobId)
                    }
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .newJobAvailable)) { notification in
                if let job = notification.userInfo?["job"] as? DriverJob {
                    withAnimation(.spring(response: 0.4)) {
                        viewModel.addJobIfNew(job)
                    }
                }
            }
        }
    }
}

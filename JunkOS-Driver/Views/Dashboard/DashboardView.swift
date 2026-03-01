//
//  DashboardView.swift
//  Umuve Pro
//
//  Home screen: big online toggle, today stats, active job card.
//

import SwiftUI

struct DashboardView: View {
    @Bindable var appState: AppState
    @State private var dashVM = DashboardViewModel()

    var body: some View {
        NavigationStack {
            ZStack {
                if appState.isOnline {
                    // Full-screen map experience when online
                    LiveMapView(appState: appState)
                } else {
                    // Normal dashboard when offline
                    offlineDashboard
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .task {
                if appState.contractorProfile == nil {
                    await appState.loadContractorProfile()
                }
                dashVM.loadStats(from: appState.contractorProfile)
            }
            .navigationDestination(for: AppRoute.self) { route in
                switch route {
                case .activeJob(let jobId):
                    ActiveJobView(appState: appState, jobId: jobId)
                case .jobDetail(let jobId):
                    JobDetailView(appState: appState, jobId: jobId)
                default:
                    EmptyView()
                }
            }
        }
    }

    // MARK: - Offline Dashboard

    private var offlineDashboard: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            ScrollView {
                VStack(spacing: DriverSpacing.lg) {
                    // Greeting
                    HStack {
                        VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                            Text(greeting)
                                .font(DriverTypography.title2)
                                .foregroundStyle(Color.driverText)

                            Text(appState.auth.currentUser?.displayName ?? "Driver")
                                .font(DriverTypography.title)
                                .foregroundStyle(Color.driverPrimary)
                        }
                        Spacer()
                    }
                    .padding(.horizontal, DriverSpacing.xl)

                    // Online toggle
                    OnlineToggleView(
                        isOnline: appState.isOnline,
                        onToggle: {
                            Task { await appState.toggleOnline() }
                        }
                    )
                    .padding(.horizontal, DriverSpacing.xl)

                    // Quick stats
                    QuickStatsCard(
                        todayEarnings: dashVM.todayEarnings,
                        todayJobs: dashVM.todayJobs,
                        rating: dashVM.rating
                    )
                    .padding(.horizontal, DriverSpacing.xl)

                    // Active job card
                    if let activeJob = appState.activeJob {
                        NavigationLink(value: AppRoute.activeJob(jobId: activeJob.id)) {
                            ActiveJobCard(job: activeJob)
                        }
                        .buttonStyle(.plain)
                        .padding(.horizontal, DriverSpacing.xl)
                    }

                    // Approval status
                    if appState.contractorProfile?.approval == .pending {
                        PendingApprovalCard()
                            .padding(.horizontal, DriverSpacing.xl)
                    }
                }
                .padding(.top, DriverSpacing.md)
                .padding(.bottom, DriverSpacing.xxxl)
            }
        }
    }

    private var greeting: String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 5..<12: return "Good morning,"
        case 12..<17: return "Good afternoon,"
        default: return "Good evening,"
        }
    }
}

// MARK: - Active Job Card

private struct ActiveJobCard: View {
    let job: DriverJob

    var body: some View {
        VStack(alignment: .leading, spacing: DriverSpacing.sm) {
            HStack {
                Text("Active Job")
                    .font(DriverTypography.caption)
                    .foregroundStyle(.white)
                    .padding(.horizontal, DriverSpacing.xs)
                    .padding(.vertical, DriverSpacing.xxxs)
                    .background(Capsule().fill(Color.driverPrimary))

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(Color.driverTextSecondary)
            }

            Text(job.shortAddress)
                .font(DriverTypography.headline)
                .foregroundStyle(Color.driverText)

            HStack(spacing: DriverSpacing.md) {
                Label(job.formattedPrice, systemImage: "dollarsign.circle")
                Label(job.jobStatus.displayName, systemImage: job.jobStatus.icon)
            }
            .font(DriverTypography.footnote)
            .foregroundStyle(Color.driverTextSecondary)
        }
        .driverCard()
    }
}

// MARK: - Pending Approval Card

private struct PendingApprovalCard: View {
    var body: some View {
        VStack(spacing: DriverSpacing.sm) {
            Image(systemName: "clock.badge.checkmark")
                .font(.system(size: 32))
                .foregroundStyle(Color.statusPending)

            Text("Account Under Review")
                .font(DriverTypography.headline)
                .foregroundStyle(Color.driverText)

            Text("Your contractor application is being reviewed. You'll be able to accept jobs once approved.")
                .font(DriverTypography.footnote)
                .foregroundStyle(Color.driverTextSecondary)
                .multilineTextAlignment(.center)
        }
        .driverCard()
    }
}

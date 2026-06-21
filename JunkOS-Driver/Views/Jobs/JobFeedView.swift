//
//  JobFeedView.swift
//  Umuve Pro
//
//  Available jobs — earnings-first hero, then sorted job stream.
//

import SwiftUI

enum JobSortMode: String, CaseIterable, Identifiable {
    case nearest
    case highestPaying
    case soonest

    var id: String { rawValue }

    var title: String {
        switch self {
        case .nearest: return "Nearest"
        case .highestPaying: return "Top $"
        case .soonest: return "Soonest"
        }
    }

    var icon: String {
        switch self {
        case .nearest: return "location.fill"
        case .highestPaying: return "dollarsign.circle.fill"
        case .soonest: return "clock.fill"
        }
    }
}

struct JobFeedView: View {
    @Bindable var appState: AppState
    @State private var viewModel = JobFeedViewModel()
    @State private var sortMode: JobSortMode = .nearest

    var body: some View {
        NavigationStack {
            ZStack {
                Color.driverBackground.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: DriverSpacing.md) {
                        statusHero
                            .padding(.horizontal, DriverSpacing.lg)
                            .padding(.top, DriverSpacing.sm)

                        if !viewModel.offers.isEmpty {
                            offersSection
                                .padding(.horizontal, DriverSpacing.lg)
                        }

                        if !sortedJobs.isEmpty {
                            sortBar
                                .padding(.horizontal, DriverSpacing.lg)
                        }

                        if sortedJobs.isEmpty && !viewModel.isLoading {
                            emptyState
                                .padding(.top, DriverSpacing.xxl)
                        } else {
                            LazyVStack(spacing: DriverSpacing.md) {
                                ForEach(Array(sortedJobs.enumerated()), id: \.element.id) { index, job in
                                    NavigationLink(value: AppRoute.jobDetail(jobId: job.id)) {
                                        JobCardView(job: job)
                                            .overlay(alignment: .topLeading) {
                                                if index == 0 {
                                                    featuredBadge
                                                        .padding(DriverSpacing.sm)
                                                }
                                            }
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            .padding(.horizontal, DriverSpacing.lg)
                            .padding(.bottom, DriverSpacing.xxxl)
                        }
                    }
                }
                .refreshable {
                    await viewModel.refresh()
                }

                if viewModel.isLoading && viewModel.jobs.isEmpty {
                    ProgressView()
                        .tint(Color.driverPrimary)
                }
            }
            .navigationTitle("Jobs")
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

    // MARK: - Sorting

    private var sortedJobs: [DriverJob] {
        switch sortMode {
        case .nearest:
            return viewModel.jobs.sorted { (a, b) in
                (a.distanceKm ?? .infinity) < (b.distanceKm ?? .infinity)
            }
        case .highestPaying:
            return viewModel.jobs.sorted { $0.totalPrice > $1.totalPrice }
        case .soonest:
            return viewModel.jobs.sorted { (a, b) in
                let now = Date.distantFuture
                return (a.scheduledDate ?? now) < (b.scheduledDate ?? now)
            }
        }
    }

    // MARK: - Status Hero

    private var statusHero: some View {
        HStack(spacing: DriverSpacing.md) {
            // Online indicator
            ZStack {
                Circle()
                    .fill(appState.isOnline ? Color.driverSuccess.opacity(0.18) : Color.driverTextTertiary.opacity(0.18))
                    .frame(width: 44, height: 44)
                Circle()
                    .fill(appState.isOnline ? Color.driverSuccess : Color.driverTextTertiary)
                    .frame(width: 14, height: 14)
                    .shadow(color: (appState.isOnline ? Color.driverSuccess : .clear).opacity(0.6), radius: 6, x: 0, y: 0)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(appState.isOnline ? "You're Online" : "You're Offline")
                    .font(DriverTypography.headline)
                    .foregroundStyle(Color.driverText)
                Text(subtitleText)
                    .font(DriverTypography.footnote)
                    .foregroundStyle(Color.driverTextSecondary)
            }

            Spacer()

            // Count pill
            if !viewModel.jobs.isEmpty {
                VStack(spacing: 0) {
                    Text("\(viewModel.jobs.count)")
                        .font(.system(size: 22, weight: .bold, design: .rounded))
                        .foregroundStyle(Color.driverPrimary)
                    Text("nearby")
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundStyle(Color.driverTextSecondary)
                        .textCase(.uppercase)
                        .tracking(0.6)
                }
                .padding(.horizontal, DriverSpacing.sm)
                .padding(.vertical, DriverSpacing.xs)
                .background(Color.driverPrimary.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
            }
        }
        .padding(DriverSpacing.md)
        .background(Color.driverSurface)
        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
        .shadow(color: .black.opacity(0.05), radius: 6, x: 0, y: 2)
    }

    private var subtitleText: String {
        if !appState.isOnline {
            return "Go online to start receiving job offers"
        }
        if viewModel.jobs.isEmpty {
            return "Watching for new jobs in your area…"
        }
        let total = viewModel.jobs.reduce(0.0) { $0 + $1.totalPrice * 0.80 }
        return String(format: "Potential earnings nearby: $%.0f", total)
    }

    // MARK: - Sort Bar

    private var sortBar: some View {
        HStack(spacing: DriverSpacing.xs) {
            ForEach(JobSortMode.allCases) { mode in
                Button {
                    withAnimation(.spring(response: 0.3)) {
                        sortMode = mode
                    }
                    HapticManager.shared.selection()
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: mode.icon)
                            .font(.system(size: 11, weight: .semibold))
                        Text(mode.title)
                            .font(.system(size: 13, weight: .semibold))
                    }
                    .foregroundStyle(sortMode == mode ? .white : Color.driverText)
                    .padding(.horizontal, DriverSpacing.sm)
                    .padding(.vertical, 8)
                    .background(sortMode == mode ? Color.driverPrimary : Color.driverSurface)
                    .clipShape(Capsule())
                }
                .buttonStyle(.plain)
            }
            Spacer()
        }
    }

    // MARK: - Broadcast offers

    private var offersSection: some View {
        VStack(alignment: .leading, spacing: DriverSpacing.sm) {
            HStack(spacing: 6) {
                Image(systemName: "bolt.badge.clock.fill")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(Color.driverPrimary)
                Text("Job offers")
                    .font(DriverTypography.headline)
                    .foregroundStyle(Color.driverText)
                Spacer()
                Text("first to accept")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(Color.driverTextSecondary)
                    .textCase(.uppercase)
                    .tracking(0.4)
            }
            ForEach(viewModel.offers) { offer in
                offerCard(offer)
            }
        }
    }

    private func offerCard(_ offer: DriverOffer) -> some View {
        VStack(alignment: .leading, spacing: DriverSpacing.sm) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(offer.address ?? "Nearby pickup")
                        .font(DriverTypography.headline)
                        .foregroundStyle(Color.driverText)
                        .lineLimit(1)
                    if let d = offer.distanceMiles {
                        Label(String(format: "%.1f mi away", d), systemImage: "location.fill")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(Color.driverTextSecondary)
                    }
                }
                Spacer()
                if let p = offer.payoutAmount {
                    Text(String(format: "$%.0f", p))
                        .font(.system(size: 22, weight: .bold, design: .rounded))
                        .foregroundStyle(Color.driverPrimary)
                }
            }
            Button {
                HapticManager.shared.selection()
                Task {
                    let ok = await viewModel.acceptOffer(offer)
                    if ok {
                        NotificationCenter.default.post(
                            name: .jobWasAccepted, object: nil,
                            userInfo: ["job_id": offer.jobId]
                        )
                    }
                }
            } label: {
                Text("Accept job")
                    .font(DriverTypography.headline)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, DriverSpacing.sm)
                    .background(Color.driverPrimary)
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
            }
            .buttonStyle(.plain)
        }
        .padding(DriverSpacing.md)
        .background(Color.driverSurface)
        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: DriverRadius.lg)
                .stroke(Color.driverPrimary.opacity(0.3), lineWidth: 1)
        )
    }

    // MARK: - Featured badge

    private var featuredBadge: some View {
        HStack(spacing: 4) {
            Image(systemName: "star.fill")
                .font(.system(size: 10, weight: .bold))
            Text(featuredLabel)
                .font(.system(size: 11, weight: .bold, design: .rounded))
                .tracking(0.4)
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(
            LinearGradient(
                colors: [Color.driverPrimary, Color.driverPrimaryDark],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .clipShape(Capsule())
        .shadow(color: Color.driverPrimary.opacity(0.4), radius: 6, x: 0, y: 2)
    }

    private var featuredLabel: String {
        switch sortMode {
        case .nearest: return "CLOSEST"
        case .highestPaying: return "TOP EARNER"
        case .soonest: return "NEXT UP"
        }
    }

    // MARK: - Empty state

    private var emptyState: some View {
        VStack(spacing: DriverSpacing.md) {
            ZStack {
                Circle()
                    .fill(Color.driverPrimary.opacity(0.08))
                    .frame(width: 88, height: 88)
                Image(systemName: appState.isOnline ? "antenna.radiowaves.left.and.right" : "moon.fill")
                    .font(.system(size: 36))
                    .foregroundStyle(Color.driverPrimary)
            }

            VStack(spacing: DriverSpacing.xs) {
                Text(appState.isOnline ? "Listening for jobs…" : "You're offline")
                    .font(DriverTypography.title3)
                    .foregroundStyle(Color.driverText)

                Text(appState.isOnline
                     ? "When customers nearby book hauls, they'll pop up here. Pull to refresh."
                     : "Flip on at the bottom to start seeing jobs near you.")
                    .font(DriverTypography.body)
                    .foregroundStyle(Color.driverTextSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, DriverSpacing.xl)
            }

            if !appState.isOnline {
                Button {
                    Task { await appState.toggleOnline() }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "bolt.fill")
                        Text("Go Online")
                    }
                    .font(DriverTypography.headline)
                    .foregroundStyle(.white)
                    .padding(.horizontal, DriverSpacing.xl)
                    .padding(.vertical, DriverSpacing.sm)
                    .background(Color.driverPrimary)
                    .clipShape(Capsule())
                }
                .padding(.top, DriverSpacing.xs)
            }
        }
        .padding(.horizontal, DriverSpacing.xl)
    }
}

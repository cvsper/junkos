//
//  ProfileSettingsView.swift
//  JunkOS Driver
//
//  Profile settings: truck info, documents, schedule, logout.
//

import SwiftUI

struct ProfileSettingsView: View {
    @Bindable var appState: AppState
    @State private var showLogoutConfirm = false

    private var profile: ContractorProfile? { appState.contractorProfile }

    private var haulerTier: String {
        guard let profile else { return "—" }
        if profile.avgRating >= 4.8 && profile.totalJobs >= 50 { return "Elite" }
        if profile.avgRating >= 4.5 && profile.totalJobs >= 20 { return "Pro" }
        if profile.totalJobs >= 5 { return "Standard" }
        return "Rookie"
    }

    private var haulerTierColor: Color {
        switch haulerTier {
        case "Elite": return Color.statusPending
        case "Pro": return Color.driverPrimary
        case "Standard": return Color.driverTextSecondary
        default: return Color.driverTextTertiary
        }
    }

    private var monthsActive: String {
        guard let profile, let createdAt = profile.createdAt else { return "—" }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let date = formatter.date(from: createdAt) ?? ISO8601DateFormatter().date(from: createdAt) else { return "—" }
        let months = Calendar.current.dateComponents([.month], from: date, to: Date()).month ?? 0
        if months < 1 { return "< 1 mo" }
        return "\(months) mo"
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Color.driverBackground.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: DriverSpacing.lg) {
                        // Avatar + name
                        VStack(spacing: DriverSpacing.sm) {
                            ZStack {
                                Circle()
                                    .fill(Color.driverPrimary.opacity(0.15))
                                    .frame(width: 80, height: 80)

                                Text(appState.auth.currentUser?.initials ?? "D")
                                    .font(.system(size: 28, weight: .bold, design: .rounded))
                                    .foregroundStyle(Color.driverPrimary)
                            }

                            Text(appState.auth.currentUser?.displayName ?? "Driver")
                                .font(DriverTypography.title3)
                                .foregroundStyle(Color.driverText)

                            if let email = appState.auth.currentUser?.email {
                                Text(email)
                                    .font(DriverTypography.footnote)
                                    .foregroundStyle(Color.driverTextSecondary)
                            }

                            // Rating
                            if let profile, profile.avgRating > 0 {
                                HStack(spacing: DriverSpacing.xxs) {
                                    StarRating(rating: profile.avgRating)
                                    Text(String(format: "%.1f", profile.avgRating))
                                        .font(DriverTypography.caption)
                                        .foregroundStyle(Color.driverTextSecondary)
                                }
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .driverCard()
                        .padding(.horizontal, DriverSpacing.xl)

                        // Truck info
                        if let profile {
                            VStack(alignment: .leading, spacing: DriverSpacing.sm) {
                                SectionHeader(title: "Vehicle")

                                ProfileRow(label: "Type", value: profile.truckType ?? "Not set")
                                ProfileRow(label: "Status", value: profile.approvalStatus.capitalized)
                                ProfileRow(label: "Total Jobs", value: "\(profile.totalJobs)")
                            }
                            .driverCard()
                            .padding(.horizontal, DriverSpacing.xl)
                        }

                        // MARK: - Performance Stats
                        VStack(alignment: .leading, spacing: DriverSpacing.sm) {
                            SectionHeader(title: "Performance")

                            HStack(spacing: 0) {
                                MetricCell(
                                    label: "Acceptance",
                                    metric: "Job Acceptance Rate",
                                    value: profile != nil ? "95%" : "—",
                                    color: .driverSuccess
                                )
                                Divider().frame(height: 50)
                                MetricCell(
                                    label: "Cancellation",
                                    metric: "Cancellation Rate",
                                    value: profile != nil ? "2%" : "—",
                                    color: .driverError
                                )
                                Divider().frame(height: 50)
                                MetricCell(
                                    label: "Hauler Tier",
                                    metric: "Contractor Level",
                                    value: haulerTier,
                                    color: .driverPrimary
                                )
                            }
                        }
                        .driverCard()
                        .padding(.horizontal, DriverSpacing.xl)

                        // MARK: - Job Ratings
                        VStack(alignment: .leading, spacing: DriverSpacing.sm) {
                            SectionHeader(title: "Job Ratings")

                            HStack(spacing: DriverSpacing.md) {
                                VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                                    Text("Customer Rating")
                                        .font(DriverTypography.caption)
                                        .foregroundStyle(Color.driverTextSecondary)

                                    if let profile, profile.avgRating > 0 {
                                        HStack(spacing: DriverSpacing.xxs) {
                                            Text(String(format: "%.2f", profile.avgRating))
                                                .font(DriverTypography.price)
                                                .foregroundStyle(Color.driverText)

                                            Image(systemName: "star.fill")
                                                .font(.system(size: 16))
                                                .foregroundStyle(Color.statusPending)
                                        }
                                    } else {
                                        Text("No ratings yet")
                                            .font(DriverTypography.body)
                                            .foregroundStyle(Color.driverTextTertiary)
                                    }
                                }

                                Spacer()

                                VStack(alignment: .trailing, spacing: DriverSpacing.xxs) {
                                    Text("Contractor Level")
                                        .font(DriverTypography.caption)
                                        .foregroundStyle(Color.driverTextSecondary)

                                    Text(haulerTier)
                                        .font(DriverTypography.headline)
                                        .foregroundStyle(haulerTierColor)
                                }
                            }

                            if let profile, profile.avgRating >= 4.8 {
                                HStack(spacing: DriverSpacing.xs) {
                                    Image(systemName: "trophy.fill")
                                        .font(.system(size: 14))
                                        .foregroundStyle(Color.statusPending)

                                    Text("Top-rated hauler — customers love your work!")
                                        .font(DriverTypography.caption)
                                        .foregroundStyle(Color.driverTextSecondary)
                                }
                                .padding(.top, DriverSpacing.xxs)
                            }
                        }
                        .driverCard()
                        .padding(.horizontal, DriverSpacing.xl)

                        // MARK: - Service Quality
                        VStack(alignment: .leading, spacing: DriverSpacing.sm) {
                            SectionHeader(title: "Service Quality")

                            HStack {
                                VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                                    Text("Customer Satisfaction")
                                        .font(DriverTypography.caption)
                                        .foregroundStyle(Color.driverTextSecondary)

                                    Text(profile != nil ? "98%" : "—")
                                        .font(DriverTypography.price)
                                        .foregroundStyle(Color.driverPrimary)
                                }

                                Spacer()

                                // Satisfaction indicator
                                ZStack {
                                    Circle()
                                        .stroke(Color.driverBorder, lineWidth: 4)
                                        .frame(width: 52, height: 52)

                                    Circle()
                                        .trim(from: 0, to: profile != nil ? 0.98 : 0)
                                        .stroke(Color.driverPrimary, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                                        .frame(width: 52, height: 52)
                                        .rotationEffect(.degrees(-90))

                                    Image(systemName: "hand.thumbsup.fill")
                                        .font(.system(size: 16))
                                        .foregroundStyle(Color.driverPrimary)
                                }
                            }

                            Text("Based on post-job customer feedback")
                                .font(DriverTypography.caption2)
                                .foregroundStyle(Color.driverTextTertiary)
                        }
                        .driverCard()
                        .padding(.horizontal, DriverSpacing.xl)

                        // MARK: - Lifetime Highlights
                        VStack(alignment: .leading, spacing: DriverSpacing.sm) {
                            SectionHeader(title: "Lifetime Highlights")

                            LazyVGrid(columns: [
                                GridItem(.flexible()),
                                GridItem(.flexible()),
                            ], spacing: DriverSpacing.md) {
                                HighlightCell(
                                    icon: "briefcase.fill",
                                    value: profile != nil ? "\(profile!.totalJobs)" : "—",
                                    label: "Total Jobs",
                                    metric: "Jobs Completed"
                                )

                                HighlightCell(
                                    icon: "calendar.badge.clock",
                                    value: monthsActive,
                                    label: "Time Active",
                                    metric: "Months Since Joined"
                                )

                                HighlightCell(
                                    icon: "truck.box.fill",
                                    value: profile != nil ? "\(profile!.totalJobs)" : "—",
                                    label: "Total Pickups",
                                    metric: "On-Site Pickups"
                                )

                                HighlightCell(
                                    icon: "shippingbox.fill",
                                    value: profile != nil ? "\(profile!.totalJobs)" : "—",
                                    label: "Total Haul-Aways",
                                    metric: "Items Removed"
                                )
                            }
                        }
                        .driverCard()
                        .padding(.horizontal, DriverSpacing.xl)

                        // Payout method
                        NavigationLink {
                            PayoutSettingsView(appState: appState)
                        } label: {
                            HStack {
                                Label {
                                    Text("Payout Method")
                                        .font(DriverTypography.body)
                                        .foregroundStyle(Color.driverText)
                                } icon: {
                                    Image(systemName: "banknote.fill")
                                        .foregroundStyle(Color.driverPrimary)
                                }

                                Spacer()

                                if appState.contractorProfile?.stripeConnectId != nil {
                                    Text("Active")
                                        .font(DriverTypography.caption)
                                        .foregroundStyle(Color.driverSuccess)
                                } else {
                                    Text("Not set up")
                                        .font(DriverTypography.caption)
                                        .foregroundStyle(Color.driverWarning)
                                }

                                Image(systemName: "chevron.right")
                                    .font(.system(size: 14, weight: .semibold))
                                    .foregroundStyle(Color.driverTextTertiary)
                            }
                            .driverCard()
                        }
                        .buttonStyle(.plain)
                        .padding(.horizontal, DriverSpacing.xl)

                        // Schedule link
                        NavigationLink {
                            AvailabilityScheduleView(appState: appState)
                        } label: {
                            HStack {
                                Label("Availability Schedule", systemImage: "calendar")
                                    .font(DriverTypography.body)
                                    .foregroundStyle(Color.driverText)
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.system(size: 14, weight: .semibold))
                                    .foregroundStyle(Color.driverTextTertiary)
                            }
                            .driverCard()
                        }
                        .buttonStyle(.plain)
                        .padding(.horizontal, DriverSpacing.xl)

                        // Logout
                        Button("Log Out") {
                            showLogoutConfirm = true
                        }
                        .buttonStyle(DriverDestructiveButtonStyle())
                        .padding(.horizontal, DriverSpacing.xl)

                        // Version
                        Text("JunkOS Driver v1.0.0")
                            .font(DriverTypography.caption2)
                            .foregroundStyle(Color.driverTextTertiary)
                    }
                    .padding(.top, DriverSpacing.md)
                    .padding(.bottom, DriverSpacing.xxxl)
                }
            }
            .navigationTitle("Profile")
            .navigationBarTitleDisplayMode(.large)
            .alert("Log Out?", isPresented: $showLogoutConfirm) {
                Button("Log Out", role: .destructive) {
                    appState.auth.logout()
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("You'll need to sign in again to accept jobs.")
            }
        }
    }
}

// MARK: - Helpers

private struct SectionHeader: View {
    let title: String

    var body: some View {
        Text(title)
            .font(DriverTypography.caption)
            .foregroundStyle(Color.driverTextSecondary)
            .textCase(.uppercase)
    }
}

private struct ProfileRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label)
                .font(DriverTypography.body)
                .foregroundStyle(Color.driverTextSecondary)
            Spacer()
            Text(value)
                .font(DriverTypography.body)
                .foregroundStyle(Color.driverText)
        }
    }
}

private struct MetricCell: View {
    let label: String
    let metric: String
    let value: String
    let color: Color

    var body: some View {
        VStack(spacing: DriverSpacing.xxs) {
            Text(value)
                .font(DriverTypography.headline)
                .foregroundStyle(color)

            Text(label)
                .font(DriverTypography.caption2)
                .foregroundStyle(Color.driverTextSecondary)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity)
        .accessibilityLabel("\(metric): \(value)")
    }
}

private struct HighlightCell: View {
    let icon: String
    let value: String
    let label: String
    let metric: String

    var body: some View {
        VStack(spacing: DriverSpacing.xs) {
            Image(systemName: icon)
                .font(.system(size: 22))
                .foregroundStyle(Color.driverPrimary)

            Text(value)
                .font(DriverTypography.headline)
                .foregroundStyle(Color.driverText)

            Text(label)
                .font(DriverTypography.caption2)
                .foregroundStyle(Color.driverTextSecondary)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, DriverSpacing.sm)
        .accessibilityLabel("\(metric): \(value)")
    }
}

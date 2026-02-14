//
//  PayoutSettingsView.swift
//  Umuve Pro
//
//  Stripe Connect payout status and onboarding access.
//  Shows Connect status badge and action buttons for setup/management.
//

import SwiftUI
import SafariServices

struct PayoutSettingsView: View {
    @Bindable var appState: AppState
    @State private var viewModel = StripeConnectViewModel()

    var body: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            ScrollView {
                VStack(spacing: DriverSpacing.lg) {
                    // Status card
                    statusCard
                        .padding(.horizontal, DriverSpacing.xl)

                    // Action section
                    actionSection
                        .padding(.horizontal, DriverSpacing.xl)

                    // Info section
                    infoSection
                        .padding(.horizontal, DriverSpacing.xl)

                    // Security note
                    HStack(spacing: DriverSpacing.xs) {
                        Image(systemName: "lock.shield.fill")
                            .font(.system(size: 14))
                            .foregroundStyle(Color.driverPrimary)

                        Text("Your banking information is encrypted and securely handled by Stripe.")
                            .font(DriverTypography.caption2)
                            .foregroundStyle(Color.driverTextTertiary)
                    }
                    .padding(.horizontal, DriverSpacing.xl)
                }
                .padding(.top, DriverSpacing.md)
                .padding(.bottom, DriverSpacing.xxxl)
            }
        }
        .navigationTitle("Payout Method")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await viewModel.checkStatus()
        }
        .sheet(isPresented: $viewModel.showSafari) {
            if let url = viewModel.accountLinkURL {
                SafariView(url: url)
                    .onDisappear {
                        Task {
                            await viewModel.onSafariDismissed()
                            // Reload profile to update Connect status
                            await appState.loadContractorProfile()
                        }
                    }
            }
        }
    }

    // MARK: - Status Card

    @ViewBuilder
    private var statusCard: some View {
        HStack(spacing: DriverSpacing.md) {
            statusIcon

            VStack(alignment: .leading, spacing: DriverSpacing.xxxs) {
                Text(statusTitle)
                    .font(DriverTypography.headline)
                    .foregroundStyle(Color.driverText)

                Text(statusDescription)
                    .font(DriverTypography.caption)
                    .foregroundStyle(Color.driverTextSecondary)
            }

            Spacer()
        }
        .driverCard()
    }

    @ViewBuilder
    private var statusIcon: some View {
        switch viewModel.onboardingStatus {
        case .loading:
            ZStack {
                Circle()
                    .fill(Color.gray.opacity(0.15))
                    .frame(width: 48, height: 48)

                ProgressView()
                    .tint(Color.gray)
            }

        case .notSetUp:
            ZStack {
                Circle()
                    .fill(Color.driverWarning.opacity(0.15))
                    .frame(width: 48, height: 48)

                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 22))
                    .foregroundStyle(Color.driverWarning)
            }

        case .pendingVerification:
            ZStack {
                Circle()
                    .fill(Color.orange.opacity(0.15))
                    .frame(width: 48, height: 48)

                Image(systemName: "clock.fill")
                    .font(.system(size: 22))
                    .foregroundStyle(Color.orange)
            }

        case .active:
            ZStack {
                Circle()
                    .fill(Color.driverSuccess.opacity(0.15))
                    .frame(width: 48, height: 48)

                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 22))
                    .foregroundStyle(Color.driverSuccess)
            }

        case .failed:
            ZStack {
                Circle()
                    .fill(Color.driverError.opacity(0.15))
                    .frame(width: 48, height: 48)

                Image(systemName: "xmark.circle.fill")
                    .font(.system(size: 22))
                    .foregroundStyle(Color.driverError)
            }
        }
    }

    private var statusTitle: String {
        switch viewModel.onboardingStatus {
        case .loading:
            return "Checking Status..."
        case .notSetUp:
            return "Not Set Up"
        case .pendingVerification:
            return "Pending Verification"
        case .active:
            return "Active"
        case .failed:
            return "Failed"
        }
    }

    private var statusDescription: String {
        switch viewModel.onboardingStatus {
        case .loading:
            return "Loading your payout status..."
        case .notSetUp:
            return "Add a bank account to receive your earnings."
        case .pendingVerification:
            return "Verification is in progress."
        case .active:
            return "Your earnings are deposited automatically."
        case .failed(let error):
            return error
        }
    }

    // MARK: - Action Section

    @ViewBuilder
    private var actionSection: some View {
        VStack(alignment: .leading, spacing: DriverSpacing.md) {
            switch viewModel.onboardingStatus {
            case .loading:
                EmptyView()

            case .notSetUp:
                Button {
                    Task {
                        await viewModel.startOnboarding()
                    }
                } label: {
                    if viewModel.isCreatingAccount {
                        ProgressView().tint(.white)
                    } else {
                        Text("Set Up Stripe Connect")
                    }
                }
                .buttonStyle(DriverPrimaryButtonStyle(isEnabled: !viewModel.isCreatingAccount))
                .disabled(viewModel.isCreatingAccount)

            case .pendingVerification:
                VStack(spacing: DriverSpacing.sm) {
                    Text("Verification is in progress. You can complete any remaining steps.")
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverTextSecondary)
                        .multilineTextAlignment(.leading)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    Button {
                        Task {
                            await viewModel.startOnboarding()
                        }
                    } label: {
                        if viewModel.isCreatingAccount {
                            ProgressView().tint(.white)
                        } else {
                            Text("Complete Setup")
                        }
                    }
                    .buttonStyle(DriverPrimaryButtonStyle(isEnabled: !viewModel.isCreatingAccount))
                    .disabled(viewModel.isCreatingAccount)
                }

            case .active:
                VStack(spacing: DriverSpacing.sm) {
                    Text("Connected")
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverSuccess)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    Button {
                        Task {
                            await viewModel.startOnboarding()
                        }
                    } label: {
                        if viewModel.isCreatingAccount {
                            ProgressView().tint(.white)
                        } else {
                            Text("Manage Payout Account")
                        }
                    }
                    .buttonStyle(DriverPrimaryButtonStyle(isEnabled: !viewModel.isCreatingAccount))
                    .disabled(viewModel.isCreatingAccount)
                }

            case .failed:
                Button {
                    Task {
                        await viewModel.checkStatus()
                    }
                } label: {
                    Text("Retry")
                }
                .buttonStyle(DriverPrimaryButtonStyle(isEnabled: true))
            }
        }
    }

    // MARK: - Info Section

    @ViewBuilder
    private var infoSection: some View {
        VStack(alignment: .leading, spacing: DriverSpacing.md) {
            Text("How payouts work")
                .font(DriverTypography.title3)
                .foregroundStyle(Color.driverText)

            VStack(alignment: .leading, spacing: DriverSpacing.sm) {
                InfoRow(
                    icon: "dollarsign.circle.fill",
                    text: "You earn 80% of each completed job"
                )

                InfoRow(
                    icon: "calendar.circle.fill",
                    text: "Payouts are sent after each job is marked complete"
                )

                InfoRow(
                    icon: "clock.circle.fill",
                    text: "Funds typically arrive in 1-2 business days"
                )
            }
        }
        .driverCard()
    }
}

// MARK: - Info Row

private struct InfoRow: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(spacing: DriverSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundStyle(Color.driverPrimary)
                .frame(width: 20)

            Text(text)
                .font(DriverTypography.footnote)
                .foregroundStyle(Color.driverTextSecondary)

            Spacer()
        }
    }
}

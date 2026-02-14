//
//  StripeConnectOnboardingView.swift
//  Umuve Pro
//
//  Mandatory Stripe Connect setup screen.
//  Blocks driver from accessing app until Connect account is active.
//

import SwiftUI
import SafariServices

struct StripeConnectOnboardingView: View {
    @Bindable var appState: AppState
    @State private var viewModel = StripeConnectViewModel()

    var body: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            VStack(spacing: DriverSpacing.xxl) {
                Spacer()

                // Icon
                ZStack {
                    Circle()
                        .fill(Color.driverPrimary.opacity(0.1))
                        .frame(width: 120, height: 120)

                    Image(systemName: "creditcard.circle.fill")
                        .font(.system(size: 80))
                        .foregroundStyle(Color.driverPrimary)
                }

                // Title and subtitle
                VStack(spacing: DriverSpacing.sm) {
                    Text("Set Up Payments")
                        .font(DriverTypography.title)
                        .foregroundStyle(Color.driverText)
                        .multilineTextAlignment(.center)

                    Text("Connect your bank account to receive earnings from completed jobs.")
                        .font(DriverTypography.body)
                        .foregroundStyle(Color.driverTextSecondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, DriverSpacing.xl)
                }

                // Status indicator
                statusView
                    .padding(.horizontal, DriverSpacing.xl)

                Spacer()

                // Action button
                Button {
                    Task {
                        await viewModel.startOnboarding()
                    }
                } label: {
                    if viewModel.isCreatingAccount {
                        ProgressView()
                            .tint(.white)
                    } else {
                        Text("Connect with Stripe")
                    }
                }
                .buttonStyle(DriverPrimaryButtonStyle(isEnabled: !viewModel.isCreatingAccount))
                .disabled(viewModel.isCreatingAccount)
                .padding(.horizontal, DriverSpacing.xl)

                Spacer()
            }
        }
        .task {
            await viewModel.checkStatus()
        }
        .sheet(isPresented: $viewModel.showSafari) {
            if let url = viewModel.accountLinkURL {
                SafariView(url: url)
                    .onDisappear {
                        Task {
                            await viewModel.onSafariDismissed()
                            // Reload profile to update stripeConnectId
                            if case .active = viewModel.onboardingStatus {
                                await appState.loadContractorProfile()
                            }
                        }
                    }
            }
        }
    }

    @ViewBuilder
    private var statusView: some View {
        switch viewModel.onboardingStatus {
        case .loading:
            HStack(spacing: DriverSpacing.sm) {
                ProgressView()
                    .tint(Color.driverPrimary)
                Text("Checking status...")
                    .font(DriverTypography.footnote)
                    .foregroundStyle(Color.driverTextSecondary)
            }

        case .notSetUp:
            HStack(spacing: DriverSpacing.sm) {
                Image(systemName: "exclamationmark.circle.fill")
                    .foregroundStyle(Color.driverWarning)
                Text("Not set up")
                    .font(DriverTypography.footnote)
                    .foregroundStyle(Color.driverTextSecondary)
            }

        case .pendingVerification:
            VStack(spacing: DriverSpacing.xs) {
                HStack(spacing: DriverSpacing.sm) {
                    Image(systemName: "clock.fill")
                        .foregroundStyle(Color.orange)
                    Text("Pending verification")
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverTextSecondary)
                }

                Text("Verification in progress. You can complete any remaining steps.")
                    .font(DriverTypography.caption2)
                    .foregroundStyle(Color.driverTextTertiary)
                    .multilineTextAlignment(.center)
            }

        case .active:
            HStack(spacing: DriverSpacing.sm) {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(Color.driverSuccess)
                Text("Active")
                    .font(DriverTypography.footnote)
                    .foregroundStyle(Color.driverTextSecondary)
            }

        case .failed(let error):
            VStack(spacing: DriverSpacing.xs) {
                HStack(spacing: DriverSpacing.sm) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(Color.driverError)
                    Text("Failed")
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverError)
                }

                Text(error)
                    .font(DriverTypography.caption2)
                    .foregroundStyle(Color.driverTextTertiary)
                    .multilineTextAlignment(.center)
            }
        }
    }
}

// MARK: - Safari View

struct SafariView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        SFSafariViewController(url: url)
    }

    func updateUIViewController(_ uiViewController: SFSafariViewController, context: Context) {
        // No updates needed
    }
}

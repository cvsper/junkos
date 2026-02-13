//
//  ReferralView.swift
//  Umuve
//
//  "Refer a Friend" screen: shows the user's referral code,
//  copy-to-clipboard button, and share via UIActivityViewController.
//

import SwiftUI

struct ReferralView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @State private var referralCode: String = ""
    @State private var totalReferrals: Int = 0
    @State private var creditsEarned: Double = 0
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var copied = false
    @State private var showShareSheet = false

    var body: some View {
        ScrollView {
            VStack(spacing: UmuveSpacing.xlarge) {
                // Header illustration
                headerSection

                if isLoading {
                    ProgressView()
                        .padding(.vertical, UmuveSpacing.huge)
                } else if let error = errorMessage {
                    errorSection(error)
                } else {
                    // Referral code card
                    codeCard

                    // Stats
                    statsSection

                    // How it works
                    howItWorksSection
                }
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.bottom, UmuveSpacing.xxlarge)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.umuveBackground.ignoresSafeArea())
        .navigationTitle("Refer a Friend")
        .navigationBarTitleDisplayMode(.large)
        .task {
            await loadReferralCode()
        }
        .sheet(isPresented: $showShareSheet) {
            ShareSheet(items: [shareMessage])
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(spacing: UmuveSpacing.normal) {
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.umuvePrimary.opacity(0.2), Color.umuvePrimaryLight.opacity(0.1)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 100, height: 100)

                Image(systemName: "gift.fill")
                    .font(.system(size: 44))
                    .foregroundColor(.umuvePrimary)
            }
            .padding(.top, UmuveSpacing.large)

            Text("Share the love, earn rewards")
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveTextMuted)
                .multilineTextAlignment(.center)
        }
    }

    // MARK: - Code Card

    private var codeCard: some View {
        VStack(spacing: UmuveSpacing.normal) {
            Text("Your Referral Code")
                .font(UmuveTypography.captionFont)
                .foregroundColor(.umuveTextMuted)

            Text(referralCode)
                .font(.system(size: 32, weight: .bold, design: .monospaced))
                .foregroundColor(.umuvePrimary)
                .kerning(4)
                .padding(.vertical, UmuveSpacing.medium)

            HStack(spacing: UmuveSpacing.medium) {
                // Copy button
                Button(action: copyCode) {
                    HStack(spacing: UmuveSpacing.small) {
                        Image(systemName: copied ? "checkmark" : "doc.on.doc")
                            .font(.system(size: 14, weight: .semibold))
                        Text(copied ? "Copied!" : "Copy Code")
                            .font(UmuveTypography.captionFont.weight(.semibold))
                    }
                    .foregroundColor(copied ? .umuveSuccess : .umuvePrimary)
                    .padding(.horizontal, UmuveSpacing.large)
                    .padding(.vertical, UmuveSpacing.medium)
                    .background(
                        (copied ? Color.umuveSuccess : Color.umuvePrimary).opacity(0.1)
                    )
                    .clipShape(Capsule())
                }

                // Share button
                Button(action: { showShareSheet = true }) {
                    HStack(spacing: UmuveSpacing.small) {
                        Image(systemName: "square.and.arrow.up")
                            .font(.system(size: 14, weight: .semibold))
                        Text("Share")
                            .font(UmuveTypography.captionFont.weight(.semibold))
                    }
                    .foregroundColor(.white)
                    .padding(.horizontal, UmuveSpacing.large)
                    .padding(.vertical, UmuveSpacing.medium)
                    .background(Color.umuvePrimary)
                    .clipShape(Capsule())
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(UmuveSpacing.xlarge)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }

    // MARK: - Stats

    private var statsSection: some View {
        HStack(spacing: UmuveSpacing.normal) {
            StatCard(title: "Referrals", value: "\(totalReferrals)", icon: "person.2.fill")
            StatCard(title: "Credits Earned", value: String(format: "$%.0f", creditsEarned), icon: "dollarsign.circle.fill")
        }
    }

    // MARK: - How It Works

    private var howItWorksSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("How It Works")
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)

            VStack(spacing: UmuveSpacing.medium) {
                ReferralStep(number: 1, text: "Share your code with friends and family")
                ReferralStep(number: 2, text: "They get a discount on their first booking")
                ReferralStep(number: 3, text: "You earn credit toward your next pickup")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(UmuveSpacing.large)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }

    // MARK: - Error Section

    private func errorSection(_ message: String) -> some View {
        VStack(spacing: UmuveSpacing.normal) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 40))
                .foregroundColor(.umuveWarning)

            Text(message)
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveTextMuted)
                .multilineTextAlignment(.center)

            Button(action: {
                Task { await loadReferralCode() }
            }) {
                Text("Try Again")
            }
            .buttonStyle(UmuveSecondaryButtonStyle())
            .frame(width: 160)
        }
        .padding(.vertical, UmuveSpacing.huge)
    }

    // MARK: - Helpers

    private var shareMessage: String {
        "Get junk removed the easy way! Use my referral code \(referralCode) on Umuve for a discount on your first pickup."
    }

    private func copyCode() {
        UIPasteboard.general.string = referralCode
        withAnimation {
            copied = true
        }
        HapticManager.shared.lightTap()
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            withAnimation {
                copied = false
            }
        }
    }

    private func loadReferralCode() async {
        isLoading = true
        errorMessage = nil
        do {
            let response = try await APIClient.shared.getReferralCode()
            referralCode = response.referralCode
            totalReferrals = response.totalReferrals ?? 0
            creditsEarned = response.creditsEarned ?? 0
        } catch {
            errorMessage = "Could not load your referral code. Please try again."
            print("Referral code error: \(error.localizedDescription)")
        }
        isLoading = false
    }
}

// MARK: - Supporting Views

private struct StatCard: View {
    let title: String
    let value: String
    let icon: String

    var body: some View {
        VStack(spacing: UmuveSpacing.small) {
            Image(systemName: icon)
                .font(.system(size: 24))
                .foregroundColor(.umuvePrimary)

            Text(value)
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)

            Text(title)
                .font(UmuveTypography.captionFont)
                .foregroundColor(.umuveTextMuted)
        }
        .frame(maxWidth: .infinity)
        .padding(UmuveSpacing.large)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }
}

private struct ReferralStep: View {
    let number: Int
    let text: String

    var body: some View {
        HStack(spacing: UmuveSpacing.medium) {
            ZStack {
                Circle()
                    .fill(Color.umuvePrimary.opacity(0.1))
                    .frame(width: 32, height: 32)

                Text("\(number)")
                    .font(UmuveTypography.bodyFont.weight(.bold))
                    .foregroundColor(.umuvePrimary)
            }

            Text(text)
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveText)

            Spacer()
        }
    }
}

// MARK: - Share Sheet (UIActivityViewController wrapper)

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

#Preview {
    NavigationStack {
        ReferralView()
            .environmentObject(AuthenticationManager())
    }
}

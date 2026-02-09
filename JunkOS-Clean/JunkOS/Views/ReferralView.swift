//
//  ReferralView.swift
//  JunkOS
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
            VStack(spacing: JunkSpacing.xlarge) {
                // Header illustration
                headerSection

                if isLoading {
                    ProgressView()
                        .padding(.vertical, JunkSpacing.huge)
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
            .padding(.horizontal, JunkSpacing.large)
            .padding(.bottom, JunkSpacing.xxlarge)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.junkBackground.ignoresSafeArea())
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
        VStack(spacing: JunkSpacing.normal) {
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.junkPrimary.opacity(0.2), Color.junkPrimaryLight.opacity(0.1)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 100, height: 100)

                Image(systemName: "gift.fill")
                    .font(.system(size: 44))
                    .foregroundColor(.junkPrimary)
            }
            .padding(.top, JunkSpacing.large)

            Text("Share the love, earn rewards")
                .font(JunkTypography.bodyFont)
                .foregroundColor(.junkTextMuted)
                .multilineTextAlignment(.center)
        }
    }

    // MARK: - Code Card

    private var codeCard: some View {
        VStack(spacing: JunkSpacing.normal) {
            Text("Your Referral Code")
                .font(JunkTypography.captionFont)
                .foregroundColor(.junkTextMuted)

            Text(referralCode)
                .font(.system(size: 32, weight: .bold, design: .monospaced))
                .foregroundColor(.junkPrimary)
                .kerning(4)
                .padding(.vertical, JunkSpacing.medium)

            HStack(spacing: JunkSpacing.medium) {
                // Copy button
                Button(action: copyCode) {
                    HStack(spacing: JunkSpacing.small) {
                        Image(systemName: copied ? "checkmark" : "doc.on.doc")
                            .font(.system(size: 14, weight: .semibold))
                        Text(copied ? "Copied!" : "Copy Code")
                            .font(JunkTypography.captionFont.weight(.semibold))
                    }
                    .foregroundColor(copied ? .junkSuccess : .junkPrimary)
                    .padding(.horizontal, JunkSpacing.large)
                    .padding(.vertical, JunkSpacing.medium)
                    .background(
                        (copied ? Color.junkSuccess : Color.junkPrimary).opacity(0.1)
                    )
                    .clipShape(Capsule())
                }

                // Share button
                Button(action: { showShareSheet = true }) {
                    HStack(spacing: JunkSpacing.small) {
                        Image(systemName: "square.and.arrow.up")
                            .font(.system(size: 14, weight: .semibold))
                        Text("Share")
                            .font(JunkTypography.captionFont.weight(.semibold))
                    }
                    .foregroundColor(.white)
                    .padding(.horizontal, JunkSpacing.large)
                    .padding(.vertical, JunkSpacing.medium)
                    .background(Color.junkPrimary)
                    .clipShape(Capsule())
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(JunkSpacing.xlarge)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }

    // MARK: - Stats

    private var statsSection: some View {
        HStack(spacing: JunkSpacing.normal) {
            StatCard(title: "Referrals", value: "\(totalReferrals)", icon: "person.2.fill")
            StatCard(title: "Credits Earned", value: String(format: "$%.0f", creditsEarned), icon: "dollarsign.circle.fill")
        }
    }

    // MARK: - How It Works

    private var howItWorksSection: some View {
        VStack(alignment: .leading, spacing: JunkSpacing.normal) {
            Text("How It Works")
                .font(JunkTypography.h2Font)
                .foregroundColor(.junkText)

            VStack(spacing: JunkSpacing.medium) {
                ReferralStep(number: 1, text: "Share your code with friends and family")
                ReferralStep(number: 2, text: "They get a discount on their first booking")
                ReferralStep(number: 3, text: "You earn credit toward your next pickup")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(JunkSpacing.large)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }

    // MARK: - Error Section

    private func errorSection(_ message: String) -> some View {
        VStack(spacing: JunkSpacing.normal) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 40))
                .foregroundColor(.junkWarning)

            Text(message)
                .font(JunkTypography.bodyFont)
                .foregroundColor(.junkTextMuted)
                .multilineTextAlignment(.center)

            Button(action: {
                Task { await loadReferralCode() }
            }) {
                Text("Try Again")
            }
            .buttonStyle(JunkSecondaryButtonStyle())
            .frame(width: 160)
        }
        .padding(.vertical, JunkSpacing.huge)
    }

    // MARK: - Helpers

    private var shareMessage: String {
        "Get junk removed the easy way! Use my referral code \(referralCode) on JunkOS for a discount on your first pickup."
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
        VStack(spacing: JunkSpacing.small) {
            Image(systemName: icon)
                .font(.system(size: 24))
                .foregroundColor(.junkPrimary)

            Text(value)
                .font(JunkTypography.h2Font)
                .foregroundColor(.junkText)

            Text(title)
                .font(JunkTypography.captionFont)
                .foregroundColor(.junkTextMuted)
        }
        .frame(maxWidth: .infinity)
        .padding(JunkSpacing.large)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }
}

private struct ReferralStep: View {
    let number: Int
    let text: String

    var body: some View {
        HStack(spacing: JunkSpacing.medium) {
            ZStack {
                Circle()
                    .fill(Color.junkPrimary.opacity(0.1))
                    .frame(width: 32, height: 32)

                Text("\(number)")
                    .font(JunkTypography.bodyFont.weight(.bold))
                    .foregroundColor(.junkPrimary)
            }

            Text(text)
                .font(JunkTypography.bodyFont)
                .foregroundColor(.junkText)

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

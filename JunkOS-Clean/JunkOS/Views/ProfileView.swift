//
//  ProfileView.swift
//  JunkOS
//
//  Profile screen with settings, reviews, and legal links.
//

import SwiftUI

struct ProfileView: View {
    @State private var userName = "Guest User"
    @State private var userEmail = "guest@junkos.com"

    var body: some View {
        ScrollView {
            VStack(spacing: JunkSpacing.xlarge) {
                userInfoSection
                settingsSection
                reviewSection
                aboutLegalSection
            }
            .padding(.horizontal, JunkSpacing.large)
            .padding(.bottom, JunkSpacing.xxlarge)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.junkBackground.ignoresSafeArea())
        .navigationTitle("Profile")
        .navigationBarTitleDisplayMode(.large)
    }

    // MARK: - User Info Section
    private var userInfoSection: some View {
        VStack(spacing: JunkSpacing.normal) {
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.junkPrimary, Color.junkPrimaryDark],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 80, height: 80)

                Text(String(userName.prefix(1)))
                    .font(.system(size: 36, weight: .bold, design: .rounded))
                    .foregroundColor(.white)
            }

            Text(userName)
                .font(JunkTypography.h2Font)
                .foregroundColor(.junkText)

            Text(userEmail)
                .font(JunkTypography.bodySmallFont)
                .foregroundColor(.junkTextMuted)

            Button(action: {}) {
                Text("Edit Profile")
                    .font(JunkTypography.captionFont)
                    .foregroundColor(.junkPrimary)
                    .padding(.horizontal, JunkSpacing.large)
                    .padding(.vertical, JunkSpacing.small)
                    .background(Color.junkPrimary.opacity(0.1))
                    .clipShape(Capsule())
            }
        }
        .frame(maxWidth: .infinity)
        .padding(JunkSpacing.xlarge)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
        .padding(.top, JunkSpacing.normal)
    }

    // MARK: - Settings Section
    private var settingsSection: some View {
        VStack(alignment: .leading, spacing: JunkSpacing.normal) {
            Text("App Settings")
                .font(JunkTypography.h2Font)
                .foregroundColor(.junkText)

            VStack(spacing: 0) {
                SettingsRow(icon: "bell.fill", title: "Notifications", color: .categoryYellow, action: {})
                Divider().padding(.leading, 50)
                SettingsRow(icon: "location.fill", title: "Location Services", color: .categoryBlue, action: {})
                Divider().padding(.leading, 50)
                SettingsRow(icon: "creditcard.fill", title: "Payment Methods", color: .junkPrimary, action: {})
                Divider().padding(.leading, 50)
                SettingsRow(icon: "globe", title: "Language", color: .categoryPurple, action: {})
            }
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
            .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
        }
    }

    // MARK: - Review Section
    private var reviewSection: some View {
        VStack(alignment: .leading, spacing: JunkSpacing.normal) {
            Text("Review Us On")
                .font(JunkTypography.h2Font)
                .foregroundColor(.junkText)

            VStack(spacing: JunkSpacing.small) {
                ReviewPlatformRow(platform: "Google", icon: "magnifyingglass", rating: "4.9", url: "https://google.com")
                ReviewPlatformRow(platform: "App Store", icon: "apple.logo", rating: "4.8", url: "https://apps.apple.com")
                ReviewPlatformRow(platform: "BBB", icon: "shield.checkered", rating: "A+", url: "https://bbb.org")
                ReviewPlatformRow(platform: "Trust Pilot", icon: "star.fill", rating: "4.9", url: "https://trustpilot.com")
                ReviewPlatformRow(platform: "Yelp", icon: "message.fill", rating: "4.7", url: "https://yelp.com")
            }
        }
    }

    // MARK: - About & Legal Section
    private var aboutLegalSection: some View {
        VStack(alignment: .leading, spacing: JunkSpacing.normal) {
            Text("About & Legal")
                .font(JunkTypography.h2Font)
                .foregroundColor(.junkText)

            VStack(spacing: 0) {
                AboutRow(icon: "info.circle.fill", title: "About Us", action: {})
                Divider().padding(.leading, 50)
                AboutRow(icon: "doc.text.fill", title: "Certificate of Liability Insurance", action: {})
                Divider().padding(.leading, 50)
                AboutRow(icon: "hand.raised.fill", title: "Privacy Policy", action: {})
                Divider().padding(.leading, 50)
                AboutRow(icon: "doc.plaintext.fill", title: "Terms & Conditions", action: {})
                Divider().padding(.leading, 50)
                AboutRow(icon: "envelope.fill", title: "Contact Us", action: {})
            }
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
            .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
        }
    }
}

// MARK: - Settings Row
struct SettingsRow: View {
    let icon: String
    let title: String
    let color: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: JunkSpacing.normal) {
                ZStack {
                    Circle()
                        .fill(color.opacity(0.15))
                        .frame(width: 32, height: 32)

                    Image(systemName: icon)
                        .font(.system(size: 14))
                        .foregroundColor(color)
                }

                Text(title)
                    .font(JunkTypography.bodyFont)
                    .foregroundColor(.junkText)

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(.junkTextTertiary)
            }
            .padding(JunkSpacing.normal)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Review Platform Row
struct ReviewPlatformRow: View {
    let platform: String
    let icon: String
    let rating: String
    let url: String

    var body: some View {
        Button(action: {
            if let url = URL(string: url) {
                UIApplication.shared.open(url)
            }
        }) {
            HStack(spacing: JunkSpacing.normal) {
                ZStack {
                    Circle()
                        .fill(Color.junkPrimary.opacity(0.1))
                        .frame(width: 36, height: 36)

                    Image(systemName: icon)
                        .font(.system(size: 16))
                        .foregroundColor(.junkPrimary)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text(platform)
                        .font(JunkTypography.bodyFont.weight(.semibold))
                        .foregroundColor(.junkText)

                    HStack(spacing: 4) {
                        Image(systemName: "star.fill")
                            .font(.system(size: 11))
                            .foregroundColor(.categoryYellow)
                        Text(rating)
                            .font(JunkTypography.captionFont)
                            .foregroundColor(.junkTextMuted)
                    }
                }

                Spacer()

                Image(systemName: "arrow.up.right")
                    .font(.system(size: 13))
                    .foregroundColor(.junkTextTertiary)
            }
            .padding(JunkSpacing.normal)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: JunkRadius.md))
            .shadow(color: .black.opacity(0.04), radius: 2, x: 0, y: 1)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - About Row
struct AboutRow: View {
    let icon: String
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: JunkSpacing.normal) {
                Image(systemName: icon)
                    .font(.system(size: 18))
                    .foregroundColor(.junkPrimary)
                    .frame(width: 32)

                Text(title)
                    .font(JunkTypography.bodyFont)
                    .foregroundColor(.junkText)

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(.junkTextTertiary)
            }
            .padding(JunkSpacing.normal)
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    NavigationStack {
        ProfileView()
    }
}

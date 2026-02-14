//
//  ProfileView.swift
//  Umuve
//
//  Profile screen with settings, reviews, and legal links.
//

import SwiftUI

struct ProfileView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @State private var userName = "Guest User"
    @State private var userEmail = "guest@goumuve.com"
    @State private var showSignOutConfirmation = false

    var body: some View {
        ScrollView {
            VStack(spacing: UmuveSpacing.xlarge) {
                userInfoSection
                settingsSection
                reviewSection
                aboutLegalSection
                signOutSection
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.bottom, UmuveSpacing.xxlarge)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.umuveBackground.ignoresSafeArea())
        .navigationTitle("Profile")
        .navigationBarTitleDisplayMode(.large)
        .alert("Sign Out", isPresented: $showSignOutConfirmation) {
            Button("Cancel", role: .cancel) { }
            Button("Sign Out", role: .destructive) {
                Task {
                    await authManager.logout()
                }
            }
        } message: {
            Text("Are you sure you want to sign out?")
        }
    }

    // MARK: - User Info Section
    private var userInfoSection: some View {
        VStack(spacing: UmuveSpacing.normal) {
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.umuvePrimary, Color.umuvePrimaryDark],
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
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)

            Text(userEmail)
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(.umuveTextMuted)

            Button(action: {}) {
                Text("Edit Profile")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.umuvePrimary)
                    .padding(.horizontal, UmuveSpacing.large)
                    .padding(.vertical, UmuveSpacing.small)
                    .background(Color.umuvePrimary.opacity(0.1))
                    .clipShape(Capsule())
            }
        }
        .frame(maxWidth: .infinity)
        .padding(UmuveSpacing.xlarge)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
        .padding(.top, UmuveSpacing.normal)
    }

    // MARK: - Settings Section
    private var settingsSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("App Settings")
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)

            VStack(spacing: 0) {
                SettingsRow(icon: "bell.fill", title: "Notifications", color: .categoryYellow, action: {})
                Divider().padding(.leading, 50)
                SettingsRow(icon: "location.fill", title: "Location Services", color: .categoryBlue, action: {})
                Divider().padding(.leading, 50)
                SettingsRow(icon: "creditcard.fill", title: "Payment Methods", color: .umuvePrimary, action: {})
                Divider().padding(.leading, 50)
                SettingsRow(icon: "globe", title: "Language", color: .categoryPurple, action: {})
            }
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
            .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
        }
    }

    // MARK: - Review Section
    private var reviewSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("Review Us On")
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)

            VStack(spacing: UmuveSpacing.small) {
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
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("About & Legal")
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)

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
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
            .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
        }
    }

    // MARK: - Sign Out Section
    private var signOutSection: some View {
        Button(action: {
            showSignOutConfirmation = true
        }) {
            Text("Sign Out")
                .font(UmuveTypography.bodyFont.weight(.semibold))
                .foregroundColor(.umuveError)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(Color.umuveError.opacity(0.1))
                .cornerRadius(UmuveRadius.md)
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
            HStack(spacing: UmuveSpacing.normal) {
                ZStack {
                    Circle()
                        .fill(color.opacity(0.15))
                        .frame(width: 32, height: 32)

                    Image(systemName: icon)
                        .font(.system(size: 14))
                        .foregroundColor(color)
                }

                Text(title)
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveText)

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(.umuveTextTertiary)
            }
            .padding(UmuveSpacing.normal)
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
            HStack(spacing: UmuveSpacing.normal) {
                ZStack {
                    Circle()
                        .fill(Color.umuvePrimary.opacity(0.1))
                        .frame(width: 36, height: 36)

                    Image(systemName: icon)
                        .font(.system(size: 16))
                        .foregroundColor(.umuvePrimary)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text(platform)
                        .font(UmuveTypography.bodyFont.weight(.semibold))
                        .foregroundColor(.umuveText)

                    HStack(spacing: 4) {
                        Image(systemName: "star.fill")
                            .font(.system(size: 11))
                            .foregroundColor(.categoryYellow)
                        Text(rating)
                            .font(UmuveTypography.captionFont)
                            .foregroundColor(.umuveTextMuted)
                    }
                }

                Spacer()

                Image(systemName: "arrow.up.right")
                    .font(.system(size: 13))
                    .foregroundColor(.umuveTextTertiary)
            }
            .padding(UmuveSpacing.normal)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
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
            HStack(spacing: UmuveSpacing.normal) {
                Image(systemName: icon)
                    .font(.system(size: 18))
                    .foregroundColor(.umuvePrimary)
                    .frame(width: 32)

                Text(title)
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveText)

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(.umuveTextTertiary)
            }
            .padding(UmuveSpacing.normal)
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    NavigationStack {
        ProfileView()
    }
}

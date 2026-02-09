//
//  AccountView.swift
//  JunkOS
//
//  User account, settings, and profile.
//

import SwiftUI

struct AccountView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @State private var showLogoutAlert = false
    @State private var showEditProfile = false
    @State private var showPaymentMethods = false
    @State private var showReferral = false

    var body: some View {
        ScrollView {
            VStack(spacing: JunkSpacing.xlarge) {
                // Profile Section
                profileSection

                // Guest mode callout
                if authManager.currentUser?.id == "guest" {
                    guestCallout
                }

                // Menu Options
                menuSection

                // Logout Button
                logoutButton

                // App Version
                Text("Version 1.0.0")
                    .font(JunkTypography.captionFont)
                    .foregroundColor(.junkTextTertiary)
                    .padding(.bottom, JunkSpacing.large)
            }
            .padding(.horizontal, JunkSpacing.large)
            .padding(.bottom, JunkSpacing.xxlarge)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.junkBackground.ignoresSafeArea())
        .navigationTitle("Account")
        .navigationBarTitleDisplayMode(.large)
        .sheet(isPresented: $showEditProfile) {
            EditProfileSheet(authManager: authManager)
        }
        .sheet(isPresented: $showPaymentMethods) {
            PaymentMethodsSheet()
        }
        .sheet(isPresented: $showReferral) {
            NavigationStack {
                ReferralView()
                    .environmentObject(authManager)
                    .toolbar {
                        ToolbarItem(placement: .topBarLeading) {
                            Button("Done") { showReferral = false }
                                .foregroundColor(.junkPrimary)
                        }
                    }
            }
        }
        .alert(
            authManager.currentUser?.id == "guest" ? "Exit Guest Mode" : "Log Out",
            isPresented: $showLogoutAlert
        ) {
            Button("Cancel", role: .cancel) {}
            Button(
                authManager.currentUser?.id == "guest" ? "Exit" : "Log Out",
                role: .destructive
            ) {
                authManager.logout()
                HapticManager.shared.success()
            }
        } message: {
            Text(authManager.currentUser?.id == "guest"
                ? "Exit guest mode and return to sign in?"
                : "Are you sure you want to log out?")
        }
    }

    // MARK: - Profile Section

    private var profileSection: some View {
        VStack(spacing: JunkSpacing.normal) {
            // Avatar
            ZStack(alignment: .bottomTrailing) {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.junkPrimary, Color.junkPrimaryDark],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 88, height: 88)
                    .overlay(
                        Text(initials)
                            .font(.system(size: 34, weight: .bold, design: .rounded))
                            .foregroundColor(.white)
                    )

                if authManager.currentUser?.id == "guest" {
                    Text("GUEST")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundColor(.white)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 3)
                        .background(Capsule().fill(Color.junkWarning))
                }
            }

            // Name and contact
            VStack(spacing: JunkSpacing.tiny) {
                if let name = authManager.currentUser?.name {
                    Text(name)
                        .font(JunkTypography.h2Font)
                        .foregroundColor(.junkText)
                }

                if let email = authManager.currentUser?.email {
                    HStack(spacing: JunkSpacing.tiny) {
                        Image(systemName: "envelope.fill")
                            .font(.system(size: 12))
                            .foregroundColor(.junkTextMuted)
                        Text(email)
                            .font(JunkTypography.bodySmallFont)
                            .foregroundColor(.junkTextMuted)
                    }
                }

                if let phone = authManager.currentUser?.phoneNumber {
                    HStack(spacing: JunkSpacing.tiny) {
                        Image(systemName: "phone.fill")
                            .font(.system(size: 12))
                            .foregroundColor(.junkTextMuted)
                        Text(phone)
                            .font(JunkTypography.bodySmallFont)
                            .foregroundColor(.junkTextMuted)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(JunkSpacing.xlarge)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
        .padding(.top, JunkSpacing.normal)
    }

    // MARK: - Guest Callout

    private var guestCallout: some View {
        VStack(spacing: JunkSpacing.medium) {
            HStack {
                Image(systemName: "info.circle.fill")
                    .foregroundColor(.junkPrimary)
                Text("You're browsing as a guest")
                    .font(JunkTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.junkText)
            }

            Text("Create an account to save your bookings and access them from any device")
                .font(JunkTypography.bodySmallFont)
                .foregroundColor(.junkTextMuted)
                .multilineTextAlignment(.center)

            Button(action: {
                authManager.logout()
            }) {
                Text("Create Account")
            }
            .buttonStyle(JunkPrimaryButtonStyle())
        }
        .padding(JunkSpacing.large)
        .background(Color.junkPrimary.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
    }

    // MARK: - Menu Section

    private var menuSection: some View {
        VStack(spacing: 0) {
            AccountMenuItem(icon: "person.fill", title: "Edit Profile", color: .junkPrimary) {
                showEditProfile = true
            }
            Divider().padding(.leading, 56)
            AccountMenuItem(icon: "bell.fill", title: "Notifications", color: .categoryYellow) {
                if let url = URL(string: UIApplication.openNotificationSettingsURLString) {
                    UIApplication.shared.open(url)
                }
            }
            Divider().padding(.leading, 56)
            AccountMenuItem(icon: "creditcard.fill", title: "Payment Methods", color: .categoryBlue) {
                showPaymentMethods = true
            }
            Divider().padding(.leading, 56)
            AccountMenuItem(icon: "gift.fill", title: "Refer a Friend", color: .categoryOrange) {
                showReferral = true
            }
            Divider().padding(.leading, 56)
            AccountMenuItem(icon: "doc.text.fill", title: "Terms & Privacy", color: .categoryPurple) {
                if let url = URL(string: "https://landing-page-premium-five.vercel.app/terms") {
                    UIApplication.shared.open(url)
                }
            }
            Divider().padding(.leading, 56)
            AccountMenuItem(icon: "questionmark.circle.fill", title: "Help & Support", color: .junkInfo) {
                if let url = URL(string: "mailto:support@junkos.com") {
                    UIApplication.shared.open(url)
                }
            }
        }
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }

    // MARK: - Logout Button

    private var logoutButton: some View {
        Button(action: { showLogoutAlert = true }) {
            HStack(spacing: JunkSpacing.small) {
                Image(systemName: "rectangle.portrait.and.arrow.right")
                Text(authManager.currentUser?.id == "guest" ? "Exit Guest Mode" : "Log Out")
                    .font(JunkTypography.bodyFont.weight(.semibold))
            }
            .foregroundColor(.junkError)
            .frame(maxWidth: .infinity)
            .padding(.vertical, JunkSpacing.normal)
            .background(Color.junkError.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: JunkRadius.md))
        }
    }

    private var initials: String {
        guard let name = authManager.currentUser?.name else { return "?" }
        let components = name.split(separator: " ")
        if components.count >= 2 {
            return String(components[0].prefix(1) + components[1].prefix(1)).uppercased()
        } else if let first = components.first {
            return String(first.prefix(1)).uppercased()
        }
        return "?"
    }
}

// MARK: - Account Menu Item

struct AccountMenuItem: View {
    let icon: String
    let title: String
    var color: Color = .junkPrimary
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
            .padding(.horizontal, JunkSpacing.normal)
            .padding(.vertical, JunkSpacing.medium)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Edit Profile Sheet

struct EditProfileSheet: View {
    let authManager: AuthenticationManager
    @Environment(\.dismiss) private var dismiss
    @State private var name: String = ""
    @State private var email: String = ""
    @State private var phone: String = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: JunkSpacing.large) {
                    // Avatar
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

                        Image(systemName: "camera.fill")
                            .font(.system(size: 28))
                            .foregroundColor(.white)
                    }
                    .padding(.top, JunkSpacing.xlarge)

                    VStack(spacing: JunkSpacing.normal) {
                        VStack(alignment: .leading, spacing: JunkSpacing.tiny) {
                            Text("Name")
                                .font(JunkTypography.captionFont)
                                .foregroundColor(.junkTextMuted)
                            TextField("Your name", text: $name)
                                .font(JunkTypography.bodyFont)
                                .padding(JunkSpacing.normal)
                                .background(Color.junkBackground)
                                .clipShape(RoundedRectangle(cornerRadius: JunkRadius.md))
                        }

                        VStack(alignment: .leading, spacing: JunkSpacing.tiny) {
                            Text("Email")
                                .font(JunkTypography.captionFont)
                                .foregroundColor(.junkTextMuted)
                            TextField("Email address", text: $email)
                                .font(JunkTypography.bodyFont)
                                .keyboardType(.emailAddress)
                                .textContentType(.emailAddress)
                                .autocapitalization(.none)
                                .padding(JunkSpacing.normal)
                                .background(Color.junkBackground)
                                .clipShape(RoundedRectangle(cornerRadius: JunkRadius.md))
                        }

                        VStack(alignment: .leading, spacing: JunkSpacing.tiny) {
                            Text("Phone")
                                .font(JunkTypography.captionFont)
                                .foregroundColor(.junkTextMuted)
                            TextField("Phone number", text: $phone)
                                .font(JunkTypography.bodyFont)
                                .keyboardType(.phonePad)
                                .textContentType(.telephoneNumber)
                                .padding(JunkSpacing.normal)
                                .background(Color.junkBackground)
                                .clipShape(RoundedRectangle(cornerRadius: JunkRadius.md))
                        }
                    }
                    .padding(.horizontal, JunkSpacing.large)

                    Button(action: { dismiss() }) {
                        Text("Save Changes")
                    }
                    .buttonStyle(JunkPrimaryButtonStyle())
                    .padding(.horizontal, JunkSpacing.large)
                }
            }
            .background(Color.white.ignoresSafeArea())
            .navigationTitle("Edit Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                        .foregroundColor(.junkPrimary)
                }
            }
        }
        .onAppear {
            name = authManager.currentUser?.name ?? ""
            email = authManager.currentUser?.email ?? ""
            phone = authManager.currentUser?.phoneNumber ?? ""
        }
    }
}

// MARK: - Payment Methods Sheet

struct PaymentMethodsSheet: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: JunkSpacing.xlarge) {
                Spacer()

                ZStack {
                    Circle()
                        .fill(Color.junkPrimary.opacity(0.1))
                        .frame(width: 100, height: 100)

                    Image(systemName: "creditcard.fill")
                        .font(.system(size: 40))
                        .foregroundColor(.junkPrimary)
                }

                Text("No payment methods")
                    .font(JunkTypography.h2Font)
                    .foregroundColor(.junkText)

                Text("Payment methods will be added during your first booking.")
                    .font(JunkTypography.bodyFont)
                    .foregroundColor(.junkTextMuted)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, JunkSpacing.huge)

                Spacer()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.junkBackground.ignoresSafeArea())
            .navigationTitle("Payment Methods")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Done") { dismiss() }
                        .foregroundColor(.junkPrimary)
                }
            }
        }
    }
}

#Preview {
    NavigationStack {
        AccountView()
            .environmentObject(AuthenticationManager())
    }
}

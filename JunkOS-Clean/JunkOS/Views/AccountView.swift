//
//  AccountView.swift
//  Umuve
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
            VStack(spacing: UmuveSpacing.xlarge) {
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
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.umuveTextTertiary)
                    .padding(.bottom, UmuveSpacing.large)
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.bottom, UmuveSpacing.xxlarge)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.umuveBackground.ignoresSafeArea())
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
                                .foregroundColor(.umuvePrimary)
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
                Task {
                    await authManager.logout()
                    HapticManager.shared.success()
                }
            }
        } message: {
            Text(authManager.currentUser?.id == "guest"
                ? "Exit guest mode and return to sign in?"
                : "Are you sure you want to log out?")
        }
    }

    // MARK: - Profile Section

    private var profileSection: some View {
        VStack(spacing: UmuveSpacing.normal) {
            // Avatar
            ZStack(alignment: .bottomTrailing) {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.umuvePrimary, Color.umuvePrimaryDark],
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
                        .background(Capsule().fill(Color.umuveWarning))
                }
            }

            // Name and contact
            VStack(spacing: UmuveSpacing.tiny) {
                if let name = authManager.currentUser?.name {
                    Text(name)
                        .font(UmuveTypography.h2Font)
                        .foregroundColor(.umuveText)
                }

                if let email = authManager.currentUser?.email {
                    HStack(spacing: UmuveSpacing.tiny) {
                        Image(systemName: "envelope.fill")
                            .font(.system(size: 12))
                            .foregroundColor(.umuveTextMuted)
                        Text(email)
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.umuveTextMuted)
                    }
                }

                if let phone = authManager.currentUser?.phoneNumber {
                    HStack(spacing: UmuveSpacing.tiny) {
                        Image(systemName: "phone.fill")
                            .font(.system(size: 12))
                            .foregroundColor(.umuveTextMuted)
                        Text(phone)
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.umuveTextMuted)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(UmuveSpacing.xlarge)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
        .padding(.top, UmuveSpacing.normal)
    }

    // MARK: - Guest Callout

    private var guestCallout: some View {
        VStack(spacing: UmuveSpacing.medium) {
            HStack {
                Image(systemName: "info.circle.fill")
                    .foregroundColor(.umuvePrimary)
                Text("You're browsing as a guest")
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)
            }

            Text("Create an account to save your bookings and access them from any device")
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(.umuveTextMuted)
                .multilineTextAlignment(.center)

            Button(action: {
                Task {
                    await authManager.logout()
                }
            }) {
                Text("Create Account")
            }
            .buttonStyle(UmuvePrimaryButtonStyle())
        }
        .padding(UmuveSpacing.large)
        .background(Color.umuvePrimary.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
    }

    // MARK: - Menu Section

    private var menuSection: some View {
        VStack(spacing: 0) {
            AccountMenuItem(icon: "person.fill", title: "Edit Profile", color: .umuvePrimary) {
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
            AccountMenuItem(icon: "questionmark.circle.fill", title: "Help & Support", color: .umuveInfo) {
                if let url = URL(string: "mailto:support@goumuve.com") {
                    UIApplication.shared.open(url)
                }
            }
        }
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }

    // MARK: - Logout Button

    private var logoutButton: some View {
        Button(action: { showLogoutAlert = true }) {
            HStack(spacing: UmuveSpacing.small) {
                Image(systemName: "rectangle.portrait.and.arrow.right")
                Text(authManager.currentUser?.id == "guest" ? "Exit Guest Mode" : "Log Out")
                    .font(UmuveTypography.bodyFont.weight(.semibold))
            }
            .foregroundColor(.umuveError)
            .frame(maxWidth: .infinity)
            .padding(.vertical, UmuveSpacing.normal)
            .background(Color.umuveError.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
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
    var color: Color = .umuvePrimary
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
            .padding(.horizontal, UmuveSpacing.normal)
            .padding(.vertical, UmuveSpacing.medium)
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
                VStack(spacing: UmuveSpacing.large) {
                    // Avatar
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

                        Image(systemName: "camera.fill")
                            .font(.system(size: 28))
                            .foregroundColor(.white)
                    }
                    .padding(.top, UmuveSpacing.xlarge)

                    VStack(spacing: UmuveSpacing.normal) {
                        VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                            Text("Name")
                                .font(UmuveTypography.captionFont)
                                .foregroundColor(.umuveTextMuted)
                            TextField("Your name", text: $name)
                                .font(UmuveTypography.bodyFont)
                                .padding(UmuveSpacing.normal)
                                .background(Color.umuveBackground)
                                .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
                        }

                        VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                            Text("Email")
                                .font(UmuveTypography.captionFont)
                                .foregroundColor(.umuveTextMuted)
                            TextField("Email address", text: $email)
                                .font(UmuveTypography.bodyFont)
                                .keyboardType(.emailAddress)
                                .textContentType(.emailAddress)
                                .autocapitalization(.none)
                                .padding(UmuveSpacing.normal)
                                .background(Color.umuveBackground)
                                .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
                        }

                        VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                            Text("Phone")
                                .font(UmuveTypography.captionFont)
                                .foregroundColor(.umuveTextMuted)
                            TextField("Phone number", text: $phone)
                                .font(UmuveTypography.bodyFont)
                                .keyboardType(.phonePad)
                                .textContentType(.telephoneNumber)
                                .padding(UmuveSpacing.normal)
                                .background(Color.umuveBackground)
                                .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
                        }
                    }
                    .padding(.horizontal, UmuveSpacing.large)

                    Button(action: { dismiss() }) {
                        Text("Save Changes")
                    }
                    .buttonStyle(UmuvePrimaryButtonStyle())
                    .padding(.horizontal, UmuveSpacing.large)
                }
            }
            .background(Color.white.ignoresSafeArea())
            .navigationTitle("Edit Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                        .foregroundColor(.umuvePrimary)
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
            VStack(spacing: UmuveSpacing.xlarge) {
                Spacer()

                ZStack {
                    Circle()
                        .fill(Color.umuvePrimary.opacity(0.1))
                        .frame(width: 100, height: 100)

                    Image(systemName: "creditcard.fill")
                        .font(.system(size: 40))
                        .foregroundColor(.umuvePrimary)
                }

                Text("No payment methods")
                    .font(UmuveTypography.h2Font)
                    .foregroundColor(.umuveText)

                Text("Payment methods will be added during your first booking.")
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, UmuveSpacing.huge)

                Spacer()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.umuveBackground.ignoresSafeArea())
            .navigationTitle("Payment Methods")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Done") { dismiss() }
                        .foregroundColor(.umuvePrimary)
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

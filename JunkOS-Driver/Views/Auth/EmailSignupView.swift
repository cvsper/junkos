//
//  EmailSignupView.swift
//  Umuve Pro
//
//  Email/password signup and login for drivers
//

import SwiftUI

struct EmailSignupView: View {
    @Bindable var appState: AppState
    let onDismiss: () -> Void

    @State private var email = ""
    @State private var password = ""
    @State private var name = ""
    @State private var isSignup = true
    @State private var hasInviteCode = false
    @State private var inviteCode = ""

    var body: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            ScrollView {
                VStack(spacing: DriverSpacing.lg) {
                    // Header
                    VStack(spacing: DriverSpacing.md) {
                        Image(systemName: "envelope.fill")
                            .font(.system(size: 48))
                            .foregroundStyle(Color.driverPrimary)

                        Text(isSignup ? "Create Account" : "Welcome Back")
                            .font(DriverTypography.title2)
                            .foregroundStyle(Color.driverText)
                    }
                    .padding(.top, DriverSpacing.xxl)

                    // Form
                    VStack(spacing: DriverSpacing.md) {
                        // Name field (signup only)
                        if isSignup {
                            TextField("Name (optional)", text: $name)
                                .textContentType(.name)
                                .autocapitalization(.words)
                                .padding()
                                .background(Color.white)
                                .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                                .overlay(
                                    RoundedRectangle(cornerRadius: DriverRadius.md)
                                        .stroke(Color.driverBorder, lineWidth: 1)
                                )

                            // Operator invite code checkbox
                            Toggle("Do you have an invite code from an operator?", isOn: $hasInviteCode)
                                .font(DriverTypography.body)
                                .foregroundStyle(Color.driverText)
                                .tint(Color.driverPrimary)

                            // Invite code field (shown when checkbox is checked)
                            if hasInviteCode {
                                TextField("Operator Invite Code", text: $inviteCode)
                                    .textInputAutocapitalization(.characters)
                                    .padding()
                                    .background(Color.white)
                                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                                    .overlay(
                                        RoundedRectangle(cornerRadius: DriverRadius.md)
                                            .stroke(Color.driverBorder, lineWidth: 1)
                                    )
                            }
                        }

                        // Email field
                        TextField("Email", text: $email)
                            .textContentType(.emailAddress)
                            .textInputAutocapitalization(.never)
                            .keyboardType(.emailAddress)
                            .padding()
                            .background(Color.white)
                            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                            .overlay(
                                RoundedRectangle(cornerRadius: DriverRadius.md)
                                    .stroke(Color.driverBorder, lineWidth: 1)
                            )

                        // Password field
                        SecureField("Password", text: $password)
                            .textContentType(isSignup ? .newPassword : .password)
                            .padding()
                            .background(Color.white)
                            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                            .overlay(
                                RoundedRectangle(cornerRadius: DriverRadius.md)
                                    .stroke(Color.driverBorder, lineWidth: 1)
                            )

                        // Submit button
                        Button {
                            submit()
                        } label: {
                            Text(isSignup ? "Sign Up" : "Log In")
                                .font(DriverTypography.headline)
                                .foregroundStyle(.white)
                                .frame(maxWidth: .infinity)
                                .frame(height: 52)
                                .background(Color.driverPrimary)
                                .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                        }
                        .disabled(email.isEmpty || password.isEmpty)
                        .opacity(email.isEmpty || password.isEmpty ? 0.5 : 1)

                        // Toggle signup/login
                        Button {
                            isSignup.toggle()
                            appState.auth.errorMessage = nil
                        } label: {
                            Text(isSignup ? "Already have an account? Log in" : "Don't have an account? Sign up")
                                .font(DriverTypography.body)
                                .foregroundStyle(Color.driverPrimary)
                        }

                        // Error message
                        if let errorMessage = appState.auth.errorMessage {
                            Text(errorMessage)
                                .font(DriverTypography.footnote)
                                .foregroundStyle(Color.driverError)
                                .multilineTextAlignment(.center)
                        }
                    }
                    .padding(.horizontal, DriverSpacing.xl)

                    Spacer()
                }
            }

            // Back button
            VStack {
                HStack {
                    Button {
                        onDismiss()
                    } label: {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 16, weight: .medium))
                            .foregroundStyle(Color.driverText)
                            .frame(width: 32, height: 32)
                            .background(Color.white)
                            .clipShape(Circle())
                    }
                    .padding(DriverSpacing.md)

                    Spacer()
                }
                Spacer()
            }

            // Loading overlay
            if appState.auth.isLoading {
                Color.black.opacity(0.3)
                    .ignoresSafeArea()
                ProgressView()
                    .tint(.white)
                    .scaleEffect(1.5)
            }
        }
        .preferredColorScheme(.light)
    }

    private func submit() {
        Task {
            HapticManager.shared.lightTap()

            if isSignup {
                await appState.auth.emailSignup(
                    email: email.trimmingCharacters(in: .whitespaces),
                    password: password,
                    name: name.isEmpty ? nil : name.trimmingCharacters(in: .whitespaces),
                    inviteCode: hasInviteCode && !inviteCode.isEmpty ? inviteCode.trimmingCharacters(in: .whitespaces) : nil
                )
            } else {
                await appState.auth.emailLogin(
                    email: email.trimmingCharacters(in: .whitespaces),
                    password: password
                )
            }

            if appState.auth.isAuthenticated {
                onDismiss()
            }
        }
    }
}

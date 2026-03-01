//
//  EmailSignupView.swift
//  Umuve Pro
//
//  Email/password signup and login for drivers
//

import SwiftUI

enum LoginMethod {
    case email
    case phone
}

struct EmailSignupView: View {
    @Bindable var appState: AppState
    var isSignup: Bool = true
    let onDismiss: () -> Void

    @State private var email = ""
    @State private var phoneNumber = ""
    @State private var password = ""
    @State private var name = ""
    @State private var isSignupState = true
    @State private var hasInviteCode = false
    @State private var inviteCode = ""
    @State private var loginMethod: LoginMethod = .email
    @State private var autoSwitchedToLogin = false

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

                        Text(isSignupState ? "Create Account" : "Welcome Back")
                            .font(DriverTypography.title2)
                            .foregroundStyle(Color.driverText)
                    }
                    .padding(.top, DriverSpacing.xxl)
                    .onAppear {
                        isSignupState = isSignup
                    }

                    // Form
                    VStack(spacing: DriverSpacing.md) {
                        // Login method toggle (login only)
                        if !isSignupState {
                            HStack(spacing: 0) {
                                Button {
                                    loginMethod = .email
                                } label: {
                                    Text("Email")
                                        .font(DriverTypography.callout)
                                        .foregroundStyle(loginMethod == .email ? Color.white : Color.driverText)
                                        .frame(maxWidth: .infinity)
                                        .padding(.vertical, DriverSpacing.sm)
                                        .background(loginMethod == .email ? Color.driverPrimary : Color.white)
                                }

                                Button {
                                    loginMethod = .phone
                                } label: {
                                    Text("Phone")
                                        .font(DriverTypography.callout)
                                        .foregroundStyle(loginMethod == .phone ? Color.white : Color.driverText)
                                        .frame(maxWidth: .infinity)
                                        .padding(.vertical, DriverSpacing.sm)
                                        .background(loginMethod == .phone ? Color.driverPrimary : Color.white)
                                }
                            }
                            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                            .overlay(
                                RoundedRectangle(cornerRadius: DriverRadius.md)
                                    .stroke(Color.driverBorder, lineWidth: 1)
                            )
                        }

                        // Name field (signup only)
                        if isSignupState {
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

                        // Email or Phone field based on login method
                        if isSignupState || loginMethod == .email {
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
                        } else {
                            TextField("Phone Number", text: $phoneNumber)
                                .textContentType(.telephoneNumber)
                                .keyboardType(.phonePad)
                                .padding()
                                .background(Color.white)
                                .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                                .overlay(
                                    RoundedRectangle(cornerRadius: DriverRadius.md)
                                        .stroke(Color.driverBorder, lineWidth: 1)
                                )
                        }

                        // Password field
                        SecureField("Password", text: $password)
                            .textContentType(isSignupState ? .newPassword : .password)
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
                            Text(isSignupState ? "Sign Up" : "Log In")
                                .font(DriverTypography.headline)
                                .foregroundStyle(.white)
                                .frame(maxWidth: .infinity)
                                .frame(height: 52)
                                .background(Color.driverPrimary)
                                .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                        }
                        .disabled(isSubmitDisabled)
                        .opacity(isSubmitDisabled ? 0.5 : 1)

                        // Toggle signup/login
                        Button {
                            isSignupState.toggle()
                            autoSwitchedToLogin = false
                            appState.auth.errorMessage = nil
                        } label: {
                            Text(isSignupState ? "Already have an account? Log in" : "Don't have an account? Sign up")
                                .font(DriverTypography.body)
                                .foregroundStyle(Color.driverPrimary)
                        }

                        // Error message
                        if let errorMessage = appState.auth.errorMessage {
                            VStack(spacing: DriverSpacing.xs) {
                                Text(errorMessage)
                                    .font(DriverTypography.footnote)
                                    .foregroundStyle(Color.driverError)
                                    .multilineTextAlignment(.center)

                                if autoSwitchedToLogin && !appState.auth.isAuthenticated {
                                    Text("Your email and password are still filled in.")
                                        .font(DriverTypography.footnote)
                                        .foregroundStyle(Color.driverTextSecondary)
                                        .multilineTextAlignment(.center)
                                }
                            }
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
                    .scaleEffect(x: 1.5, y: 1.5)
            }
        }
        .preferredColorScheme(.light)
        .onChange(of: appState.auth.errorMessage) { _, newValue in
            guard isSignupState,
                  appState.auth.indicatesExistingAccount(message: newValue),
                  !appState.auth.isAuthenticated else { return }
            loginMethod = .email
            isSignupState = false
            autoSwitchedToLogin = true
            appState.auth.errorMessage = "Account already exists. Log in with your existing password."
        }
    }

    private var isSubmitDisabled: Bool {
        if password.isEmpty { return true }

        if isSignupState {
            return email.isEmpty
        } else {
            switch loginMethod {
            case .email:
                return email.isEmpty || !isValidEmail(email)
            case .phone:
                return phoneNumber.isEmpty || !isValidPhone(phoneNumber)
            }
        }
    }

    private func isValidEmail(_ email: String) -> Bool {
        let emailRegex = "[A-Z0-9a-z._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,64}"
        let emailPredicate = NSPredicate(format: "SELF MATCHES %@", emailRegex)
        return emailPredicate.evaluate(with: email)
    }

    private func isValidPhone(_ phone: String) -> Bool {
        // Remove non-numeric characters for validation
        let digits = phone.filter { $0.isNumber }
        // Accept 10 digits (US) or 11 digits (with country code)
        return digits.count >= 10 && digits.count <= 15
    }

    private func formatPhoneNumber(_ phone: String) -> String {
        // Format to +1XXXXXXXXXX for US numbers
        let digits = phone.filter { $0.isNumber }
        if digits.count == 10 {
            return "+1" + digits
        } else if digits.count == 11 && digits.hasPrefix("1") {
            return "+" + digits
        }
        return phone // Return as-is for international
    }

    private func submit() {
        Task {
            HapticManager.shared.lightTap()

            if isSignupState {
                await appState.auth.emailSignup(
                    email: email.trimmingCharacters(in: .whitespaces),
                    password: password,
                    name: name.isEmpty ? nil : name.trimmingCharacters(in: .whitespaces),
                    inviteCode: hasInviteCode && !inviteCode.isEmpty ? inviteCode.trimmingCharacters(in: .whitespaces) : nil
                )
            } else {
                switch loginMethod {
                case .email:
                    await appState.auth.emailLogin(
                        email: email.trimmingCharacters(in: .whitespaces),
                        password: password
                    )
                case .phone:
                    let formattedPhone = formatPhoneNumber(phoneNumber.trimmingCharacters(in: .whitespaces))
                    await appState.auth.phoneLogin(
                        phone: formattedPhone,
                        password: password
                    )
                }
            }

            if appState.auth.isAuthenticated {
                onDismiss()
            }
        }
    }
}

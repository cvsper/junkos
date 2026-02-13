//
//  EmailLoginView.swift
//  Umuve
//
//  Email and password login form
//

import SwiftUI

struct EmailLoginView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @Environment(\.dismiss) var dismiss
    @State private var email = ""
    @State private var password = ""
    @State private var isLoading = false
    @State private var showPassword = false
    @State private var errorMessage: String?
    @State private var showForgotPassword = false
    @State private var forgotEmail = ""
    @State private var forgotPasswordSent = false
    @State private var forgotPasswordLoading = false
    @State private var forgotPasswordError: String?
    
    var body: some View {
        ScrollView {
            VStack(spacing: UmuveSpacing.xxlarge) {
                // Close button
                HStack {
                    Spacer()
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark")
                            .font(.title3)
                            .foregroundColor(.umuveText)
                            .padding()
                    }
                }
                
                // Header
                VStack(spacing: UmuveSpacing.large) {
                    Image(systemName: "envelope.circle.fill")
                        .font(.system(size: 80))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Color.umuvePrimary, Color.umuveCTA],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                    
                    Text("Log in with Email")
                        .font(.system(size: 32, weight: .bold))
                        .foregroundColor(.umuveText)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.top, UmuveSpacing.xlarge)
                
                // Form
                VStack(spacing: UmuveSpacing.large) {
                    // Email field
                    VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                        Text("Email Address")
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.umuveTextMuted)
                        
                        HStack {
                            Image(systemName: "envelope.fill")
                                .foregroundColor(.umuveTextMuted)
                            
                            TextField("your@email.com", text: $email)
                                .font(UmuveTypography.bodyFont)
                                .keyboardType(.emailAddress)
                                .autocapitalization(.none)
                                .autocorrectionDisabled()
                        }
                        .padding(UmuveSpacing.normal)
                        .background(Color.white)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.umuveBorder, lineWidth: 1)
                        )
                    }
                    
                    // Password field
                    VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                        Text("Password")
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.umuveTextMuted)
                        
                        HStack {
                            Image(systemName: "lock.fill")
                                .foregroundColor(.umuveTextMuted)
                            
                            if showPassword {
                                TextField("", text: $password)
                                    .font(UmuveTypography.bodyFont)
                                    .autocapitalization(.none)
                                    .autocorrectionDisabled()
                            } else {
                                SecureField("", text: $password)
                                    .font(UmuveTypography.bodyFont)
                                    .autocapitalization(.none)
                                    .autocorrectionDisabled()
                            }
                            
                            Button(action: { showPassword.toggle() }) {
                                Image(systemName: showPassword ? "eye.slash.fill" : "eye.fill")
                                    .foregroundColor(.umuveTextMuted)
                            }
                        }
                        .padding(UmuveSpacing.normal)
                        .background(Color.white)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.umuveBorder, lineWidth: 1)
                        )
                    }
                    
                    // Forgot password
                    HStack {
                        Spacer()
                        Button("Forgot Password?") {
                            forgotEmail = email
                            showForgotPassword = true
                        }
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuvePrimary)
                    }
                }
                .padding(.horizontal, UmuveSpacing.xlarge)
                
                // Error message
                if let error = errorMessage {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.red)
                        Text(error)
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.red)
                    }
                    .padding(UmuveSpacing.small)
                    .background(Color.red.opacity(0.1))
                    .cornerRadius(8)
                    .padding(.horizontal, UmuveSpacing.xlarge)
                    .transition(.scale.combined(with: .opacity))
                }
                
                Spacer()
                
                // Login button
                Button(action: login) {
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    } else {
                        Text("Log In")
                            .font(UmuveTypography.h3Font)
                            .foregroundColor(.white)
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(height: 56)
                .background(isFormValid ? Color.umuvePrimary : Color.umuveTextMuted)
                .cornerRadius(28)
                .disabled(!isFormValid || isLoading)
                .padding(.horizontal, UmuveSpacing.xlarge)
                .padding(.bottom, UmuveSpacing.xlarge)
            }
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .sheet(isPresented: $showForgotPassword) {
            forgotPasswordSheet
        }
    }

    // MARK: - Forgot Password Sheet
    private var forgotPasswordSheet: some View {
        NavigationView {
            VStack(spacing: UmuveSpacing.xxlarge) {
                // Icon
                Image(systemName: "lock.rotation")
                    .font(.system(size: 60))
                    .foregroundColor(.umuvePrimary)
                    .padding(.top, UmuveSpacing.xxlarge)

                // Title
                VStack(spacing: UmuveSpacing.small) {
                    Text("Reset Password")
                        .font(.system(size: 24, weight: .bold))
                        .foregroundColor(.umuveText)

                    Text("Enter your email and we'll send you a reset link")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, UmuveSpacing.xlarge)
                }

                if forgotPasswordSent {
                    // Success state
                    HStack(spacing: UmuveSpacing.small) {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.umuveSuccess)
                        Text("Reset link sent! Check your email.")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveSuccess)
                    }
                    .padding(UmuveSpacing.normal)
                    .background(Color.umuveSuccess.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
                    .padding(.horizontal, UmuveSpacing.xlarge)
                } else {
                    // Email field
                    VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                        HStack {
                            Image(systemName: "envelope.fill")
                                .foregroundColor(.umuveTextMuted)
                            TextField("your@email.com", text: $forgotEmail)
                                .font(UmuveTypography.bodyFont)
                                .keyboardType(.emailAddress)
                                .autocapitalization(.none)
                                .autocorrectionDisabled()
                        }
                        .padding(UmuveSpacing.normal)
                        .background(Color.white)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.umuveBorder, lineWidth: 1)
                        )
                    }
                    .padding(.horizontal, UmuveSpacing.xlarge)

                    if let error = forgotPasswordError {
                        Text(error)
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.red)
                            .padding(.horizontal, UmuveSpacing.xlarge)
                    }

                    // Send button
                    Button(action: sendForgotPassword) {
                        if forgotPasswordLoading {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        } else {
                            Text("Send Reset Link")
                                .font(UmuveTypography.h3Font)
                                .foregroundColor(.white)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 56)
                    .background(
                        forgotEmail.contains("@") ? Color.umuvePrimary : Color.umuveTextMuted
                    )
                    .cornerRadius(28)
                    .disabled(!forgotEmail.contains("@") || forgotPasswordLoading)
                    .padding(.horizontal, UmuveSpacing.xlarge)
                }

                Spacer()
            }
            .background(Color.umuveBackground.ignoresSafeArea())
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        showForgotPassword = false
                        forgotPasswordSent = false
                        forgotPasswordError = nil
                    }
                    .foregroundColor(.umuvePrimary)
                }
            }
        }
    }

    // MARK: - Helpers
    
    private var isFormValid: Bool {
        !email.isEmpty && email.contains("@") && password.count >= 6
    }
    
    private func sendForgotPassword() {
        forgotPasswordLoading = true
        forgotPasswordError = nil

        authManager.requestPasswordReset(email: forgotEmail) { success, error in
            forgotPasswordLoading = false
            if success {
                forgotPasswordSent = true
                HapticManager.shared.success()
            } else {
                forgotPasswordError = error ?? "Failed to send reset link"
                HapticManager.shared.error()
            }
        }
    }

    private func login() {
        isLoading = true
        errorMessage = nil
        HapticManager.shared.lightTap()
        
        authManager.loginWithEmail(email: email, password: password) { success, error in
            isLoading = false
            if success {
                HapticManager.shared.success()
                dismiss()
            } else {
                HapticManager.shared.error()
                errorMessage = error ?? "Invalid email or password"
            }
        }
    }
}

#Preview {
    NavigationView {
        EmailLoginView()
            .environmentObject(AuthenticationManager())
    }
}

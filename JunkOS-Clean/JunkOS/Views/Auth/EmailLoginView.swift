//
//  EmailLoginView.swift
//  JunkOS
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
            VStack(spacing: JunkSpacing.xxlarge) {
                // Close button
                HStack {
                    Spacer()
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark")
                            .font(.title3)
                            .foregroundColor(.junkText)
                            .padding()
                    }
                }
                
                // Header
                VStack(spacing: JunkSpacing.large) {
                    Image(systemName: "envelope.circle.fill")
                        .font(.system(size: 80))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Color.junkPrimary, Color.junkCTA],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                    
                    Text("Log in with Email")
                        .font(.system(size: 32, weight: .bold))
                        .foregroundColor(.junkText)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.top, JunkSpacing.xlarge)
                
                // Form
                VStack(spacing: JunkSpacing.large) {
                    // Email field
                    VStack(alignment: .leading, spacing: JunkSpacing.small) {
                        Text("Email Address")
                            .font(JunkTypography.bodySmallFont)
                            .foregroundColor(.junkTextMuted)
                        
                        HStack {
                            Image(systemName: "envelope.fill")
                                .foregroundColor(.junkTextMuted)
                            
                            TextField("your@email.com", text: $email)
                                .font(JunkTypography.bodyFont)
                                .keyboardType(.emailAddress)
                                .autocapitalization(.none)
                                .autocorrectionDisabled()
                        }
                        .padding(JunkSpacing.normal)
                        .background(Color.white)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.junkBorder, lineWidth: 1)
                        )
                    }
                    
                    // Password field
                    VStack(alignment: .leading, spacing: JunkSpacing.small) {
                        Text("Password")
                            .font(JunkTypography.bodySmallFont)
                            .foregroundColor(.junkTextMuted)
                        
                        HStack {
                            Image(systemName: "lock.fill")
                                .foregroundColor(.junkTextMuted)
                            
                            if showPassword {
                                TextField("", text: $password)
                                    .font(JunkTypography.bodyFont)
                                    .autocapitalization(.none)
                                    .autocorrectionDisabled()
                            } else {
                                SecureField("", text: $password)
                                    .font(JunkTypography.bodyFont)
                                    .autocapitalization(.none)
                                    .autocorrectionDisabled()
                            }
                            
                            Button(action: { showPassword.toggle() }) {
                                Image(systemName: showPassword ? "eye.slash.fill" : "eye.fill")
                                    .foregroundColor(.junkTextMuted)
                            }
                        }
                        .padding(JunkSpacing.normal)
                        .background(Color.white)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.junkBorder, lineWidth: 1)
                        )
                    }
                    
                    // Forgot password
                    HStack {
                        Spacer()
                        Button("Forgot Password?") {
                            forgotEmail = email
                            showForgotPassword = true
                        }
                        .font(JunkTypography.bodySmallFont)
                        .foregroundColor(.junkPrimary)
                    }
                }
                .padding(.horizontal, JunkSpacing.xlarge)
                
                // Error message
                if let error = errorMessage {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.red)
                        Text(error)
                            .font(JunkTypography.bodySmallFont)
                            .foregroundColor(.red)
                    }
                    .padding(JunkSpacing.small)
                    .background(Color.red.opacity(0.1))
                    .cornerRadius(8)
                    .padding(.horizontal, JunkSpacing.xlarge)
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
                            .font(JunkTypography.h3Font)
                            .foregroundColor(.white)
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(height: 56)
                .background(isFormValid ? Color.junkPrimary : Color.junkTextMuted)
                .cornerRadius(28)
                .disabled(!isFormValid || isLoading)
                .padding(.horizontal, JunkSpacing.xlarge)
                .padding(.bottom, JunkSpacing.xlarge)
            }
        }
        .background(Color.junkBackground.ignoresSafeArea())
        .sheet(isPresented: $showForgotPassword) {
            forgotPasswordSheet
        }
    }

    // MARK: - Forgot Password Sheet
    private var forgotPasswordSheet: some View {
        NavigationView {
            VStack(spacing: JunkSpacing.xxlarge) {
                // Icon
                Image(systemName: "lock.rotation")
                    .font(.system(size: 60))
                    .foregroundColor(.junkPrimary)
                    .padding(.top, JunkSpacing.xxlarge)

                // Title
                VStack(spacing: JunkSpacing.small) {
                    Text("Reset Password")
                        .font(.system(size: 24, weight: .bold))
                        .foregroundColor(.junkText)

                    Text("Enter your email and we'll send you a reset link")
                        .font(JunkTypography.bodyFont)
                        .foregroundColor(.junkTextMuted)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, JunkSpacing.xlarge)
                }

                if forgotPasswordSent {
                    // Success state
                    HStack(spacing: JunkSpacing.small) {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.junkSuccess)
                        Text("Reset link sent! Check your email.")
                            .font(JunkTypography.bodyFont)
                            .foregroundColor(.junkSuccess)
                    }
                    .padding(JunkSpacing.normal)
                    .background(Color.junkSuccess.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: JunkRadius.sm))
                    .padding(.horizontal, JunkSpacing.xlarge)
                } else {
                    // Email field
                    VStack(alignment: .leading, spacing: JunkSpacing.small) {
                        HStack {
                            Image(systemName: "envelope.fill")
                                .foregroundColor(.junkTextMuted)
                            TextField("your@email.com", text: $forgotEmail)
                                .font(JunkTypography.bodyFont)
                                .keyboardType(.emailAddress)
                                .autocapitalization(.none)
                                .autocorrectionDisabled()
                        }
                        .padding(JunkSpacing.normal)
                        .background(Color.white)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.junkBorder, lineWidth: 1)
                        )
                    }
                    .padding(.horizontal, JunkSpacing.xlarge)

                    if let error = forgotPasswordError {
                        Text(error)
                            .font(JunkTypography.bodySmallFont)
                            .foregroundColor(.red)
                            .padding(.horizontal, JunkSpacing.xlarge)
                    }

                    // Send button
                    Button(action: sendForgotPassword) {
                        if forgotPasswordLoading {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        } else {
                            Text("Send Reset Link")
                                .font(JunkTypography.h3Font)
                                .foregroundColor(.white)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 56)
                    .background(
                        forgotEmail.contains("@") ? Color.junkPrimary : Color.junkTextMuted
                    )
                    .cornerRadius(28)
                    .disabled(!forgotEmail.contains("@") || forgotPasswordLoading)
                    .padding(.horizontal, JunkSpacing.xlarge)
                }

                Spacer()
            }
            .background(Color.junkBackground.ignoresSafeArea())
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        showForgotPassword = false
                        forgotPasswordSent = false
                        forgotPasswordError = nil
                    }
                    .foregroundColor(.junkPrimary)
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

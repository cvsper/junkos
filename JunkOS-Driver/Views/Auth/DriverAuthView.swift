//
//  DriverAuthView.swift
//  Umuve Pro
//
//  Welcome screen with Apple Sign In only.
//  Clean white background with Umuve Pro branding and red accent.
//

import SwiftUI
import AuthenticationServices

struct DriverAuthView: View {
    @Bindable var appState: AppState
    @State private var showPhoneAuth = false
    @State private var showEmailAuth = false
    @State private var isSignupMode = false

    var body: some View {
        if showEmailAuth {
            EmailSignupView(appState: appState, isSignup: isSignupMode) {
                showEmailAuth = false
            }
        } else if showPhoneAuth {
            PhoneSignupView(appState: appState) {
                showPhoneAuth = false
            }
        } else {
            mainAuthView
        }
    }

    private var mainAuthView: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // Hero
                VStack(spacing: DriverSpacing.md) {
                    Image(systemName: "truck.box.fill")
                        .font(.system(size: 64))
                        .foregroundStyle(Color.driverPrimary)

                    Text("Umuve Pro")
                        .font(DriverTypography.title)
                        .foregroundStyle(Color.driverText)

                    Text("Earn money hauling junk on your schedule.\nBe your own boss.")
                        .font(DriverTypography.body)
                        .foregroundStyle(Color.driverTextSecondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, DriverSpacing.xxl)
                }

                Spacer()

                // Auth Options
                VStack(spacing: DriverSpacing.md) {
                    // Login Button (Primary)
                    Button {
                        isSignupMode = false
                        showEmailAuth = true
                    } label: {
                        Text("Log In")
                            .font(DriverTypography.headline)
                            .foregroundStyle(.white)
                            .frame(maxWidth: .infinity)
                            .frame(height: 52)
                            .background(Color.driverPrimary)
                            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                    }

                    // Sign Up Link (Secondary)
                    Button {
                        isSignupMode = true
                        showEmailAuth = true
                    } label: {
                        Text("Sign Up")
                            .font(DriverTypography.body)
                            .foregroundStyle(Color.driverPrimary)
                            .underline()
                    }
                    .padding(.top, DriverSpacing.xs)

                    // Divider
                    HStack(spacing: DriverSpacing.sm) {
                        Rectangle()
                            .fill(Color.driverBorder)
                            .frame(height: 1)
                        Text("or")
                            .font(DriverTypography.footnote)
                            .foregroundStyle(Color.driverTextSecondary)
                        Rectangle()
                            .fill(Color.driverBorder)
                            .frame(height: 1)
                    }
                    .padding(.vertical, DriverSpacing.sm)

                    // Apple Sign In Button
                    SignInWithAppleButton(.signIn) { request in
                        appState.auth.handleAppleSignInRequest(request)
                    } onCompletion: { result in
                        appState.auth.handleAppleSignInCompletion(result)
                    }
                    .signInWithAppleButtonStyle(.black)
                    .frame(height: 52)
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))

                    // Error message display
                    if let errorMessage = appState.auth.errorMessage {
                        Text(errorMessage)
                            .font(DriverTypography.footnote)
                            .foregroundStyle(Color.driverError)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, DriverSpacing.md)
                    }
                }
                .padding(.horizontal, DriverSpacing.xl)
                .padding(.bottom, DriverSpacing.xxl)

                // Debug: Clear Keychain button
                Button(action: {
                    KeychainHelper.delete(forKey: "authToken")
                    KeychainHelper.delete(forKey: "userId")
                    // Also clear old keys if they exist
                    KeychainHelper.delete(forKey: "com.junkos.driver.authToken")
                    KeychainHelper.delete(forKey: "com.junkos.driver.userId")
                    appState.auth.isAuthenticated = false
                    appState.auth.currentUser = nil
                    print("🗑️ Cleared all Keychain data")
                }) {
                    Text("Clear Keychain (Debug)")
                        .font(.system(size: 10))
                        .foregroundStyle(Color.gray.opacity(0.5))
                }
                .padding(.bottom, DriverSpacing.sm)
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
}

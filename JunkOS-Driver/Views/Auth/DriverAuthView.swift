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
    @State private var showPhoneSignup = false
    @State private var showEmailSignup = false

    var body: some View {
        if showPhoneSignup {
            PhoneSignupView(appState: appState) {
                showPhoneSignup = false
            }
        } else if showEmailSignup {
            EmailSignupView(appState: appState) {
                showEmailSignup = false
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

                // Sign In Options
                VStack(spacing: DriverSpacing.md) {
                    // Apple Sign In Button
                    SignInWithAppleButton(.signIn) { request in
                        appState.auth.handleAppleSignInRequest(request)
                    } onCompletion: { result in
                        appState.auth.handleAppleSignInCompletion(result)
                    }
                    .signInWithAppleButtonStyle(.black)
                    .frame(height: 52)
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))

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
                    .padding(.vertical, DriverSpacing.xs)

                    // Email Sign Up Button
                    Button {
                        showEmailSignup = true
                    } label: {
                        HStack(spacing: DriverSpacing.sm) {
                            Image(systemName: "envelope.fill")
                                .font(.system(size: 16, weight: .medium))
                            Text("Sign Up with Email")
                                .font(DriverTypography.headline)
                        }
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 52)
                        .background(Color.driverPrimary)
                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                    }

                    // Phone Sign Up Button
                    Button {
                        showPhoneSignup = true
                    } label: {
                        HStack(spacing: DriverSpacing.sm) {
                            Image(systemName: "phone.fill")
                                .font(.system(size: 16, weight: .medium))
                            Text("Sign Up with Phone Number")
                                .font(DriverTypography.headline)
                        }
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 52)
                        .background(Color.driverPrimary.opacity(0.8))
                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                    }

                    // Dev Login Button (for testing)
                    Button {
                        Task {
                            await appState.auth.devLogin()
                        }
                    } label: {
                        Text("Quick Test Login")
                            .font(DriverTypography.caption)
                            .foregroundStyle(Color.driverTextSecondary)
                    }
                    .padding(.top, DriverSpacing.sm)

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

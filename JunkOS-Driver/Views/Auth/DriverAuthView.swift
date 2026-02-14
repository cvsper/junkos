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

    var body: some View {
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

                // Apple Sign In Button
                VStack(spacing: DriverSpacing.sm) {
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

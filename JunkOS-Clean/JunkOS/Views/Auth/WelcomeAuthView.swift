//
//  WelcomeAuthView.swift
//  Umuve
//
//  Apple Sign In only screen
//

import SwiftUI
import AuthenticationServices

struct WelcomeAuthView: View {
    @EnvironmentObject var authManager: AuthenticationManager

    var body: some View {
        ZStack {
            // Clean white background
            Color.umuveBackground.ignoresSafeArea()

            VStack(spacing: UmuveSpacing.xxlarge) {
                Spacer()

                // Logo and branding
                VStack(spacing: UmuveSpacing.large) {
                    Image(systemName: "trash.circle.fill")
                        .font(.system(size: 120))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Color.umuvePrimary, Color.umuvePrimaryDark],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .shadow(color: Color.umuvePrimary.opacity(0.3), radius: 20, x: 0, y: 10)

                    VStack(spacing: UmuveSpacing.small) {
                        Text("Umuve")
                            .font(.system(size: 48, weight: .bold))
                            .foregroundColor(.umuvePrimary)

                        Text("Hauling made simple.")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveTextMuted)
                            .multilineTextAlignment(.center)
                    }
                }

                Spacer()

                // Sign in section
                VStack(spacing: UmuveSpacing.normal) {
                    // Apple Sign In button
                    SignInWithAppleButton(.signIn) { request in
                        authManager.handleAppleSignInRequest(request)
                    } onCompletion: { result in
                        authManager.handleAppleSignInCompletion(result)
                    }
                    .signInWithAppleButtonStyle(.black)
                    .frame(height: 52)
                    .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))

                    // Error message
                    if let errorMessage = authManager.errorMessage {
                        Text(errorMessage)
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.umuveError)
                            .multilineTextAlignment(.center)
                            .padding(.top, UmuveSpacing.small)
                    }
                }
                .padding(.horizontal, UmuveSpacing.xlarge)
                .padding(.bottom, UmuveSpacing.xxlarge)
                .overlay(
                    Group {
                        if authManager.isLoading {
                            ProgressView()
                                .scaleEffect(1.2)
                                .frame(maxWidth: .infinity, maxHeight: .infinity)
                                .background(Color.umuveBackground.opacity(0.8))
                        }
                    }
                )
            }
        }
    }
}

#Preview {
    WelcomeAuthView()
        .environmentObject(AuthenticationManager())
}

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
    @State private var showPhoneSignup = false

    var body: some View {
        ZStack {
            // Clean white background
            Color.umuveBackground.ignoresSafeArea()

            VStack(spacing: UmuveSpacing.xxlarge) {
                Spacer()

                // Logo and tagline — the wordmark already says "Umuve",
                // no need for a separate Text("Umuve") label below it.
                VStack(spacing: UmuveSpacing.medium) {
                    Image("UmuveLogo")
                        .resizable()
                        .scaledToFit()
                        .frame(height: 80)
                        .accessibilityLabel("Umuve")
                        .shadow(color: Color.umuvePrimary.opacity(0.15), radius: 12, x: 0, y: 6)

                    Text("Hauling made simple.")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)
                        .multilineTextAlignment(.center)
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

                    // Divider
                    HStack(spacing: UmuveSpacing.small) {
                        Rectangle()
                            .fill(Color.umuveBorder)
                            .frame(height: 1)
                        Text("or")
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundStyle(Color.umuveTextMuted)
                        Rectangle()
                            .fill(Color.umuveBorder)
                            .frame(height: 1)
                    }
                    .padding(.vertical, UmuveSpacing.tiny)

                    // Phone Sign Up Button
                    Button {
                        showPhoneSignup = true
                    } label: {
                        HStack(spacing: UmuveSpacing.small) {
                            Image(systemName: "phone.fill")
                                .font(.system(size: 16, weight: .medium))
                            Text("Sign Up with Phone Number")
                                .font(UmuveTypography.h3Font)
                        }
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 52)
                        .background(Color.umuvePrimary)
                        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
                    }

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
        .fullScreenCover(isPresented: $showPhoneSignup) {
            NavigationView {
                PhoneSignUpView()
                    .environmentObject(authManager)
            }
        }
    }
}

#Preview {
    WelcomeAuthView()
        .environmentObject(AuthenticationManager())
}

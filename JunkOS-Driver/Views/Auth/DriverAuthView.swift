//
//  DriverAuthView.swift
//  JunkOS Driver
//
//  Welcome screen with login options — email, Apple Sign In.
//

import SwiftUI
import AuthenticationServices

struct DriverAuthView: View {
    @Bindable var appState: AppState
    @State private var showLogin = false
    @State private var showSignup = false

    var body: some View {
        NavigationStack {
            ZStack {
                Color.driverBackground.ignoresSafeArea()

                VStack(spacing: 0) {
                    Spacer()

                    // Hero
                    VStack(spacing: DriverSpacing.md) {
                        Image(systemName: "truck.box.fill")
                            .font(.system(size: 64))
                            .foregroundStyle(Color.driverPrimary)

                        Text("Drive with JunkOS")
                            .font(DriverTypography.title)
                            .foregroundStyle(Color.driverText)

                        Text("Earn money hauling junk on your schedule.\nBe your own boss.")
                            .font(DriverTypography.body)
                            .foregroundStyle(Color.driverTextSecondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, DriverSpacing.xxl)
                    }

                    Spacer()

                    // Buttons
                    VStack(spacing: DriverSpacing.sm) {
                        Button("Sign In with Email") {
                            showLogin = true
                        }
                        .buttonStyle(DriverPrimaryButtonStyle())

                        Button("Create Account") {
                            showSignup = true
                        }
                        .buttonStyle(DriverSecondaryButtonStyle())

                        SignInWithAppleButton(.signIn) { request in
                            appState.auth.handleAppleSignInRequest(request)
                        } onCompletion: { result in
                            appState.auth.handleAppleSignInCompletion(result)
                        }
                        .signInWithAppleButtonStyle(.black)
                        .frame(height: 52)
                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                    }
                    .padding(.horizontal, DriverSpacing.xl)
                    .padding(.bottom, DriverSpacing.xxl)
                }
            }
            .navigationDestination(isPresented: $showLogin) {
                DriverLoginView(appState: appState)
            }
            .navigationDestination(isPresented: $showSignup) {
                DriverSignupView(appState: appState)
            }
        }
    }
}

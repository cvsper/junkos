//
//  LoginOptionsView.swift
//  Umuve
//
//  Login screen with multiple authentication options
//

import SwiftUI
import AuthenticationServices

struct LoginOptionsView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @Environment(\.dismiss) var dismiss
    @State private var showEmailLogin = false
    @State private var showPhoneSignUp = false
    
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
                
                Spacer(minLength: 40)
                
                // Header
                VStack(spacing: UmuveSpacing.large) {
                    Image(systemName: "trash.circle.fill")
                        .font(.system(size: 80))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Color.umuvePrimary, Color.umuveCTA],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                    
                    VStack(spacing: UmuveSpacing.small) {
                        Text("Welcome back")
                            .font(.system(size: 32, weight: .bold))
                            .foregroundColor(.umuveText)
                            .multilineTextAlignment(.center)
                        
                        Text("Login to access your account")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveTextMuted)
                            .multilineTextAlignment(.center)
                    }
                }
                
                // Login options
                VStack(spacing: UmuveSpacing.normal) {
                    // Email login
                    Button(action: {
                        showEmailLogin = true
                    }) {
                        HStack {
                            Image(systemName: "envelope.fill")
                                .font(.title3)
                            Text("Log in with Email")
                                .font(UmuveTypography.h3Font)
                            Spacer()
                        }
                        .foregroundColor(.umuveText)
                        .frame(maxWidth: .infinity)
                        .frame(height: 56)
                        .padding(.horizontal, UmuveSpacing.large)
                        .background(Color.white)
                        .cornerRadius(28)
                        .overlay(
                            RoundedRectangle(cornerRadius: 28)
                                .stroke(Color.umuveBorder, lineWidth: 2)
                        )
                    }
                    
                    // Phone login
                    Button(action: {
                        showPhoneSignUp = true
                    }) {
                        HStack {
                            Image(systemName: "phone.fill")
                                .font(.title3)
                            Text("Log in with Phone")
                                .font(UmuveTypography.h3Font)
                            Spacer()
                        }
                        .foregroundColor(.umuveText)
                        .frame(maxWidth: .infinity)
                        .frame(height: 56)
                        .padding(.horizontal, UmuveSpacing.large)
                        .background(Color.white)
                        .cornerRadius(28)
                        .overlay(
                            RoundedRectangle(cornerRadius: 28)
                                .stroke(Color.umuveBorder, lineWidth: 2)
                        )
                    }
                    
                    // Apple Sign In
                    SignInWithAppleButton(
                        onRequest: { request in
                            authManager.handleAppleSignInRequest(request)
                        },
                        onCompletion: { result in
                            authManager.handleAppleSignInCompletion(result)
                        }
                    )
                    .frame(height: 56)
                    .cornerRadius(28)
                    .signInWithAppleButtonStyle(.black)
                }
                .padding(.horizontal, UmuveSpacing.xlarge)
                
                Spacer()
                
                // Sign up link
                Button(action: {
                    dismiss()
                    // Parent will show phone signup
                }) {
                    VStack(spacing: 4) {
                        Text("Don't have an account yet?")
                            .foregroundColor(.umuveTextMuted)
                        Text("Create an account")
                            .fontWeight(.bold)
                            .foregroundColor(.umuvePrimary)
                    }
                    .font(UmuveTypography.bodyFont)
                    .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.bottom, UmuveSpacing.xlarge)
            }
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .fullScreenCover(isPresented: $showEmailLogin) {
            NavigationView {
                EmailLoginView()
                    .environmentObject(authManager)
            }
        }
        .fullScreenCover(isPresented: $showPhoneSignUp) {
            NavigationView {
                PhoneSignUpView()
                    .environmentObject(authManager)
            }
        }
    }
}

#Preview {
    NavigationView {
        LoginOptionsView()
            .environmentObject(AuthenticationManager())
    }
}

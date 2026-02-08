//
//  LoginOptionsView.swift
//  JunkOS
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
                
                Spacer(minLength: 40)
                
                // Header
                VStack(spacing: JunkSpacing.large) {
                    Image(systemName: "trash.circle.fill")
                        .font(.system(size: 80))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Color.junkPrimary, Color.junkCTA],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                    
                    VStack(spacing: JunkSpacing.small) {
                        Text("Welcome back")
                            .font(.system(size: 32, weight: .bold))
                            .foregroundColor(.junkText)
                            .multilineTextAlignment(.center)
                        
                        Text("Login to access your account")
                            .font(JunkTypography.bodyFont)
                            .foregroundColor(.junkTextMuted)
                            .multilineTextAlignment(.center)
                    }
                }
                
                // Login options
                VStack(spacing: JunkSpacing.normal) {
                    // Email login
                    Button(action: {
                        showEmailLogin = true
                    }) {
                        HStack {
                            Image(systemName: "envelope.fill")
                                .font(.title3)
                            Text("Log in with Email")
                                .font(JunkTypography.h3Font)
                            Spacer()
                        }
                        .foregroundColor(.junkText)
                        .frame(maxWidth: .infinity)
                        .frame(height: 56)
                        .padding(.horizontal, JunkSpacing.large)
                        .background(Color.white)
                        .cornerRadius(28)
                        .overlay(
                            RoundedRectangle(cornerRadius: 28)
                                .stroke(Color.junkBorder, lineWidth: 2)
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
                                .font(JunkTypography.h3Font)
                            Spacer()
                        }
                        .foregroundColor(.junkText)
                        .frame(maxWidth: .infinity)
                        .frame(height: 56)
                        .padding(.horizontal, JunkSpacing.large)
                        .background(Color.white)
                        .cornerRadius(28)
                        .overlay(
                            RoundedRectangle(cornerRadius: 28)
                                .stroke(Color.junkBorder, lineWidth: 2)
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
                .padding(.horizontal, JunkSpacing.xlarge)
                
                Spacer()
                
                // Sign up link
                Button(action: {
                    dismiss()
                    // Parent will show phone signup
                }) {
                    VStack(spacing: 4) {
                        Text("Don't have an account yet?")
                            .foregroundColor(.junkTextMuted)
                        Text("Create an account")
                            .fontWeight(.bold)
                            .foregroundColor(.junkPrimary)
                    }
                    .font(JunkTypography.bodyFont)
                    .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.bottom, JunkSpacing.xlarge)
            }
        }
        .background(Color.junkBackground.ignoresSafeArea())
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

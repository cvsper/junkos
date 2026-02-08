//
//  WelcomeAuthView.swift
//  JunkOS
//
//  Initial welcome screen with login/signup options
//

import SwiftUI

struct WelcomeAuthView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @State private var showPhoneSignUp = false
    @State private var showLogin = false
    
    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                colors: [Color.junkPrimary, Color.junkCTA],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VStack(spacing: JunkSpacing.xxlarge) {
                Spacer()
                
                // Logo and branding
                VStack(spacing: JunkSpacing.large) {
                    Image(systemName: "trash.circle.fill")
                        .font(.system(size: 120))
                        .foregroundStyle(.white)
                        .shadow(color: .black.opacity(0.2), radius: 20, x: 0, y: 10)
                    
                    VStack(spacing: JunkSpacing.small) {
                        Text("JunkOS")
                            .font(.system(size: 48, weight: .bold))
                            .foregroundColor(.white)
                        
                        Text("Junk removal made simple")
                            .font(JunkTypography.bodyFont)
                            .foregroundColor(.white.opacity(0.9))
                            .multilineTextAlignment(.center)
                    }
                }
                
                Spacer()
                
                // Action buttons
                VStack(spacing: JunkSpacing.normal) {
                    // Create Account (Primary action)
                    Button(action: {
                        showPhoneSignUp = true
                    }) {
                        Text("Create an account")
                            .font(JunkTypography.h3Font)
                            .foregroundColor(.junkPrimary)
                            .frame(maxWidth: .infinity)
                            .frame(height: 56)
                            .background(Color.white)
                            .cornerRadius(28)
                    }
                    
                    // Continue as Guest
                    Button(action: {
                        authManager.continueAsGuest()
                        HapticManager.shared.lightTap()
                    }) {
                        Text("Continue as Guest")
                            .font(JunkTypography.h3Font)
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .frame(height: 56)
                            .background(Color.white.opacity(0.2))
                            .cornerRadius(28)
                            .overlay(
                                RoundedRectangle(cornerRadius: 28)
                                    .stroke(Color.white.opacity(0.5), lineWidth: 2)
                            )
                    }
                    
                    // Login (Secondary action)
                    Button(action: {
                        showLogin = true
                    }) {
                        VStack(spacing: 4) {
                            Text("Already have an account?")
                                .foregroundColor(.white.opacity(0.9))
                            Text("Log In")
                                .fontWeight(.bold)
                                .foregroundColor(.white)
                        }
                        .font(JunkTypography.bodyFont)
                        .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity)
                }
                .padding(.horizontal, JunkSpacing.xlarge)
                .padding(.bottom, JunkSpacing.xxlarge)
            }
        }
        .fullScreenCover(isPresented: $showPhoneSignUp) {
            NavigationView {
                PhoneSignUpView()
                    .environmentObject(authManager)
            }
        }
        .fullScreenCover(isPresented: $showLogin) {
            NavigationView {
                LoginOptionsView()
                    .environmentObject(authManager)
            }
        }
    }
}

#Preview {
    WelcomeAuthView()
        .environmentObject(AuthenticationManager())
}

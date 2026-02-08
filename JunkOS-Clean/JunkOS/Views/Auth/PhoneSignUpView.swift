//
//  PhoneSignUpView.swift
//  JunkOS
//
//  Phone number sign up with country code selection
//

import SwiftUI

struct PhoneSignUpView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @Environment(\.dismiss) var dismiss
    @State private var phoneNumber = ""
    @State private var selectedCountry = Country.unitedStates
    @State private var showVerification = false
    @State private var isLoading = false
    
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
                VStack(spacing: JunkSpacing.normal) {
                    Text("Sign up with your phone")
                        .font(.system(size: 28, weight: .bold))
                        .foregroundColor(.junkText)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, JunkSpacing.large)
                }
                .frame(maxWidth: .infinity)
                .padding(.top, JunkSpacing.xlarge)
                
                // Phone input
                HStack(spacing: JunkSpacing.normal) {
                    // Country code picker
                    Menu {
                        ForEach(Country.popular) { country in
                            Button(action: {
                                selectedCountry = country
                            }) {
                                HStack {
                                    Text(country.flag)
                                    Text(country.name)
                                    Spacer()
                                    Text(country.dialCode)
                                }
                            }
                        }
                    } label: {
                        HStack(spacing: 8) {
                            Text(selectedCountry.flag)
                                .font(.title2)
                            Text(selectedCountry.dialCode)
                                .font(JunkTypography.bodyFont)
                                .foregroundColor(.junkText)
                            Image(systemName: "chevron.down")
                                .font(.caption)
                                .foregroundColor(.junkTextMuted)
                        }
                        .padding(.vertical, JunkSpacing.normal)
                        .padding(.horizontal, JunkSpacing.normal)
                    }
                    
                    // Phone number input
                    TextField("phone number", text: $phoneNumber)
                        .font(JunkTypography.bodyFont)
                        .keyboardType(.phonePad)
                        .autocapitalization(.none)
                        .padding(.vertical, JunkSpacing.normal)
                        .padding(.horizontal, JunkSpacing.normal)
                }
                .overlay(
                    Rectangle()
                        .frame(height: 1)
                        .foregroundColor(.junkBorder),
                    alignment: .bottom
                )
                .padding(.horizontal, JunkSpacing.xlarge)
                
                Spacer()
                
                // Terms and privacy
                VStack(spacing: JunkSpacing.small) {
                    HStack(spacing: 4) {
                        Text("By creating an account you are agreeing to our")
                            .foregroundColor(.junkTextMuted)
                        Button("terms of use") {
                            // Open terms
                        }
                        .foregroundColor(.junkPrimary)
                    }
                    
                    HStack(spacing: 4) {
                        Text("and")
                            .foregroundColor(.junkTextMuted)
                        Button("privacy policy.") {
                            // Open privacy policy
                        }
                        .foregroundColor(.junkPrimary)
                    }
                }
                .font(JunkTypography.bodySmallFont)
                .multilineTextAlignment(.center)
                .padding(.horizontal, JunkSpacing.xlarge)
                
                Text("We will send a verification code to your phone.")
                    .font(JunkTypography.bodySmallFont)
                    .foregroundColor(.junkTextMuted)
                    .multilineTextAlignment(.center)
                
                // Continue button
                Button(action: sendVerificationCode) {
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    } else {
                        Text("Next")
                            .font(JunkTypography.h3Font)
                            .foregroundColor(.white)
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(height: 56)
                .background(isValidPhoneNumber ? Color.junkPrimary : Color.junkTextMuted)
                .cornerRadius(28)
                .disabled(!isValidPhoneNumber || isLoading)
                .padding(.horizontal, JunkSpacing.xlarge)
                .padding(.bottom, JunkSpacing.xlarge)
            }
        }
        .background(Color.junkBackground.ignoresSafeArea())
        .fullScreenCover(isPresented: $showVerification) {
            NavigationView {
                VerificationCodeView(phoneNumber: fullPhoneNumber)
                    .environmentObject(authManager)
            }
        }
    }
    
    // MARK: - Helpers
    
    private var fullPhoneNumber: String {
        "\(selectedCountry.dialCode)\(phoneNumber)"
    }
    
    private var isValidPhoneNumber: Bool {
        phoneNumber.count >= 10
    }
    
    private func sendVerificationCode() {
        isLoading = true
        HapticManager.shared.lightTap()
        
        authManager.sendVerificationCode(to: fullPhoneNumber) { success in
            isLoading = false
            if success {
                HapticManager.shared.success()
                showVerification = true
            } else {
                HapticManager.shared.error()
            }
        }
    }
}

// MARK: - Country Model

struct Country: Identifiable {
    let id = UUID()
    let flag: String
    let name: String
    let dialCode: String
    
    static let unitedStates = Country(flag: "🇺🇸", name: "United States", dialCode: "+1")
    static let canada = Country(flag: "🇨🇦", name: "Canada", dialCode: "+1")
    static let mexico = Country(flag: "🇲🇽", name: "Mexico", dialCode: "+52")
    static let unitedKingdom = Country(flag: "🇬🇧", name: "United Kingdom", dialCode: "+44")
    
    static let popular = [unitedStates, canada, mexico, unitedKingdom]
}

#Preview {
    NavigationView {
        PhoneSignUpView()
            .environmentObject(AuthenticationManager())
    }
}

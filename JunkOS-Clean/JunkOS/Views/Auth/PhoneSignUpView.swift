//
//  PhoneSignUpView.swift
//  Umuve
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
                
                // Header
                VStack(spacing: UmuveSpacing.normal) {
                    Text("Sign up with your phone")
                        .font(.system(size: 28, weight: .bold))
                        .foregroundColor(.umuveText)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, UmuveSpacing.large)
                }
                .frame(maxWidth: .infinity)
                .padding(.top, UmuveSpacing.xlarge)
                
                // Phone input
                HStack(spacing: UmuveSpacing.normal) {
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
                                .font(UmuveTypography.bodyFont)
                                .foregroundColor(.umuveText)
                            Image(systemName: "chevron.down")
                                .font(.caption)
                                .foregroundColor(.umuveTextMuted)
                        }
                        .padding(.vertical, UmuveSpacing.normal)
                        .padding(.horizontal, UmuveSpacing.normal)
                    }
                    
                    // Phone number input
                    TextField("phone number", text: $phoneNumber)
                        .font(UmuveTypography.bodyFont)
                        .keyboardType(.phonePad)
                        .autocapitalization(.none)
                        .padding(.vertical, UmuveSpacing.normal)
                        .padding(.horizontal, UmuveSpacing.normal)
                }
                .overlay(
                    Rectangle()
                        .frame(height: 1)
                        .foregroundColor(.umuveBorder),
                    alignment: .bottom
                )
                .padding(.horizontal, UmuveSpacing.xlarge)
                
                Spacer()
                
                // Terms and privacy
                VStack(spacing: UmuveSpacing.small) {
                    HStack(spacing: 4) {
                        Text("By creating an account you are agreeing to our")
                            .foregroundColor(.umuveTextMuted)
                        Button("terms of use") {
                            // Open terms
                        }
                        .foregroundColor(.umuvePrimary)
                    }
                    
                    HStack(spacing: 4) {
                        Text("and")
                            .foregroundColor(.umuveTextMuted)
                        Button("privacy policy.") {
                            // Open privacy policy
                        }
                        .foregroundColor(.umuvePrimary)
                    }
                }
                .font(UmuveTypography.bodySmallFont)
                .multilineTextAlignment(.center)
                .padding(.horizontal, UmuveSpacing.xlarge)
                
                Text("We will send a verification code to your phone.")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
                    .multilineTextAlignment(.center)
                
                // Continue button
                Button(action: sendVerificationCode) {
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    } else {
                        Text("Next")
                            .font(UmuveTypography.h3Font)
                            .foregroundColor(.white)
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(height: 56)
                .background(isValidPhoneNumber ? Color.umuvePrimary : Color.umuveTextMuted)
                .cornerRadius(28)
                .disabled(!isValidPhoneNumber || isLoading)
                .padding(.horizontal, UmuveSpacing.xlarge)
                .padding(.bottom, UmuveSpacing.xlarge)
            }
        }
        .background(Color.umuveBackground.ignoresSafeArea())
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

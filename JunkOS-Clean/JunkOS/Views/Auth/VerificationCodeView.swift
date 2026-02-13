//
//  VerificationCodeView.swift
//  Umuve
//
//  6-digit SMS verification code entry
//

import SwiftUI

struct VerificationCodeView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @Environment(\.dismiss) var dismiss
    
    let phoneNumber: String
    @State private var code: [String] = Array(repeating: "", count: 6)
    @FocusState private var focusedField: Int?
    @State private var isLoading = false
    @State private var resendCountdown = 0
    @State private var errorMessage: String?
    
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
                    Text("Please enter the\nverification code")
                        .font(.system(size: 28, weight: .bold))
                        .foregroundColor(.umuveText)
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.horizontal, UmuveSpacing.xlarge)
                }
                .frame(maxWidth: .infinity)
                .padding(.top, UmuveSpacing.xlarge)
                
                // Code input boxes
                HStack(spacing: 12) {
                    ForEach(0..<6) { index in
                        CodeDigitField(
                            text: $code[index],
                            isFocused: focusedField == index,
                            onTextChange: { newValue in
                                handleCodeChange(at: index, newValue: newValue)
                            }
                        )
                        .focused($focusedField, equals: index)
                    }
                }
                .padding(.horizontal, UmuveSpacing.large)
                
                // Phone number display
                VStack(spacing: UmuveSpacing.small) {
                    VStack(spacing: 4) {
                        Text("We've just sent a code to")
                            .foregroundColor(.umuveTextMuted)
                        Text(phoneNumber)
                            .foregroundColor(.umuveText)
                            .fontWeight(.semibold)
                    }
                    .font(UmuveTypography.bodyFont)
                    .multilineTextAlignment(.center)
                    
                    Button("Change my number") {
                        dismiss()
                    }
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuvePrimary)
                }
                .frame(maxWidth: .infinity)
                
                // Error message
                if let error = errorMessage {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.red)
                        Text(error)
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.red)
                    }
                    .padding(UmuveSpacing.small)
                    .background(Color.red.opacity(0.1))
                    .cornerRadius(8)
                    .transition(.scale.combined(with: .opacity))
                }
                
                // Resend section
                VStack(spacing: UmuveSpacing.normal) {
                    Text("Didn't receive a code?")
                        .font(UmuveTypography.bodyFont)
                        .fontWeight(.semibold)
                        .foregroundColor(.umuveText)
                    
                    Text("Check the phone number above is correct")
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveTextMuted)
                        .multilineTextAlignment(.center)
                    
                    if resendCountdown > 0 {
                        Text("Please Resend (\(resendCountdown)s)")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveTextMuted)
                    } else {
                        Button("Please Resend") {
                            resendCode()
                        }
                        .font(UmuveTypography.bodyFont)
                        .fontWeight(.semibold)
                        .foregroundColor(.umuvePrimary)
                    }
                }
                .frame(maxWidth: .infinity)
                .multilineTextAlignment(.center)
                .padding(.horizontal, UmuveSpacing.large)
                
                Spacer()
                
                // Continue button
                Button(action: verifyCode) {
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
                .background(isCodeComplete ? Color.umuvePrimary : Color.umuveTextMuted)
                .cornerRadius(28)
                .disabled(!isCodeComplete || isLoading)
                .padding(.horizontal, UmuveSpacing.xlarge)
                .padding(.bottom, UmuveSpacing.xlarge)
            }
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .onAppear {
            focusedField = 0
            startResendTimer()
        }
    }
    
    // MARK: - Helpers
    
    private var isCodeComplete: Bool {
        code.allSatisfy { !$0.isEmpty }
    }
    
    private var fullCode: String {
        code.joined()
    }
    
    private func handleCodeChange(at index: Int, newValue: String) {
        // Only allow digits
        let filtered = newValue.filter { $0.isNumber }
        
        if filtered.isEmpty {
            code[index] = ""
            // Move back on delete
            if index > 0 {
                focusedField = index - 1
            }
        } else {
            code[index] = String(filtered.prefix(1))
            // Auto-advance to next field
            if index < 5 {
                focusedField = index + 1
            } else {
                // Last digit entered, auto-submit
                focusedField = nil
                if isCodeComplete {
                    verifyCode()
                }
            }
        }
    }
    
    private func verifyCode() {
        isLoading = true
        errorMessage = nil
        HapticManager.shared.lightTap()
        
        authManager.verifyCode(fullCode, for: phoneNumber) { success, error in
            isLoading = false
            if success {
                HapticManager.shared.success()
                dismiss()
            } else {
                HapticManager.shared.error()
                errorMessage = error ?? "Invalid code. Please try again."
                // Clear code
                code = Array(repeating: "", count: 6)
                focusedField = 0
            }
        }
    }
    
    private func resendCode() {
        authManager.sendVerificationCode(to: phoneNumber) { success in
            if success {
                HapticManager.shared.success()
                startResendTimer()
            } else {
                HapticManager.shared.error()
            }
        }
    }
    
    private func startResendTimer() {
        resendCountdown = 120 // 2 minutes
        Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { timer in
            if resendCountdown > 0 {
                resendCountdown -= 1
            } else {
                timer.invalidate()
            }
        }
    }
}

// MARK: - Code Digit Field

struct CodeDigitField: View {
    @Binding var text: String
    let isFocused: Bool
    let onTextChange: (String) -> Void
    
    var body: some View {
        TextField("", text: Binding(
            get: { text },
            set: { onTextChange($0) }
        ))
        .font(.system(size: 32, weight: .medium))
        .foregroundColor(.umuveText)
        .multilineTextAlignment(.center)
        .keyboardType(.numberPad)
        .frame(width: 48, height: 64)
        .background(Color.white)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(
                    isFocused ? Color.umuvePrimary : Color.umuveBorder,
                    lineWidth: isFocused ? 2 : 1
                )
        )
    }
}

#Preview {
    NavigationView {
        VerificationCodeView(phoneNumber: "+15618883427")
            .environmentObject(AuthenticationManager())
    }
}

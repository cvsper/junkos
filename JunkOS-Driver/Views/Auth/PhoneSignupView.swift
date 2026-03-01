//
//  PhoneSignupView.swift
//  Umuve Pro
//
//  Phone number signup with SMS verification.
//  Two-step flow: enter phone → verify code.
//

import SwiftUI

struct PhoneSignupView: View {
    @Bindable var appState: AppState
    let onDismiss: () -> Void
    @State private var phoneNumber = ""
    @State private var verificationCode = ""
    @State private var codeSent = false

    var body: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            VStack(spacing: 0) {
                // Header
                HStack {
                    Button {
                        if codeSent {
                            codeSent = false
                            verificationCode = ""
                        } else {
                            onDismiss()
                        }
                    } label: {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 20, weight: .medium))
                            .foregroundStyle(Color.driverText)
                    }

                    Spacer()
                }
                .padding(.horizontal, DriverSpacing.lg)
                .padding(.top, DriverSpacing.md)
                .frame(height: 44)

                Spacer()

                // Content
                if !codeSent {
                    phoneEntryView
                } else {
                    codeVerificationView
                }

                Spacer()
            }

            // Loading overlay
            if appState.auth.isLoading {
                Color.black.opacity(0.3)
                    .ignoresSafeArea()
                ProgressView()
                    .tint(.white)
                    .scaleEffect(x: 1.5, y: 1.5)
            }
        }
        .preferredColorScheme(.light)
    }

    // MARK: - Phone Entry

    private var phoneEntryView: some View {
        VStack(spacing: DriverSpacing.xl) {
            VStack(spacing: DriverSpacing.md) {
                Image(systemName: "phone.fill")
                    .font(.system(size: 48))
                    .foregroundStyle(Color.driverPrimary)

                Text("Enter Your Phone Number")
                    .font(DriverTypography.title)
                    .foregroundStyle(Color.driverText)

                Text("We'll send you a verification code")
                    .font(DriverTypography.body)
                    .foregroundStyle(Color.driverTextSecondary)
                    .multilineTextAlignment(.center)
            }

            VStack(spacing: DriverSpacing.md) {
                // Phone number input
                TextField("Phone Number", text: $phoneNumber)
                    .keyboardType(.phonePad)
                    .textContentType(.telephoneNumber)
                    .font(DriverTypography.body)
                    .padding(DriverSpacing.md)
                    .background(Color.driverSurface)
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                    .overlay {
                        RoundedRectangle(cornerRadius: DriverRadius.md)
                            .stroke(Color.driverBorder, lineWidth: 1)
                    }

                Button {
                    Task {
                        await appState.auth.sendVerificationCode(phoneNumber: phoneNumber)
                        if appState.auth.errorMessage == nil {
                            codeSent = true
                        }
                    }
                } label: {
                    Text("Send Code")
                        .font(DriverTypography.headline)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 52)
                        .background(phoneNumber.count >= 10 ? Color.driverPrimary : Color.driverTextSecondary.opacity(0.3))
                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                }
                .disabled(phoneNumber.count < 10 || appState.auth.isLoading)

                // Error message
                if let errorMessage = appState.auth.errorMessage {
                    Text(errorMessage)
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverError)
                        .multilineTextAlignment(.center)
                }
            }
            .padding(.horizontal, DriverSpacing.xl)
        }
    }

    // MARK: - Code Verification

    private var codeVerificationView: some View {
        VStack(spacing: DriverSpacing.xl) {
            VStack(spacing: DriverSpacing.md) {
                Image(systemName: "message.fill")
                    .font(.system(size: 48))
                    .foregroundStyle(Color.driverPrimary)

                Text("Enter Verification Code")
                    .font(DriverTypography.title)
                    .foregroundStyle(Color.driverText)

                Text("Sent to \(phoneNumber)")
                    .font(DriverTypography.body)
                    .foregroundStyle(Color.driverTextSecondary)
                    .multilineTextAlignment(.center)
            }

            VStack(spacing: DriverSpacing.md) {
                // Verification code input
                TextField("6-digit code", text: $verificationCode)
                    .keyboardType(.numberPad)
                    .textContentType(.oneTimeCode)
                    .font(DriverTypography.largeTitle)
                    .multilineTextAlignment(.center)
                    .padding(DriverSpacing.md)
                    .background(Color.driverSurface)
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                    .overlay {
                        RoundedRectangle(cornerRadius: DriverRadius.md)
                            .stroke(Color.driverBorder, lineWidth: 1)
                    }

                Button {
                    Task {
                        await appState.auth.verifyCode(phoneNumber: phoneNumber, code: verificationCode)
                    }
                } label: {
                    Text("Verify & Sign Up")
                        .font(DriverTypography.headline)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 52)
                        .background(verificationCode.count == 6 ? Color.driverPrimary : Color.driverTextSecondary.opacity(0.3))
                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                }
                .disabled(verificationCode.count != 6 || appState.auth.isLoading)

                // Resend button
                Button {
                    Task {
                        appState.auth.errorMessage = nil
                        await appState.auth.sendVerificationCode(phoneNumber: phoneNumber)
                    }
                } label: {
                    Text("Resend Code")
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverPrimary)
                }
                .disabled(appState.auth.isLoading)
                .padding(.top, DriverSpacing.sm)

                // Error message
                if let errorMessage = appState.auth.errorMessage {
                    Text(errorMessage)
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverError)
                        .multilineTextAlignment(.center)
                }
            }
            .padding(.horizontal, DriverSpacing.xl)
        }
    }
}

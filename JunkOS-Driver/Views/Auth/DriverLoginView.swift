//
//  DriverLoginView.swift
//  JunkOS Driver
//
//  Email/password login form.
//

import SwiftUI

struct DriverLoginView: View {
    @Bindable var appState: AppState
    @State private var viewModel = AuthViewModel()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            ScrollView {
                VStack(spacing: DriverSpacing.xl) {
                    // Header
                    VStack(spacing: DriverSpacing.xs) {
                        Text("Welcome Back")
                            .font(DriverTypography.title)
                            .foregroundStyle(Color.driverText)

                        Text("Sign in to your driver account")
                            .font(DriverTypography.body)
                            .foregroundStyle(Color.driverTextSecondary)
                    }
                    .padding(.top, DriverSpacing.xxl)

                    // Form
                    VStack(spacing: DriverSpacing.md) {
                        VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                            TextField("Email", text: $viewModel.email)
                                .textFieldStyle(DriverTextFieldStyle())
                                .textContentType(.emailAddress)
                                .keyboardType(.emailAddress)
                                .autocorrectionDisabled()
                                .textInputAutocapitalization(.never)

                            if let error = viewModel.emailError {
                                Text(error)
                                    .font(DriverTypography.caption)
                                    .foregroundStyle(Color.driverError)
                            }
                        }

                        VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                            SecureField("Password", text: $viewModel.password)
                                .textFieldStyle(DriverTextFieldStyle())
                                .textContentType(.password)

                            if let error = viewModel.passwordError {
                                Text(error)
                                    .font(DriverTypography.caption)
                                    .foregroundStyle(Color.driverError)
                            }
                        }
                    }

                    // Error message
                    if let error = appState.auth.errorMessage {
                        Text(error)
                            .font(DriverTypography.footnote)
                            .foregroundStyle(Color.driverError)
                            .multilineTextAlignment(.center)
                    }

                    // Sign in button
                    Button {
                        guard viewModel.validate() else { return }
                        Task {
                            await appState.auth.login(
                                email: viewModel.email,
                                password: viewModel.password
                            )
                        }
                    } label: {
                        if appState.auth.isLoading {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Text("Sign In")
                        }
                    }
                    .buttonStyle(DriverPrimaryButtonStyle(isEnabled: viewModel.isFormValid))
                    .disabled(!viewModel.isFormValid || appState.auth.isLoading)
                }
                .padding(.horizontal, DriverSpacing.xl)
            }
        }
        .navigationBarTitleDisplayMode(.inline)
    }
}

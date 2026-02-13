//
//  DriverSignupView.swift
//  Umuve Pro
//
//  Create account form.
//

import SwiftUI

struct DriverSignupView: View {
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
                        Text("Create Account")
                            .font(DriverTypography.title)
                            .foregroundStyle(Color.driverText)

                        Text("Start earning with Umuve")
                            .font(DriverTypography.body)
                            .foregroundStyle(Color.driverTextSecondary)
                    }
                    .padding(.top, DriverSpacing.xxl)

                    // Form
                    VStack(spacing: DriverSpacing.md) {
                        TextField("Full Name", text: $viewModel.name)
                            .textFieldStyle(DriverTextFieldStyle())
                            .textContentType(.name)

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
                            SecureField("Password (6+ characters)", text: $viewModel.password)
                                .textFieldStyle(DriverTextFieldStyle())
                                .textContentType(.newPassword)

                            if let error = viewModel.passwordError {
                                Text(error)
                                    .font(DriverTypography.caption)
                                    .foregroundStyle(Color.driverError)
                            }
                        }
                    }

                    if let error = appState.auth.errorMessage {
                        Text(error)
                            .font(DriverTypography.footnote)
                            .foregroundStyle(Color.driverError)
                            .multilineTextAlignment(.center)
                    }

                    Button {
                        guard viewModel.validate() else { return }
                        Task {
                            await appState.auth.signup(
                                email: viewModel.email,
                                password: viewModel.password,
                                name: viewModel.name.isEmpty ? nil : viewModel.name
                            )
                        }
                    } label: {
                        if appState.auth.isLoading {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Text("Create Account")
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

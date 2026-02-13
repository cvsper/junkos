//
//  PayoutSettingsView.swift
//  Umuve Pro
//
//  Payout method management — bank account details for driver payouts.
//

import SwiftUI

struct PayoutSettingsView: View {
    @Bindable var appState: AppState
    @State private var accountHolderName = ""
    @State private var routingNumber = ""
    @State private var accountNumber = ""
    @State private var confirmAccountNumber = ""
    @State private var accountType: AccountType = .checking
    @State private var isSaving = false
    @State private var showSuccess = false
    @State private var errorMessage: String?

    private var hasExistingPayout: Bool {
        appState.contractorProfile?.stripeConnectId != nil
    }

    private var isFormValid: Bool {
        !accountHolderName.isEmpty &&
        routingNumber.count == 9 &&
        accountNumber.count >= 4 &&
        accountNumber == confirmAccountNumber
    }

    enum AccountType: String, CaseIterable {
        case checking = "Checking"
        case savings = "Savings"
    }

    var body: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            ScrollView {
                VStack(spacing: DriverSpacing.lg) {
                    // Current payout status
                    PayoutStatusCard(isSetUp: hasExistingPayout)
                        .padding(.horizontal, DriverSpacing.xl)

                    // Bank account form
                    VStack(alignment: .leading, spacing: DriverSpacing.md) {
                        Text(hasExistingPayout ? "Update Bank Account" : "Add Bank Account")
                            .font(DriverTypography.title3)
                            .foregroundStyle(Color.driverText)

                        Text("Your earnings will be deposited directly into this account.")
                            .font(DriverTypography.footnote)
                            .foregroundStyle(Color.driverTextSecondary)

                        // Account holder name
                        VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                            Text("Account Holder Name")
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverTextSecondary)

                            TextField("Full legal name", text: $accountHolderName)
                                .textFieldStyle(DriverTextFieldStyle())
                                .textContentType(.name)
                        }

                        // Account type
                        VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                            Text("Account Type")
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverTextSecondary)

                            Picker("Account Type", selection: $accountType) {
                                ForEach(AccountType.allCases, id: \.self) { type in
                                    Text(type.rawValue).tag(type)
                                }
                            }
                            .pickerStyle(.segmented)
                        }

                        // Routing number
                        VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                            Text("Routing Number")
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverTextSecondary)

                            TextField("9-digit routing number", text: $routingNumber)
                                .textFieldStyle(DriverTextFieldStyle())
                                .keyboardType(.numberPad)
                                .onChange(of: routingNumber) { _, newValue in
                                    routingNumber = String(newValue.prefix(9).filter(\.isNumber))
                                }

                            if !routingNumber.isEmpty && routingNumber.count != 9 {
                                Text("Must be 9 digits")
                                    .font(DriverTypography.caption2)
                                    .foregroundStyle(Color.driverError)
                            }
                        }

                        // Account number
                        VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                            Text("Account Number")
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverTextSecondary)

                            SecureField("Account number", text: $accountNumber)
                                .textFieldStyle(DriverTextFieldStyle())
                                .keyboardType(.numberPad)
                        }

                        // Confirm account number
                        VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                            Text("Confirm Account Number")
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverTextSecondary)

                            SecureField("Re-enter account number", text: $confirmAccountNumber)
                                .textFieldStyle(DriverTextFieldStyle())
                                .keyboardType(.numberPad)

                            if !confirmAccountNumber.isEmpty && accountNumber != confirmAccountNumber {
                                Text("Account numbers don't match")
                                    .font(DriverTypography.caption2)
                                    .foregroundStyle(Color.driverError)
                            }
                        }
                    }
                    .driverCard()
                    .padding(.horizontal, DriverSpacing.xl)

                    // Error
                    if let error = errorMessage {
                        Text(error)
                            .font(DriverTypography.footnote)
                            .foregroundStyle(Color.driverError)
                            .padding(.horizontal, DriverSpacing.xl)
                    }

                    // Save button
                    Button {
                        savePayout()
                    } label: {
                        if isSaving {
                            ProgressView().tint(.white)
                        } else {
                            Text(hasExistingPayout ? "Update Payout Method" : "Save Payout Method")
                        }
                    }
                    .buttonStyle(DriverPrimaryButtonStyle(isEnabled: isFormValid))
                    .disabled(!isFormValid || isSaving)
                    .padding(.horizontal, DriverSpacing.xl)

                    // Security note
                    HStack(spacing: DriverSpacing.xs) {
                        Image(systemName: "lock.shield.fill")
                            .font(.system(size: 14))
                            .foregroundStyle(Color.driverPrimary)

                        Text("Your banking information is encrypted and securely transmitted via Stripe.")
                            .font(DriverTypography.caption2)
                            .foregroundStyle(Color.driverTextTertiary)
                    }
                    .padding(.horizontal, DriverSpacing.xl)
                }
                .padding(.top, DriverSpacing.md)
                .padding(.bottom, DriverSpacing.xxxl)
            }
        }
        .navigationTitle("Payout Method")
        .navigationBarTitleDisplayMode(.inline)
        .alert("Payout Method Saved", isPresented: $showSuccess) {
            Button("OK") {}
        } message: {
            Text("Your bank account has been saved. Earnings will be deposited after each completed job.")
        }
    }

    private func savePayout() {
        isSaving = true
        errorMessage = nil

        // In production this would call Stripe Connect onboarding API
        // For now, simulate success
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            isSaving = false
            showSuccess = true
            HapticManager.shared.success()
        }
    }
}

// MARK: - Payout Status Card

private struct PayoutStatusCard: View {
    let isSetUp: Bool

    var body: some View {
        HStack(spacing: DriverSpacing.md) {
            ZStack {
                Circle()
                    .fill(isSetUp ? Color.driverSuccess.opacity(0.15) : Color.driverWarning.opacity(0.15))
                    .frame(width: 48, height: 48)

                Image(systemName: isSetUp ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                    .font(.system(size: 22))
                    .foregroundStyle(isSetUp ? Color.driverSuccess : Color.driverWarning)
            }

            VStack(alignment: .leading, spacing: DriverSpacing.xxxs) {
                Text(isSetUp ? "Payout Active" : "Payout Not Set Up")
                    .font(DriverTypography.headline)
                    .foregroundStyle(Color.driverText)

                Text(isSetUp
                     ? "Your earnings are deposited automatically."
                     : "Add a bank account to receive your earnings.")
                    .font(DriverTypography.caption)
                    .foregroundStyle(Color.driverTextSecondary)
            }

            Spacer()
        }
        .driverCard()
    }
}

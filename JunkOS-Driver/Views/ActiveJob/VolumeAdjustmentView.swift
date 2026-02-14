//
//  VolumeAdjustmentView.swift
//  Umuve Pro
//
//  Volume input UI with price preview and real-time approval/decline response.
//

import SwiftUI

struct VolumeAdjustmentView: View {
    let jobId: String
    let originalEstimate: Double?

    @State private var viewModel = VolumeAdjustmentViewModel()

    var body: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            ScrollView {
                VStack(spacing: DriverSpacing.xl) {
                    // Header
                    VStack(spacing: DriverSpacing.xs) {
                        Text("Adjust Volume")
                            .font(DriverTypography.title2)
                            .foregroundStyle(Color.driverText)

                        Text("Enter the actual volume measured on-site")
                            .font(DriverTypography.subheadline)
                            .foregroundStyle(Color.driverTextSecondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top, DriverSpacing.md)

                    // Current estimate display
                    if let estimate = originalEstimate {
                        VStack(alignment: .leading, spacing: DriverSpacing.xs) {
                            Text("Original Estimate")
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverTextSecondary)

                            Text(String(format: "%.1f cu yd", estimate))
                                .font(DriverTypography.title3)
                                .foregroundStyle(Color.driverText)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(DriverSpacing.md)
                        .background(Color.driverSurface)
                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                        .overlay(
                            RoundedRectangle(cornerRadius: DriverRadius.md)
                                .stroke(Color.driverBorder, lineWidth: 1)
                        )
                    }

                    // Volume input
                    VStack(alignment: .leading, spacing: DriverSpacing.xs) {
                        Text("Actual Volume (cu yd)")
                            .font(DriverTypography.caption)
                            .foregroundStyle(Color.driverTextSecondary)

                        TextField("0.0", text: $viewModel.volumeInput)
                            .keyboardType(.decimalPad)
                            .font(DriverTypography.title)
                            .foregroundStyle(Color.driverText)
                            .padding(DriverSpacing.md)
                            .background(Color.white)
                            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                            .overlay(
                                RoundedRectangle(cornerRadius: DriverRadius.md)
                                    .stroke(Color.driverBorder, lineWidth: 1)
                            )
                            .onChange(of: viewModel.volumeInput) { oldValue, newValue in
                                // Filter input: only allow digits and single decimal point
                                let filtered = newValue.filter { $0.isNumber || $0 == "." }
                                let decimalCount = filtered.filter { $0 == "." }.count
                                if decimalCount > 1 {
                                    viewModel.volumeInput = oldValue
                                } else if filtered != newValue {
                                    viewModel.volumeInput = filtered
                                } else {
                                    // Limit to 1 decimal place
                                    if let decimalIndex = filtered.firstIndex(of: ".") {
                                        let afterDecimal = filtered[filtered.index(after: decimalIndex)...]
                                        if afterDecimal.count > 1 {
                                            viewModel.volumeInput = oldValue
                                        }
                                    }
                                }
                            }
                    }

                    // Price comparison (if new price calculated)
                    if let newPrice = viewModel.newPrice,
                       let originalPrice = viewModel.originalPrice {
                        VStack(spacing: DriverSpacing.sm) {
                            Text("Price Adjustment")
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverTextSecondary)

                            HStack(spacing: DriverSpacing.md) {
                                // Original price
                                VStack(spacing: DriverSpacing.xxs) {
                                    Text("Original")
                                        .font(DriverTypography.caption2)
                                        .foregroundStyle(Color.driverTextSecondary)

                                    Text(String(format: "$%.0f", originalPrice))
                                        .font(DriverTypography.priceSmall)
                                        .foregroundStyle(Color.driverText)
                                }

                                // Arrow
                                Image(systemName: "arrow.right")
                                    .font(.system(size: 20))
                                    .foregroundStyle(Color.driverTextSecondary)

                                // New price
                                VStack(spacing: DriverSpacing.xxs) {
                                    Text("New")
                                        .font(DriverTypography.caption2)
                                        .foregroundStyle(Color.driverTextSecondary)

                                    Text(String(format: "$%.0f", newPrice))
                                        .font(DriverTypography.priceSmall)
                                        .foregroundStyle(
                                            newPrice < originalPrice ? Color.driverSuccess : Color.driverPrimary
                                        )
                                }
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(DriverSpacing.md)
                        .background(Color.driverSurface)
                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                        .overlay(
                            RoundedRectangle(cornerRadius: DriverRadius.md)
                                .stroke(Color.driverBorder, lineWidth: 1)
                        )
                    }

                    // Error message
                    if let error = viewModel.errorMessage {
                        Text(error)
                            .font(DriverTypography.footnote)
                            .foregroundStyle(Color.driverError)
                            .multilineTextAlignment(.center)
                    }

                    // Submit button
                    Button(action: {
                        Task {
                            await viewModel.proposeAdjustment(jobId: jobId)
                        }
                    }) {
                        if viewModel.isSubmitting {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Text("Submit Adjustment")
                        }
                    }
                    .buttonStyle(DriverPrimaryButtonStyle(isEnabled: viewModel.isValid && !viewModel.isSubmitting))
                    .disabled(!viewModel.isValid || viewModel.isSubmitting)
                }
                .padding(.horizontal, DriverSpacing.xl)
                .padding(.bottom, DriverSpacing.xxl)
            }

            // Waiting for approval overlay
            if viewModel.isWaitingForApproval {
                ZStack {
                    Color.black.opacity(0.6)
                        .ignoresSafeArea()

                    VStack(spacing: DriverSpacing.md) {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(1.5)

                        Text("Waiting for customer approval...")
                            .font(DriverTypography.headline)
                            .foregroundStyle(.white)
                            .multilineTextAlignment(.center)
                    }
                    .padding(DriverSpacing.xxl)
                    .background(Color.driverPrimary)
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
                }
            }

            // Success overlay (approved)
            if let approved = viewModel.wasApproved, approved {
                ZStack {
                    Color.black.opacity(0.6)
                        .ignoresSafeArea()

                    VStack(spacing: DriverSpacing.md) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 64))
                            .foregroundStyle(Color.driverSuccess)

                        Text(viewModel.autoApproved ? "Auto-Approved" : "Customer Approved")
                            .font(DriverTypography.title2)
                            .foregroundStyle(.white)

                        if viewModel.autoApproved {
                            Text("Price Decreased")
                                .font(DriverTypography.subheadline)
                                .foregroundStyle(.white.opacity(0.8))
                        }
                    }
                    .padding(DriverSpacing.xxl)
                    .background(Color.driverSuccess.opacity(0.9))
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
                }
            }

            // Decline overlay
            if let approved = viewModel.wasApproved, !approved {
                ZStack {
                    Color.black.opacity(0.6)
                        .ignoresSafeArea()

                    VStack(spacing: DriverSpacing.md) {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 64))
                            .foregroundStyle(Color.driverError)

                        Text("Customer Declined")
                            .font(DriverTypography.title2)
                            .foregroundStyle(.white)

                        if let tripFee = viewModel.tripFee {
                            Text(String(format: "Trip fee: $%.2f", tripFee))
                                .font(DriverTypography.headline)
                                .foregroundStyle(.white.opacity(0.9))
                        }
                    }
                    .padding(DriverSpacing.xxl)
                    .background(Color.driverError.opacity(0.9))
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
                }
            }
        }
        .navigationTitle("Adjust Volume")
        .navigationBarTitleDisplayMode(.inline)
    }
}

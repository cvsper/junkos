//
//  ContractorRegistrationView.swift
//  JunkOS Driver
//
//  Multi-step contractor registration: Truck Type → License → Insurance.
//

import SwiftUI

struct ContractorRegistrationView: View {
    @Bindable var appState: AppState
    @State private var viewModel = RegistrationViewModel()
    @State private var showCamera = false

    var body: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            VStack(spacing: 0) {
                // Progress bar
                ProgressView(value: Double(viewModel.currentStep + 1), total: Double(viewModel.totalSteps))
                    .tint(Color.driverPrimary)
                    .padding(.horizontal, DriverSpacing.xl)
                    .padding(.top, DriverSpacing.md)

                // Step indicator
                Text("Step \(viewModel.currentStep + 1) of \(viewModel.totalSteps)")
                    .font(DriverTypography.caption)
                    .foregroundStyle(Color.driverTextSecondary)
                    .padding(.top, DriverSpacing.xs)

                // Header
                VStack(spacing: DriverSpacing.xs) {
                    Text(viewModel.stepTitle)
                        .font(DriverTypography.title2)
                        .foregroundStyle(Color.driverText)

                    Text(viewModel.stepSubtitle)
                        .font(DriverTypography.body)
                        .foregroundStyle(Color.driverTextSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, DriverSpacing.xl)
                .padding(.top, DriverSpacing.lg)

                Spacer()

                // Step content
                Group {
                    switch viewModel.currentStep {
                    case 0:
                        InviteCodeStepView(viewModel: viewModel)
                    case 1:
                        TruckTypeSelectionView(selectedType: $viewModel.selectedTruckType)
                    case 2:
                        DocumentUploadView(
                            title: "Driver's License",
                            image: $viewModel.licenseImage,
                            showCamera: $showCamera
                        )
                    case 3:
                        DocumentUploadView(
                            title: "Insurance Document",
                            image: $viewModel.insuranceImage,
                            showCamera: $showCamera
                        )
                    default:
                        EmptyView()
                    }
                }
                .transition(.asymmetric(
                    insertion: .move(edge: .trailing).combined(with: .opacity),
                    removal: .move(edge: .leading).combined(with: .opacity)
                ))
                .animation(AnimationConstants.smoothSpring, value: viewModel.currentStep)

                Spacer()

                // Error
                if let error = viewModel.errorMessage {
                    Text(error)
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverError)
                        .padding(.horizontal, DriverSpacing.xl)
                }

                // Navigation buttons
                HStack(spacing: DriverSpacing.sm) {
                    if viewModel.currentStep > 0 {
                        Button("Back") {
                            viewModel.previousStep()
                        }
                        .buttonStyle(DriverSecondaryButtonStyle())
                    }

                    Button {
                        if viewModel.currentStep < viewModel.totalSteps - 1 {
                            viewModel.nextStep()
                        } else {
                            Task {
                                await viewModel.submit()
                                if viewModel.isComplete {
                                    await appState.loadContractorProfile()
                                }
                            }
                        }
                    } label: {
                        if viewModel.isLoading {
                            ProgressView().tint(.white)
                        } else {
                            Text(viewModel.currentStep < viewModel.totalSteps - 1 ? "Continue" : "Submit")
                        }
                    }
                    .buttonStyle(DriverPrimaryButtonStyle(isEnabled: viewModel.canProceed))
                    .disabled(!viewModel.canProceed || viewModel.isLoading)
                }
                .padding(.horizontal, DriverSpacing.xl)
                .padding(.bottom, DriverSpacing.xxl)
            }
        }
        .sheet(isPresented: $showCamera) {
            CameraPickerView { image in
                if viewModel.currentStep == 2 {
                    viewModel.licenseImage = image
                } else if viewModel.currentStep == 3 {
                    viewModel.insuranceImage = image
                }
            }
        }
    }
}

//
//  BeforePhotosView.swift
//  JunkOS Driver
//
//  Camera capture for "before" photos + Mark Started button.
//

import SwiftUI

struct BeforePhotosView: View {
    @Bindable var viewModel: ActiveJobViewModel
    @State private var showCamera = false

    var body: some View {
        VStack(spacing: DriverSpacing.lg) {
            Spacer()

            // Instructions
            VStack(spacing: DriverSpacing.xs) {
                Image(systemName: "camera.fill")
                    .font(.system(size: 40))
                    .foregroundStyle(Color.driverPrimary)

                Text("Before Photos")
                    .font(DriverTypography.title3)
                    .foregroundStyle(Color.driverText)

                Text("Take photos of the items before starting removal")
                    .font(DriverTypography.footnote)
                    .foregroundStyle(Color.driverTextSecondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal, DriverSpacing.xl)

            // Photo grid
            if !viewModel.beforePhotos.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: DriverSpacing.sm) {
                        ForEach(viewModel.beforePhotos.indices, id: \.self) { index in
                            Image(uiImage: viewModel.beforePhotos[index])
                                .resizable()
                                .scaledToFill()
                                .frame(width: 100, height: 100)
                                .clipShape(RoundedRectangle(cornerRadius: DriverRadius.sm))
                        }

                        // Add more
                        Button {
                            showCamera = true
                        } label: {
                            VStack {
                                Image(systemName: "plus")
                                    .font(.system(size: 24))
                                    .foregroundStyle(Color.driverPrimary)
                            }
                            .frame(width: 100, height: 100)
                            .background(
                                RoundedRectangle(cornerRadius: DriverRadius.sm)
                                    .strokeBorder(Color.driverPrimary, style: StrokeStyle(lineWidth: 2, dash: [6]))
                            )
                        }
                    }
                    .padding(.horizontal, DriverSpacing.xl)
                }
            } else {
                Button {
                    showCamera = true
                } label: {
                    VStack(spacing: DriverSpacing.sm) {
                        Image(systemName: "camera.badge.ellipsis")
                            .font(.system(size: 32))
                        Text("Take Photo")
                            .font(DriverTypography.headline)
                    }
                    .foregroundStyle(Color.driverPrimary)
                    .frame(maxWidth: .infinity)
                    .frame(height: 140)
                    .background(
                        RoundedRectangle(cornerRadius: DriverRadius.lg)
                            .strokeBorder(Color.driverPrimary, style: StrokeStyle(lineWidth: 2, dash: [8]))
                            .background(RoundedRectangle(cornerRadius: DriverRadius.lg).fill(Color.driverPrimary.opacity(0.05)))
                    )
                }
                .buttonStyle(.plain)
                .padding(.horizontal, DriverSpacing.xl)
            }

            Spacer()

            // Mark Started
            Button {
                Task { await viewModel.markStarted() }
            } label: {
                if viewModel.isUpdating {
                    ProgressView().tint(.white)
                } else {
                    Text("Start Job")
                }
            }
            .buttonStyle(DriverPrimaryButtonStyle(isEnabled: !viewModel.beforePhotos.isEmpty))
            .disabled(viewModel.beforePhotos.isEmpty || viewModel.isUpdating)
            .padding(.horizontal, DriverSpacing.xl)
            .padding(.bottom, DriverSpacing.xxl)
        }
        .sheet(isPresented: $showCamera) {
            CameraPickerView { image in
                viewModel.beforePhotos.append(image)
            }
        }
    }
}

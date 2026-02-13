//
//  DocumentUploadView.swift
//  Umuve Pro
//
//  Photo upload for license and insurance documents.
//

import SwiftUI

struct DocumentUploadView: View {
    let title: String
    @Binding var image: UIImage?
    @Binding var showCamera: Bool

    var body: some View {
        VStack(spacing: DriverSpacing.lg) {
            if let image {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()
                    .frame(maxHeight: 260)
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
                    .overlay(
                        RoundedRectangle(cornerRadius: DriverRadius.lg)
                            .stroke(Color.driverPrimary, lineWidth: 2)
                    )
                    .shadow(color: .black.opacity(0.1), radius: 8, y: 4)

                Button("Retake Photo") {
                    showCamera = true
                }
                .font(DriverTypography.subheadline)
                .foregroundStyle(Color.driverPrimary)
            } else {
                Button {
                    showCamera = true
                } label: {
                    VStack(spacing: DriverSpacing.md) {
                        Image(systemName: "camera.fill")
                            .font(.system(size: 40))
                            .foregroundStyle(Color.driverPrimary)

                        Text("Take a Photo")
                            .font(DriverTypography.headline)
                            .foregroundStyle(Color.driverText)

                        Text("Make sure all details are clearly visible")
                            .font(DriverTypography.footnote)
                            .foregroundStyle(Color.driverTextSecondary)
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 200)
                    .background(
                        RoundedRectangle(cornerRadius: DriverRadius.lg)
                            .strokeBorder(Color.driverPrimary, style: StrokeStyle(lineWidth: 2, dash: [8]))
                            .background(
                                RoundedRectangle(cornerRadius: DriverRadius.lg)
                                    .fill(Color.driverPrimary.opacity(0.05))
                            )
                    )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, DriverSpacing.xl)
    }
}

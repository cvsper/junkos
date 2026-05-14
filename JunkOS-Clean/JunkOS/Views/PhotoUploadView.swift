//
//  PhotoUploadView.swift
//  Umuve
//
//  Photo upload screen with gallery
//  Enhanced with photo entrance animations and deletion haptics
//  SF Symbols Reference: https://developer.apple.com/sf-symbols/
//

import SwiftUI
import PhotosUI
import UIKit

struct PhotoUploadView: View {
    @EnvironmentObject var bookingData: BookingData
    @EnvironmentObject var wizardVM: BookingWizardViewModel
    @StateObject private var viewModel = PhotoUploadViewModel()
    @State private var showCamera = false

    var body: some View {
        ScrollView {
            VStack(spacing: UmuveSpacing.xxlarge) {
                // Header — web parity copy
                VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                    Text("Upload Photos")
                        .font(UmuveTypography.h1Font)
                        .foregroundColor(.umuveText)

                    Text("Show us what needs to go. This helps us give you an accurate estimate.")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, UmuveSpacing.normal)

                // Encouragement message when no photos
                if bookingData.photos.isEmpty {
                    encouragementMessage
                }

                // Photo grid or empty state
                if bookingData.photos.isEmpty {
                    emptyState
                } else {
                    photoGrid
                }

                // Action buttons
                actionButtons

                // Tip box
                tipBox

                Spacer()
            }
            .padding(UmuveSpacing.large)
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .sheet(isPresented: $showCamera) {
            CameraPicker { photoData in
                bookingData.photos.append(photoData)
            }
            .ignoresSafeArea()
        }
        .safeAreaInset(edge: .bottom) {
            continueButton
        }
        .onAppear {
            viewModel.startAnimations()
        }
    }
    
    // MARK: - Encouragement Message
    private var encouragementMessage: some View {
        HStack(alignment: .top, spacing: UmuveSpacing.normal) {
            ZStack {
                RoundedRectangle(cornerRadius: UmuveRadius.sm)
                    .fill(Color.categoryBlue.opacity(0.18))
                    .frame(width: 40, height: 40)

                Image(systemName: "info.circle.fill")
                    .font(.system(size: 20))
                    .foregroundColor(.categoryBlue)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Skip this step? You can.")
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)

                Text("Upload 1–2 photos to help us prep the right truck. You can also add items manually on the next step.")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 0)
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuveBorder, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 4)
    }

    // MARK: - Empty State
    private var emptyState: some View {
        PhotoUploadEmptyState {
            // Empty tap action - actual photo selection happens via buttons below
        }
        .accessibilityHint("Add photos using the buttons below")
    }
    
    // MARK: - Photo Grid
    private var photoGrid: some View {
        LazyVGrid(columns: [
            GridItem(.flexible(), spacing: UmuveSpacing.normal),
            GridItem(.flexible(), spacing: UmuveSpacing.normal),
            GridItem(.flexible(), spacing: UmuveSpacing.normal)
        ], spacing: UmuveSpacing.normal) {
            ForEach(Array(bookingData.photos.enumerated()), id: \.offset) { index, photoData in
                ZStack(alignment: .topTrailing) {
                    if let uiImage = UIImage(data: photoData) {
                        Image(uiImage: uiImage)
                            .resizable()
                            .aspectRatio(1, contentMode: .fill)
                            .frame(maxWidth: .infinity)
                            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
                            .overlay(
                                RoundedRectangle(cornerRadius: UmuveRadius.md)
                                    .strokeBorder(Color.umuveBorder, lineWidth: 1)
                            )
                            .shadow(color: .black.opacity(0.08), radius: 6, x: 0, y: 3)
                    }

                    Button(action: {
                        viewModel.removePhoto(at: index, from: &bookingData.photos)
                    }) {
                        Image(systemName: "xmark")
                            .font(.system(size: 12, weight: .bold))
                            .foregroundColor(.white)
                            .padding(6)
                            .background(Circle().fill(Color.umuvePrimary))
                            .shadow(color: .black.opacity(0.2), radius: 3, x: 0, y: 1)
                    }
                    .offset(x: 6, y: -6)
                }
            }
        }
    }
    
    // MARK: - Action Buttons
    private var actionButtons: some View {
        HStack(spacing: UmuveSpacing.normal) {
            PhotosPicker(
                selection: $viewModel.selectedItems,
                maxSelectionCount: 10,
                matching: .images
            ) {
                photoActionLabel(icon: "photo.on.rectangle.angled", title: "Gallery", accent: .categoryBlue)
            }
            .onChange(of: viewModel.selectedItems) { items in
                loadPhotos(items)
            }

            Button {
                showCamera = true
            } label: {
                photoActionLabel(icon: "camera.fill", title: "Camera", accent: .categoryOrange)
            }
        }
        .buttonStyle(.plain)
    }

    private func photoActionLabel(icon: String, title: String, accent: Color) -> some View {
        VStack(spacing: UmuveSpacing.small) {
            ZStack {
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .fill(accent.opacity(0.18))
                    .frame(width: 56, height: 56)

                Image(systemName: icon)
                    .font(.system(size: 26))
                    .foregroundColor(accent)
            }

            Text(title)
                .font(UmuveTypography.bodyFont.weight(.semibold))
                .foregroundColor(.umuveText)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuveBorder, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 4)
    }

    // MARK: - Tip Box
    private var tipBox: some View {
        HStack(alignment: .top, spacing: UmuveSpacing.normal) {
            ZStack {
                RoundedRectangle(cornerRadius: UmuveRadius.sm)
                    .fill(Color.categoryYellow.opacity(0.22))
                    .frame(width: 40, height: 40)

                Image(systemName: "lightbulb.fill")
                    .font(.system(size: 18))
                    .foregroundColor(.categoryYellow)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Pro tip")
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)

                Text("More photos = more accurate quotes")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
            }

            Spacer(minLength: 0)
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuveBorder, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 4)
    }
    
    // MARK: - Continue Button
    private var continueButton: some View {
        Button {
            wizardVM.completeCurrentStep()
        } label: {
            Text(viewModel.continueButtonText(photoCount: bookingData.photos.count))
        }
        .buttonStyle(UmuvePrimaryButtonStyle())
        .padding(UmuveSpacing.large)
        .background(Color.umuveBackground)
    }
    
    // MARK: - Load Photos
    private func loadPhotos(_ items: [PhotosPickerItem]) {
        viewModel.loadPhotos(from: items) { photoData in
            bookingData.photos.append(contentsOf: photoData)
        }
    }
}

// MARK: - Preview
struct PhotoUploadView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            PhotoUploadView()
                .environmentObject(BookingData())
        }
    }
}

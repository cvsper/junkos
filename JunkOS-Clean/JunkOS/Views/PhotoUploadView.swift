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
                // Header (no progress bar - wizard handles that)
                VStack(spacing: UmuveSpacing.small) {
                    Text("Take Photos")
                        .font(UmuveTypography.h1Font)
                        .foregroundColor(.umuveText)

                    Text("Help us understand what needs to go")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
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
        HStack(alignment: .top, spacing: UmuveSpacing.medium) {
            Image(systemName: "info.circle.fill")
                .font(.system(size: 24))
                .foregroundColor(.umuveCTA)

            Text("Photos help us provide accurate pricing. You can skip this step, but we recommend at least 1 photo.")
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(.umuveTextMuted)
                .fixedSize(horizontal: false, vertical: true)

            Spacer()
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveCTA.opacity(0.1))
        .cornerRadius(12)
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
            GridItem(.flexible(), spacing: UmuveSpacing.medium),
            GridItem(.flexible(), spacing: UmuveSpacing.medium),
            GridItem(.flexible(), spacing: UmuveSpacing.medium)
        ], spacing: UmuveSpacing.medium) {
            ForEach(Array(bookingData.photos.enumerated()), id: \.offset) { index, photoData in
                ZStack(alignment: .topTrailing) {
                    if let uiImage = UIImage(data: photoData) {
                        Image(uiImage: uiImage)
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                            .frame(width: 100, height: 100)
                            .clipped()
                            .cornerRadius(12)
                    }
                    
                    // Remove button (with haptic)
                    Button(action: {
                        viewModel.removePhoto(at: index, from: &bookingData.photos)
                    }) {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 24))
                            .foregroundColor(.white)
                            .background(Circle().fill(Color.red))
                    }
                    .offset(x: 8, y: -8)
                }
            }
        }
    }
    
    // MARK: - Action Buttons
    private var actionButtons: some View {
        HStack(spacing: UmuveSpacing.normal) {
            // SF Symbol: photo.on.rectangle for photo gallery
            PhotosPicker(
                selection: $viewModel.selectedItems,
                maxSelectionCount: 10,
                matching: .images
            ) {
                HStack {
                    Image(systemName: "photo.on.rectangle")
                    Text("Gallery")
                }
            }
            .buttonStyle(UmuveSecondaryButtonStyle())
            .onChange(of: viewModel.selectedItems) { items in
                loadPhotos(items)
            }
            
            // SF Symbol: camera for camera
            Button(action: {
                showCamera = true
            }) {
                HStack {
                    Image(systemName: "camera")
                    Text("Camera")
                }
            }
            .buttonStyle(UmuveSecondaryButtonStyle())
        }
    }
    
    // MARK: - Tip Box
    private var tipBox: some View {
        HStack(alignment: .top, spacing: UmuveSpacing.medium) {
            // SF Symbol: lightbulb.fill for tips/ideas
            // https://developer.apple.com/design/human-interface-guidelines/sf-symbols
            Image(systemName: "lightbulb.fill")
                .font(.system(size: 24))
                .foregroundColor(.umuveCTA)
            
            VStack(alignment: .leading, spacing: 4) {
                Text("Tip")
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)
                
                Text("More photos = more accurate quotes")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
            }
            
            Spacer()
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuvePrimary.opacity(0.1))
        .cornerRadius(12)
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

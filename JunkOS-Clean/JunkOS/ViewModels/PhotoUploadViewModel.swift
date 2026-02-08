//
//  PhotoUploadViewModel.swift
//  JunkOS
//
//  ViewModel for PhotoUploadView
//

import SwiftUI
import PhotosUI
import Combine

class PhotoUploadViewModel: ObservableObject {
    // MARK: - Published Properties
    @Published var selectedItems: [PhotosPickerItem] = []
    @Published var elementsVisible = false
    
    // MARK: - Public Methods
    
    /// Start entrance animations
    func startAnimations() {
        withAnimation(AnimationConstants.smoothSpring) {
            elementsVisible = true
        }
    }
    
    /// Load photos from PhotosPicker items
    func loadPhotos(from items: [PhotosPickerItem], completion: @escaping ([Data]) -> Void) {
        Task {
            var photoDataArray: [Data] = []
            
            for item in items {
                if let data = try? await item.loadTransferable(type: Data.self) {
                    photoDataArray.append(data)
                }
            }
            
            await MainActor.run {
                completion(photoDataArray)
                self.selectedItems = []
            }
        }
    }
    
    /// Remove photo at index with animation
    func removePhoto(at index: Int, from photos: inout [Data]) {
        HapticManager.shared.lightTap()
        withAnimation(AnimationConstants.fastEase) {
            photos.remove(at: index)
        }
    }
    
    /// Generate continue button text
    func continueButtonText(photoCount: Int) -> String {
        if photoCount == 0 {
            return "Skip Photos →"
        } else {
            return "Continue with \(photoCount) photo\(photoCount == 1 ? "" : "s") →"
        }
    }
}

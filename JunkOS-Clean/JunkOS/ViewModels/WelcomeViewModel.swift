//
//  WelcomeViewModel.swift
//  JunkOS
//
//  ViewModel for WelcomeView
//

import SwiftUI
import Combine

class WelcomeViewModel: ObservableObject {
    // MARK: - Published Properties
    @Published var isAnimating = false
    
    // MARK: - Public Methods
    
    /// Trigger entrance animations
    func startAnimations() {
        withAnimation(.easeInOut(duration: 0.6)) {
            isAnimating = true
        }
    }
}

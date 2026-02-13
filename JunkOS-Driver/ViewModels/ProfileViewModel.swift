//
//  ProfileViewModel.swift
//  Umuve Pro
//
//  Profile editing and logout.
//

import Foundation

@Observable
final class ProfileViewModel {
    var isLoading = false
    var errorMessage: String?

    func updateProfile(truckType: String?, truckCapacity: Double?) async {
        // Placeholder for future profile editing API
    }
}

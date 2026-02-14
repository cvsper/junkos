//
//  StripeConnectViewModel.swift
//  Umuve Pro
//
//  Manages Stripe Connect onboarding state.
//  Handles account creation, onboarding link generation, and status checking.
//

import Foundation
import SwiftUI

enum ConnectOnboardingStatus {
    case loading
    case notSetUp
    case pendingVerification
    case active
    case failed(String)
}

@Observable
final class StripeConnectViewModel {
    var onboardingStatus: ConnectOnboardingStatus = .loading
    var showSafari = false
    var accountLinkURL: URL?
    var isCreatingAccount = false

    private let api = DriverAPIClient.shared

    // MARK: - Check Status

    func checkStatus() async {
        onboardingStatus = .loading

        do {
            let response = try await api.getConnectStatus()

            // Map status string to enum
            switch response.status {
            case "active":
                onboardingStatus = .active
            case "pending_verification":
                onboardingStatus = .pendingVerification
            case "not_set_up":
                onboardingStatus = .notSetUp
            default:
                onboardingStatus = .notSetUp
            }
        } catch {
            onboardingStatus = .failed(error.localizedDescription)
        }
    }

    // MARK: - Start Onboarding

    func startOnboarding() async {
        isCreatingAccount = true

        do {
            // Step 1: Create account (idempotent — safe to call multiple times)
            _ = try await api.createConnectAccount()

            // Step 2: Get fresh account link
            let linkResponse = try await api.createAccountLink()

            guard let url = URL(string: linkResponse.url) else {
                onboardingStatus = .failed("Invalid onboarding URL")
                isCreatingAccount = false
                return
            }

            accountLinkURL = url
            showSafari = true
            isCreatingAccount = false
        } catch {
            onboardingStatus = .failed(error.localizedDescription)
            isCreatingAccount = false
        }
    }

    // MARK: - Safari Dismissed

    func onSafariDismissed() async {
        // User returned from browser — check updated status
        await checkStatus()
    }
}

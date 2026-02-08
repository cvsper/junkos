//
//  AuthenticationManager.swift
//  JunkOS Driver
//
//  Manages driver authentication state — login, signup, Apple Sign In.
//  Stores JWT in Keychain for persistence. Uses async/await.
//

import Foundation
import AuthenticationServices

@Observable
final class AuthenticationManager {
    var isAuthenticated = false
    var currentUser: DriverUser?
    var isLoading = false
    var errorMessage: String?

    private let api = DriverAPIClient.shared

    init() {
        Task { await restoreSession() }
    }

    // MARK: - Email Auth

    func login(email: String, password: String) async {
        isLoading = true
        errorMessage = nil
        do {
            let response = try await api.login(email: email, password: password)
            setAuthenticated(user: response.user, token: response.token)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func signup(email: String, password: String, name: String?) async {
        isLoading = true
        errorMessage = nil
        do {
            let response = try await api.signup(email: email, password: password, name: name)
            setAuthenticated(user: response.user, token: response.token)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    // MARK: - Apple Sign In

    func handleAppleSignInRequest(_ request: ASAuthorizationAppleIDRequest) {
        request.requestedScopes = [.fullName, .email]
    }

    func handleAppleSignInCompletion(_ result: Result<ASAuthorization, Error>) {
        switch result {
        case .success(let auth):
            guard let credential = auth.credential as? ASAuthorizationAppleIDCredential else { return }
            Task {
                isLoading = true
                errorMessage = nil
                let name = [credential.fullName?.givenName, credential.fullName?.familyName]
                    .compactMap { $0 }
                    .joined(separator: " ")
                do {
                    let response = try await api.appleSignIn(
                        userIdentifier: credential.user,
                        email: credential.email,
                        name: name.isEmpty ? nil : name
                    )
                    setAuthenticated(user: response.user, token: response.token)
                } catch {
                    errorMessage = error.localizedDescription
                }
                isLoading = false
            }
        case .failure(let error):
            errorMessage = error.localizedDescription
            HapticManager.shared.error()
        }
    }

    // MARK: - Logout

    func logout() {
        isAuthenticated = false
        currentUser = nil
        KeychainHelper.delete(forKey: "authToken")
        KeychainHelper.delete(forKey: "userId")
        SocketIOManager.shared.disconnect()
    }

    // MARK: - Private

    private func setAuthenticated(user: DriverUser, token: String) {
        currentUser = user
        isAuthenticated = true
        KeychainHelper.save(token, forKey: "authToken")
        KeychainHelper.save(user.id, forKey: "userId")
        HapticManager.shared.success()
    }

    private func restoreSession() async {
        guard let savedToken = KeychainHelper.loadString(forKey: "authToken"),
              !savedToken.isEmpty else { return }
        do {
            let profileResponse = try await api.getContractorProfile()
            if let user = profileResponse.contractor.user {
                currentUser = user
                isAuthenticated = true
            }
        } catch {
            // Only clear if the token hasn't been replaced by a fresh login
            let currentToken = KeychainHelper.loadString(forKey: "authToken")
            if currentToken == savedToken {
                KeychainHelper.delete(forKey: "authToken")
                KeychainHelper.delete(forKey: "userId")
            }
        }
    }
}

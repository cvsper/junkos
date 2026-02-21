//
//  AuthenticationManager.swift
//  Umuve
//
//  Manages user authentication state and API calls
//

import Foundation
import SwiftUI
import AuthenticationServices
import CryptoKit

class AuthenticationManager: ObservableObject {
    // MARK: - Published Properties
    @Published var isAuthenticated = false
    @Published var currentUser: User?
    @Published var isLoading = false
    @Published var errorMessage: String?

    // MARK: - Private Properties
    private let baseURL = Config.shared.baseURL
    private let apiKey = Config.shared.apiKey
    private var currentNonce: String?

    // MARK: - Initialization
    init() {
        // Restore session from Keychain
        Task {
            await restoreSession()
        }
    }

    // MARK: - Apple Sign In

    /// Handle Apple Sign In request configuration
    func handleAppleSignInRequest(_ request: ASAuthorizationAppleIDRequest) {
        // Generate random nonce
        let nonce = generateNonce(length: 32)
        currentNonce = nonce

        // Set request configuration
        request.requestedScopes = [.fullName, .email]
        request.nonce = sha256(nonce)
    }

    /// Handle Apple Sign In completion
    func handleAppleSignInCompletion(_ result: Result<ASAuthorization, Error>) {
        Task { @MainActor in
            switch result {
            case .success(let authorization):
                if let appleIDCredential = authorization.credential as? ASAuthorizationAppleIDCredential {
                    await authenticateWithApple(credential: appleIDCredential)
                }
            case .failure(let error):
                print("Apple Sign In failed: \(error.localizedDescription)")
                errorMessage = "Something went wrong. Try again."
                HapticManager.shared.error()
            }
        }
    }

    /// Authenticate with Apple ID credential
    private func authenticateWithApple(credential: ASAuthorizationAppleIDCredential) async {
        guard let identityTokenData = credential.identityToken,
              let identityToken = String(data: identityTokenData, encoding: .utf8),
              let nonce = currentNonce else {
            await MainActor.run {
                errorMessage = "Something went wrong. Try again."
                HapticManager.shared.error()
            }
            return
        }

        // Extract email and name
        let email = credential.email
        var name: String?
        if let fullName = credential.fullName {
            let nameParts = [fullName.givenName, fullName.familyName]
                .compactMap { $0 }
                .joined(separator: " ")
            if !nameParts.isEmpty {
                name = nameParts
            }
        }

        // Send to backend with nonce
        await authenticateWithAppleBackend(
            identityToken: identityToken,
            nonce: nonce,
            email: email,
            name: name
        )
    }

    /// Send Apple Sign In credential to backend with nonce validation
    private func authenticateWithAppleBackend(
        identityToken: String,
        nonce: String,
        email: String?,
        name: String?
    ) async {
        guard let url = URL(string: "\(baseURL)/api/auth/apple") else {
            await MainActor.run {
                errorMessage = "Something went wrong. Try again."
                HapticManager.shared.error()
            }
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")

        var body: [String: Any] = [
            "identity_token": identityToken,
            "nonce": nonce
        ]

        if let email = email {
            body["email"] = email
        }

        if let name = name {
            body["name"] = name
        }

        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        // Retry logic: 2-3 attempts with 1 second delay
        var lastError: Error?
        for attempt in 1...3 {
            do {
                let (data, response) = try await URLSession.shared.data(for: request)

                guard let httpResponse = response as? HTTPURLResponse else {
                    lastError = NSError(domain: "AuthError", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid response"])
                    if attempt < 3 {
                        try await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
                        continue
                    }
                    break
                }

                if httpResponse.statusCode == 200,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let token = json["token"] as? String,
                   let userData = json["user"] as? [String: Any] {

                    // Parse user
                    let user = User(
                        id: userData["id"] as? String ?? "",
                        name: userData["name"] as? String,
                        email: userData["email"] as? String,
                        phoneNumber: userData["phoneNumber"] as? String,
                        role: userData["role"] as? String
                    )

                    await setAuthenticated(user: user, token: token)
                    await MainActor.run {
                        HapticManager.shared.success()
                    }
                    return
                } else {
                    // Check for specific error messages from backend
                    if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       let errorMsg = json["error"] as? String {
                        if errorMsg.contains("role") {
                            await MainActor.run {
                                errorMessage = "This account is registered as a driver. Please use the driver app."
                            }
                            return
                        }
                    }

                    lastError = NSError(domain: "AuthError", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: "Authentication failed"])
                    if attempt < 3 {
                        try await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
                        continue
                    }
                }

            } catch {
                lastError = error
                if attempt < 3 {
                    try? await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
                    continue
                }
            }
        }

        // All retries failed
        await MainActor.run {
            errorMessage = "Something went wrong. Try again."
            HapticManager.shared.error()
        }
    }

    // MARK: - Session Management

    /// Restore session from Keychain on app launch
    func restoreSession() async {
        guard let token = KeychainHelper.loadString(forKey: "authToken") else {
            return
        }

        guard let url = URL(string: "\(baseURL)/api/auth/validate") else {
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let userData = json["user"] as? [String: Any] else {
                // Invalid token, clear storage
                await logout()
                return
            }

            let user = User(
                id: userData["id"] as? String ?? "",
                name: userData["name"] as? String,
                email: userData["email"] as? String,
                phoneNumber: userData["phoneNumber"] as? String,
                role: userData["role"] as? String
            )

            await MainActor.run {
                self.currentUser = user
                self.isAuthenticated = true
            }

        } catch {
            // Network error during restore - keep trying on next launch
            print("Session restore failed: \(error.localizedDescription)")
        }
    }

    /// Set authenticated state and save to Keychain
    @MainActor
    private func setAuthenticated(user: User, token: String) async {
        self.currentUser = user
        self.isAuthenticated = true

        // Save to Keychain
        KeychainHelper.save(token, forKey: "authToken")
        KeychainHelper.save(user.id, forKey: "userId")

        // Re-register push token with the backend now that we have auth
        NotificationManager.shared.reRegisterTokenIfNeeded()
    }

    /// Refresh JWT token if near expiry
    func refreshTokenIfNeeded() async {
        guard let token = KeychainHelper.loadString(forKey: "authToken") else {
            return
        }

        // Decode JWT to check expiry
        let parts = token.split(separator: ".")
        guard parts.count == 3,
              let payloadData = Data(base64Encoded: String(parts[1])),
              let payload = try? JSONSerialization.jsonObject(with: payloadData) as? [String: Any],
              let exp = payload["exp"] as? TimeInterval else {
            return
        }

        let expiryDate = Date(timeIntervalSince1970: exp)
        let now = Date()
        let timeUntilExpiry = expiryDate.timeIntervalSince(now)

        // Refresh if expiring within 24 hours
        guard timeUntilExpiry < 86400 else {
            return
        }

        guard let url = URL(string: "\(baseURL)/api/auth/refresh") else {
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let newToken = json["token"] as? String else {
                // Refresh failed but don't logout - keep cached state
                return
            }

            // Save new token
            KeychainHelper.save(newToken, forKey: "authToken")

        } catch {
            // Network error during refresh - keep cached state
            print("Token refresh failed: \(error.localizedDescription)")
        }
    }

    /// Logout and clear all stored credentials
    @MainActor
    func logout() async {
        isAuthenticated = false
        currentUser = nil
        errorMessage = nil

        // Clear Keychain
        KeychainHelper.delete(forKey: "authToken")
        KeychainHelper.delete(forKey: "userId")
    }

    // MARK: - Deprecated Auth Methods (Stubs for UI Compatibility)

    // MARK: - Phone Authentication

    /// Send verification code via SMS
    func sendVerificationCode(phoneNumber: String) async {
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        do {
            let url = URL(string: "\(baseURL)/api/auth/send-code")!
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")

            let body = ["phoneNumber": phoneNumber]
            request.httpBody = try JSONEncoder().encode(body)

            let (data, response) = try await URLSession.shared.data(for: request)

            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                // Parse response to get dev code if available
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let code = json["code"] as? String {
                    // Dev mode - show code in error message
                    await MainActor.run {
                        errorMessage = "DEV MODE - Your code is: \(code)"
                        isLoading = false
                    }
                } else {
                    await MainActor.run {
                        isLoading = false
                    }
                }
            } else {
                throw NSError(domain: "Auth", code: -1, userInfo: [NSLocalizedDescriptionKey: "Failed to send code"])
            }
        } catch {
            await MainActor.run {
                errorMessage = "Failed to send code. Try again."
                isLoading = false
                HapticManager.shared.error()
            }
        }
    }

    /// Verify SMS code and authenticate
    func verifyCode(phoneNumber: String, code: String) async {
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        do {
            let url = URL(string: "\(baseURL)/api/auth/verify-code")!
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")

            let body = ["phoneNumber": phoneNumber, "code": code]
            request.httpBody = try JSONEncoder().encode(body)

            let (data, response) = try await URLSession.shared.data(for: request)

            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)

                // Save token to Keychain
                KeychainHelper.save(authResponse.token, forKey: "authToken")

                // Update state
                await MainActor.run {
                    currentUser = authResponse.user
                    isAuthenticated = true
                    isLoading = false
                    HapticManager.shared.success()
                }
            } else {
                throw NSError(domain: "Auth", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid code"])
            }
        } catch {
            await MainActor.run {
                errorMessage = "Invalid code. Try again."
                isLoading = false
                HapticManager.shared.error()
            }
        }
    }

    /// Deprecated: Email auth removed - Apple Sign In only
    func loginWithEmail(email: String, password: String, completion: @escaping (Bool, String?) -> Void) {
        DispatchQueue.main.async {
            self.errorMessage = "Email authentication is no longer supported. Please use Sign in with Apple."
            completion(false, "Email authentication is no longer supported")
        }
    }

    /// Deprecated: Email auth removed - Apple Sign In only
    func loginWithEmail(email: String, password: String, completion: @escaping (Bool, String?) -> Void) {
        DispatchQueue.main.async {
            self.errorMessage = "Email authentication is no longer supported. Please use Sign in with Apple."
            completion(false, "Email authentication is no longer supported")
        }
    }

    /// Deprecated: Password reset removed - Apple Sign In only
    func requestPasswordReset(email: String, completion: @escaping (Bool, String?) -> Void) {
        DispatchQueue.main.async {
            self.errorMessage = "Password reset is no longer supported. Please use Sign in with Apple."
            completion(false, "Password reset is no longer supported")
        }
    }

    /// Deprecated: Guest mode removed
    func continueAsGuest() {
        DispatchQueue.main.async {
            self.errorMessage = "Guest mode is no longer supported. Please use Sign in with Apple."
        }
    }

    // MARK: - Nonce Helpers

    /// Generate random nonce for Apple Sign In
    private func generateNonce(length: Int = 32) -> String {
        var randomBytes = [UInt8](repeating: 0, count: length)
        let status = SecRandomCopyBytes(kSecRandomDefault, length, &randomBytes)

        guard status == errSecSuccess else {
            // Fallback to UUID-based nonce
            return UUID().uuidString.replacingOccurrences(of: "-", with: "")
        }

        return randomBytes.map { String(format: "%02x", $0) }.joined()
    }

    /// SHA256 hash for nonce
    private func sha256(_ input: String) -> String {
        let inputData = Data(input.utf8)
        let hashed = SHA256.hash(data: inputData)
        return hashed.compactMap { String(format: "%02x", $0) }.joined()
    }
}

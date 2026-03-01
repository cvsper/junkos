//
//  AuthenticationManager.swift
//  Umuve Pro
//
//  Manages driver authentication state — login, signup, Apple Sign In.
//  Stores JWT in Keychain for persistence. Uses async/await.
//

import Foundation
import AuthenticationServices
import CryptoKit

@Observable
final class AuthenticationManager {
    var isAuthenticated = false
    var currentUser: DriverUser?
    var isLoading = false
    var errorMessage: String?

    private let api = DriverAPIClient.shared
    private var currentNonce: String?
    private let existingAccountMarkers = [
        "already exists",
        "already registered",
        "account exists",
        "user exists",
        "duplicate",
        "email already",
        "phone already"
    ]

    init() {
        Task { await restoreSession() }
    }

    // MARK: - Apple Sign In

    func handleAppleSignInRequest(_ request: ASAuthorizationAppleIDRequest) {
        let nonce = generateNonce()
        currentNonce = nonce
        request.nonce = sha256(nonce)
        request.requestedScopes = [.fullName, .email]
    }

    func handleAppleSignInCompletion(_ result: Result<ASAuthorization, Error>) {
        switch result {
        case .success(let auth):
            guard let credential = auth.credential as? ASAuthorizationAppleIDCredential else { return }
            Task {
                isLoading = true
                errorMessage = nil

                guard let identityTokenData = credential.identityToken,
                      let identityToken = String(data: identityTokenData, encoding: .utf8) else {
                    errorMessage = "Failed to get identity token"
                    isLoading = false
                    return
                }

                let name = [credential.fullName?.givenName, credential.fullName?.familyName]
                    .compactMap { $0 }
                    .joined(separator: " ")

                // Retry logic: up to 3 attempts
                var attempts = 0
                let maxAttempts = 3

                while attempts < maxAttempts {
                    do {
                        let response = try await api.appleSignIn(
                            identityToken: identityToken,
                            nonce: currentNonce,
                            userIdentifier: credential.user,
                            email: credential.email,
                            name: name.isEmpty ? nil : name
                        )
                        currentNonce = nil
                        setAuthenticated(user: response.user, token: response.token)
                        isLoading = false
                        return
                    } catch {
                        attempts += 1
                        if attempts < maxAttempts {
                            try? await Task.sleep(nanoseconds: 1_000_000_000) // 1 second delay
                        }
                    }
                }

                // All retries failed
                currentNonce = nil
                errorMessage = "Something went wrong. Try again."
                isLoading = false
            }
        case .failure(let error):
            currentNonce = nil
            let asError = error as? ASAuthorizationError
            print("🔴 Apple Sign In FAILED — code: \(asError?.code.rawValue ?? -1), domain: \((error as NSError).domain), description: \(error.localizedDescription)")
            errorMessage = error.localizedDescription
            HapticManager.shared.error()
        }
    }

    // MARK: - Email Authentication

    func emailSignup(email: String, password: String, name: String?, inviteCode: String?) async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await api.emailSignup(email: email, password: password, name: name, inviteCode: inviteCode)
            setAuthenticated(user: response.user, token: response.token)
            isLoading = false
        } catch {
            errorMessage = normalizedAuthErrorMessage(for: error, fallback: "Signup failed. Try again.")
            isLoading = false
            HapticManager.shared.error()
        }
    }

    func emailLogin(email: String, password: String) async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await api.emailLogin(email: email, password: password)
            setAuthenticated(user: response.user, token: response.token)
            isLoading = false
        } catch {
            errorMessage = normalizedAuthErrorMessage(for: error, fallback: "Login failed. Check your credentials.")
            isLoading = false
            HapticManager.shared.error()
        }
    }

    func phoneLogin(phone: String, password: String) async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await api.phoneLogin(phone: phone, password: password)
            setAuthenticated(user: response.user, token: response.token)
            isLoading = false
        } catch {
            errorMessage = normalizedAuthErrorMessage(for: error, fallback: "Login failed. Check your credentials.")
            isLoading = false
            HapticManager.shared.error()
        }
    }

    // MARK: - Phone Authentication

    func sendVerificationCode(phoneNumber: String) async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await api.sendVerificationCode(phoneNumber: phoneNumber)
            // Check if dev mode code is present
            if let code = response.code {
                errorMessage = "DEV MODE - Your code is: \(code)"
            }
            isLoading = false
        } catch {
            errorMessage = "Failed to send code. Try again."
            isLoading = false
            HapticManager.shared.error()
        }
    }

    func verifyCode(phoneNumber: String, code: String) async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await api.verifyCode(phoneNumber: phoneNumber, code: code)
            setAuthenticated(user: response.user, token: response.token)
            isLoading = false
        } catch {
            errorMessage = normalizedAuthErrorMessage(for: error, fallback: "Invalid code. Try again.")
            isLoading = false
            HapticManager.shared.error()
        }
    }

    func indicatesExistingAccount(message: String?) -> Bool {
        guard let message else { return false }
        let normalized = message.lowercased()
        return existingAccountMarkers.contains { normalized.contains($0) }
    }

    // MARK: - Dev Login

    func devLogin() async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await api.devDriverLogin()
            setAuthenticated(user: response.user, token: response.token)
            isLoading = false
        } catch {
            errorMessage = "Dev login failed. Try again."
            isLoading = false
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

    private func normalizedAuthErrorMessage(for error: Error, fallback: String) -> String {
        let message: String
        if let apiError = error as? APIError {
            message = apiError.errorDescription ?? fallback
        } else {
            message = fallback
        }

        if indicatesExistingAccount(message: message) {
            return "Account already exists. Log in with your existing password."
        }

        return message
    }

    private func restoreSession() async {
        guard let savedToken = KeychainHelper.loadString(forKey: "authToken"),
              !savedToken.isEmpty else {
            print("🔐 No saved token found")
            return
        }

        print("🔐 Checking saved token...")

        // First, check if token is expired and try to refresh
        if isTokenExpired(savedToken) {
            print("⏰ Token expired, attempting refresh...")
            do {
                let response = try await api.refreshToken()
                if response.success {
                    KeychainHelper.save(response.token, forKey: "authToken")
                    print("✅ Token refreshed successfully")
                } else {
                    print("❌ Token refresh failed")
                    logout()
                    return
                }
            } catch {
                print("❌ Token refresh error: \(error.localizedDescription)")
                logout()
                return
            }
        }

        // Now try to restore session with valid token
        do {
            let profileResponse = try await api.getContractorProfile()
            if let user = profileResponse.contractor.user {
                currentUser = user
                isAuthenticated = true
                print("✅ Session restored successfully")
            }
        } catch {
            print("❌ Session restore failed: \(error.localizedDescription)")
            // Only clear if the token hasn't been replaced by a fresh login
            let currentToken = KeychainHelper.loadString(forKey: "authToken")
            if currentToken == savedToken {
                logout()
            }
        }
    }

    private func isTokenExpired(_ token: String) -> Bool {
        let segments = token.split(separator: ".")
        guard segments.count == 3 else { return true }

        let payloadSegment = String(segments[1])
        var base64 = payloadSegment.replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        while base64.count % 4 != 0 {
            base64.append("=")
        }

        guard let payloadData = Data(base64Encoded: base64),
              let payload = try? JSONSerialization.jsonObject(with: payloadData) as? [String: Any],
              let exp = payload["exp"] as? TimeInterval else {
            return true
        }

        let expirationDate = Date(timeIntervalSince1970: exp)
        return Date() >= expirationDate
    }

    private func refreshTokenIfNeeded() async {
        guard let token = KeychainHelper.loadString(forKey: "authToken") else { return }

        // Decode JWT payload to check expiration
        let segments = token.split(separator: ".")
        guard segments.count == 3 else { return }

        let payloadSegment = String(segments[1])
        // Add padding if needed for base64
        var base64 = payloadSegment.replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        while base64.count % 4 != 0 {
            base64.append("=")
        }

        guard let payloadData = Data(base64Encoded: base64),
              let payload = try? JSONSerialization.jsonObject(with: payloadData) as? [String: Any],
              let exp = payload["exp"] as? TimeInterval else {
            return
        }

        let expirationDate = Date(timeIntervalSince1970: exp)
        let now = Date()
        let twentyFourHoursFromNow = now.addingTimeInterval(24 * 60 * 60)

        // Refresh if expiring within 24 hours
        if expirationDate <= twentyFourHoursFromNow {
            do {
                let response = try await api.refreshToken()
                if response.success {
                    KeychainHelper.save(response.token, forKey: "authToken")
                }
            } catch {
                // Keep existing token on failure — don't force logout
            }
        }
    }

    // MARK: - Nonce Generation

    private func generateNonce(length: Int = 32) -> String {
        var bytes = [UInt8](repeating: 0, count: length)
        let result = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        guard result == errSecSuccess else {
            return UUID().uuidString.replacingOccurrences(of: "-", with: "")
        }
        return bytes.map { String(format: "%02x", $0) }.joined()
    }

    private func sha256(_ input: String) -> String {
        let inputData = Data(input.utf8)
        let hashed = SHA256.hash(data: inputData)
        return hashed.compactMap { String(format: "%02x", $0) }.joined()
    }
}

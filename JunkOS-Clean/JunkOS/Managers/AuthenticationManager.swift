//
//  AuthenticationManager.swift
//  JunkOS
//
//  Manages user authentication state and API calls
//

import Foundation
import SwiftUI
import AuthenticationServices

class AuthenticationManager: ObservableObject {
    // MARK: - Published Properties
    @Published var isAuthenticated = false
    @Published var currentUser: User?
    @Published var authToken: String?
    
    // MARK: - API Configuration
    private let baseURL = Config.shared.baseURL
    private let apiKey = Config.shared.apiKey
    
    // MARK: - Initialization
    init() {
        // Check for stored auth token
        loadStoredAuth()
    }
    
    // MARK: - Phone Authentication
    
    /// Send SMS verification code to phone number
    func sendVerificationCode(to phoneNumber: String, completion: @escaping (Bool) -> Void) {
        guard let url = URL(string: "\(baseURL)/api/auth/send-code") else {
            completion(false)
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "X-API-Key")
        
        let body: [String: Any] = ["phoneNumber": phoneNumber]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    print("Error sending verification code: \(error.localizedDescription)")
                    completion(false)
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse,
                      httpResponse.statusCode == 200 else {
                    completion(false)
                    return
                }
                
                completion(true)
            }
        }.resume()
    }
    
    /// Verify SMS code and authenticate user
    func verifyCode(_ code: String, for phoneNumber: String, completion: @escaping (Bool, String?) -> Void) {
        guard let url = URL(string: "\(baseURL)/api/auth/verify-code") else {
            completion(false, "Invalid URL")
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "X-API-Key")
        
        let body: [String: Any] = [
            "phoneNumber": phoneNumber,
            "code": code
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    print("Error verifying code: \(error.localizedDescription)")
                    completion(false, "Network error")
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse else {
                    completion(false, "Invalid response")
                    return
                }
                
                if httpResponse.statusCode == 200,
                   let data = data,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let token = json["token"] as? String,
                   let userData = json["user"] as? [String: Any] {
                    
                    // Parse user
                    let user = User(
                        id: userData["id"] as? String ?? "",
                        name: userData["name"] as? String,
                        email: userData["email"] as? String,
                        phoneNumber: userData["phoneNumber"] as? String
                    )
                    
                    self.setAuthenticated(user: user, token: token)
                    completion(true, nil)
                } else {
                    completion(false, "Invalid verification code")
                }
            }
        }.resume()
    }
    
    // MARK: - Email Authentication
    
    /// Login with email and password
    func loginWithEmail(email: String, password: String, completion: @escaping (Bool, String?) -> Void) {
        guard let url = URL(string: "\(baseURL)/api/auth/login") else {
            completion(false, "Invalid URL")
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "X-API-Key")
        
        let body: [String: Any] = [
            "email": email,
            "password": password
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    print("Error logging in: \(error.localizedDescription)")
                    completion(false, "Network error")
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse else {
                    completion(false, "Invalid response")
                    return
                }
                
                if httpResponse.statusCode == 200,
                   let data = data,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let token = json["token"] as? String,
                   let userData = json["user"] as? [String: Any] {
                    
                    // Parse user
                    let user = User(
                        id: userData["id"] as? String ?? "",
                        name: userData["name"] as? String,
                        email: userData["email"] as? String,
                        phoneNumber: userData["phoneNumber"] as? String
                    )
                    
                    self.setAuthenticated(user: user, token: token)
                    completion(true, nil)
                } else if httpResponse.statusCode == 401 {
                    completion(false, "Invalid email or password")
                } else {
                    completion(false, "Login failed")
                }
            }
        }.resume()
    }
    
    // MARK: - Apple Sign In
    
    /// Handle Apple Sign In request configuration
    func handleAppleSignInRequest(_ request: ASAuthorizationAppleIDRequest) {
        request.requestedScopes = [.fullName, .email]
    }
    
    /// Handle Apple Sign In completion
    func handleAppleSignInCompletion(_ result: Result<ASAuthorization, Error>) {
        switch result {
        case .success(let authorization):
            if let appleIDCredential = authorization.credential as? ASAuthorizationAppleIDCredential {
                authenticateWithApple(credential: appleIDCredential)
            }
        case .failure(let error):
            print("Apple Sign In failed: \(error.localizedDescription)")
            HapticManager.shared.error()
        }
    }
    
    /// Authenticate with Apple ID credential
    private func authenticateWithApple(credential: ASAuthorizationAppleIDCredential) {
        guard let url = URL(string: "\(baseURL)/api/auth/apple") else {
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "X-API-Key")
        
        var body: [String: Any] = [
            "userIdentifier": credential.user
        ]
        
        if let email = credential.email {
            body["email"] = email
        }
        
        if let fullName = credential.fullName {
            let name = [fullName.givenName, fullName.familyName]
                .compactMap { $0 }
                .joined(separator: " ")
            if !name.isEmpty {
                body["name"] = name
            }
        }
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    print("Error authenticating with Apple: \(error.localizedDescription)")
                    HapticManager.shared.error()
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse,
                      httpResponse.statusCode == 200,
                      let data = data,
                      let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let token = json["token"] as? String,
                      let userData = json["user"] as? [String: Any] else {
                    HapticManager.shared.error()
                    return
                }
                
                // Parse user
                let user = User(
                    id: userData["id"] as? String ?? "",
                    name: userData["name"] as? String,
                    email: userData["email"] as? String,
                    phoneNumber: userData["phoneNumber"] as? String
                )
                
                self.setAuthenticated(user: user, token: token)
                HapticManager.shared.success()
            }
        }.resume()
    }
    
    // MARK: - Forgot Password

    /// Request a password reset link
    func requestPasswordReset(email: String, completion: @escaping (Bool, String?) -> Void) {
        guard let url = URL(string: "\(baseURL)/api/auth/forgot-password") else {
            completion(false, "Invalid URL")
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "X-API-Key")

        let body: [String: Any] = ["email": email]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    print("Error requesting password reset: \(error.localizedDescription)")
                    completion(false, "Network error")
                    return
                }

                guard let httpResponse = response as? HTTPURLResponse else {
                    completion(false, "Invalid response")
                    return
                }

                if httpResponse.statusCode == 200 {
                    completion(true, nil)
                } else if httpResponse.statusCode == 404 {
                    completion(false, "No account found with that email")
                } else {
                    completion(false, "Failed to send reset link")
                }
            }
        }.resume()
    }

    // MARK: - Guest Mode
    
    func continueAsGuest() {
        let guestUser = User(
            id: "guest",
            name: "Guest",
            email: nil,
            phoneNumber: nil
        )
        
        self.currentUser = guestUser
        self.authToken = nil
        self.isAuthenticated = true
        
        // Don't persist guest session
    }
    
    // MARK: - Logout
    
    func logout() {
        isAuthenticated = false
        currentUser = nil
        authToken = nil
        
        // Clear stored auth
        UserDefaults.standard.removeObject(forKey: "authToken")
        UserDefaults.standard.removeObject(forKey: "userId")
    }
    
    // MARK: - Private Helpers
    
    private func setAuthenticated(user: User, token: String) {
        self.currentUser = user
        self.authToken = token
        self.isAuthenticated = true

        // Store auth token
        UserDefaults.standard.set(token, forKey: "authToken")
        UserDefaults.standard.set(user.id, forKey: "userId")

        // Re-register push token with the backend now that we have auth
        NotificationManager.shared.reRegisterTokenIfNeeded()
    }
    
    private func loadStoredAuth() {
        if let token = UserDefaults.standard.string(forKey: "authToken"),
           let userId = UserDefaults.standard.string(forKey: "userId") {
            // Validate token with backend
            validateToken(token: token, userId: userId)
        }
    }
    
    private func validateToken(token: String, userId: String) {
        guard let url = URL(string: "\(baseURL)/api/auth/validate") else {
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "X-API-Key")
        request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let httpResponse = response as? HTTPURLResponse,
                   httpResponse.statusCode == 200,
                   let data = data,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let userData = json["user"] as? [String: Any] {
                    
                    let user = User(
                        id: userData["id"] as? String ?? userId,
                        name: userData["name"] as? String,
                        email: userData["email"] as? String,
                        phoneNumber: userData["phoneNumber"] as? String
                    )
                    
                    self.currentUser = user
                    self.authToken = token
                    self.isAuthenticated = true
                } else {
                    // Invalid token, clear storage
                    self.logout()
                }
            }
        }.resume()
    }
}

// MARK: - User Model

struct User: Codable {
    let id: String
    let name: String?
    let email: String?
    let phoneNumber: String?
}

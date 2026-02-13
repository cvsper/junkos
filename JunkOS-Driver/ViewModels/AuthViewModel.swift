//
//  AuthViewModel.swift
//  Umuve Pro
//
//  Login/signup form logic.
//

import Foundation

@Observable
final class AuthViewModel {
    // Form fields
    var email = ""
    var password = ""
    var name = ""
    var isSignup = false

    // Validation
    var emailError: String?
    var passwordError: String?

    var isFormValid: Bool {
        !email.isEmpty && !password.isEmpty && password.count >= 6 &&
        email.contains("@") && email.contains(".")
    }

    func validate() -> Bool {
        emailError = nil
        passwordError = nil

        if email.isEmpty {
            emailError = "Email is required"
            return false
        }
        if !email.contains("@") || !email.contains(".") {
            emailError = "Enter a valid email"
            return false
        }
        if password.isEmpty {
            passwordError = "Password is required"
            return false
        }
        if password.count < 6 {
            passwordError = "Password must be at least 6 characters"
            return false
        }
        return true
    }

    func reset() {
        email = ""
        password = ""
        name = ""
        emailError = nil
        passwordError = nil
    }
}

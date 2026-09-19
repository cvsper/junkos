//  Config.swift — Umuve Desk
//  Same backend as the browser desk and the other Umuve apps.

import Foundation

enum AppConfig {
    static let baseURL = URL(string: "https://junkos-backend.onrender.com")!
    /// Sent with every voice-token request so the server adds the push credential.
    static let platform = "ios"
    /// Render cold starts are real; the browser desk allows for them too.
    static let requestTimeout: TimeInterval = 60
}

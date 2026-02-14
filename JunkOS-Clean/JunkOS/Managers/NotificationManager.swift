//
//  NotificationManager.swift
//  Umuve
//
//  Manages push notification setup, permissions, and handling
//

import Foundation
import SwiftUI
import UserNotifications
import UIKit

// MARK: - Notification Categories

enum NotificationCategory: String, CaseIterable {
    case bookingConfirmed = "booking_confirmed"
    case driverAssigned = "driver_assigned"
    case driverEnRoute = "driver_en_route"
    case jobCompleted = "job_completed"
    case volumeAdjustment = "VOLUME_ADJUSTMENT"

    var title: String {
        switch self {
        case .bookingConfirmed:
            return "Booking Confirmed"
        case .driverAssigned:
            return "Driver Assigned"
        case .driverEnRoute:
            return "Driver En Route"
        case .jobCompleted:
            return "Job Completed"
        case .volumeAdjustment:
            return "Volume Adjustment"
        }
    }
}

// MARK: - NotificationManager

class NotificationManager: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    /// Shared singleton for accessing push token methods from outside SwiftUI
    static let shared = NotificationManager()

    // MARK: - Published Properties
    @Published var isPermissionGranted = false
    @Published var pendingDeepLink: NotificationCategory?

    // MARK: - API Configuration
    private let baseURL = Config.shared.baseURL
    private let apiKey = Config.shared.apiKey

    // MARK: - Initialization
    override init() {
        super.init()
        checkCurrentPermission()
        registerNotificationCategories()
    }

    // MARK: - Permission Management

    /// Check the current notification authorization status
    private func checkCurrentPermission() {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async {
                self.isPermissionGranted = settings.authorizationStatus == .authorized
            }
        }
    }

    /// Request notification permissions from the user
    func requestPermission() {
        UNUserNotificationCenter.current().requestAuthorization(
            options: [.alert, .badge, .sound]
        ) { granted, error in
            DispatchQueue.main.async {
                self.isPermissionGranted = granted

                if let error = error {
                    print("Notification permission error: \(error.localizedDescription)")
                    return
                }

                if granted {
                    print("Notification permission granted")
                    self.registerForRemoteNotifications()
                } else {
                    print("Notification permission denied")
                }
            }
        }
    }

    /// Register for remote (push) notifications via APNs
    private func registerForRemoteNotifications() {
        DispatchQueue.main.async {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }

    // MARK: - Notification Categories

    /// Register notification categories with the system
    private func registerNotificationCategories() {
        // Standard categories (no actions)
        var categories = Set<UNNotificationCategory>()
        for category in NotificationCategory.allCases where category != .volumeAdjustment {
            categories.insert(UNNotificationCategory(
                identifier: category.rawValue,
                actions: [],
                intentIdentifiers: [],
                options: []
            ))
        }

        // Add job status categories (for real-time tracking notifications)
        let statusCategories = ["job_en_route", "job_arrived", "job_started", "job_completed"]
        for categoryId in statusCategories {
            categories.insert(UNNotificationCategory(
                identifier: categoryId,
                actions: [],
                intentIdentifiers: [],
                options: []
            ))
        }

        // Volume adjustment category with approve/decline actions
        let approveAction = UNNotificationAction(
            identifier: "APPROVE_VOLUME",
            title: "Approve New Price",
            options: [.foreground]
        )
        let declineAction = UNNotificationAction(
            identifier: "DECLINE_VOLUME",
            title: "Decline & Cancel",
            options: [.destructive, .foreground]
        )
        let volumeCategory = UNNotificationCategory(
            identifier: NotificationCategory.volumeAdjustment.rawValue,
            actions: [approveAction, declineAction],
            intentIdentifiers: [],
            options: [.customDismissAction]
        )
        categories.insert(volumeCategory)

        UNUserNotificationCenter.current().setNotificationCategories(categories)
    }

    // MARK: - Device Token Registration

    /// Handle successful device token registration from APNs
    func handleDeviceToken(_ deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        print("APNs device token: \(token)")
        registerToken(token)
    }

    /// Handle failed device token registration
    func handleRegistrationError(_ error: Error) {
        print("Failed to register for remote notifications: \(error.localizedDescription)")
    }

    /// Register the device token with the backend
    func registerToken(_ token: String) {
        // Store token locally for re-registration after login
        UserDefaults.standard.set(token, forKey: "pushDeviceToken")
        sendTokenToBackend(token)
    }

    /// Re-send stored device token to backend (call after login)
    func reRegisterTokenIfNeeded() {
        guard let token = UserDefaults.standard.string(forKey: "pushDeviceToken"),
              !token.isEmpty else { return }
        sendTokenToBackend(token)
    }

    /// Send the push token to the backend API
    private func sendTokenToBackend(_ token: String) {
        guard let url = URL(string: "\(baseURL)/api/push/register-token") else {
            print("Invalid notification registration URL")
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "X-API-Key")

        // Attach auth token if available (from Keychain)
        if let authToken = KeychainHelper.loadString(forKey: "authToken") {
            request.addValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        }

        let body: [String: Any] = [
            "token": token,
            "platform": "ios",
            "app_type": "customer"
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("Error registering notification token: \(error.localizedDescription)")
                UserDefaults.standard.set(false, forKey: "pushTokenRegistered")
                return
            }

            guard let httpResponse = response as? HTTPURLResponse else {
                print("Invalid response from notification registration")
                return
            }

            if httpResponse.statusCode == 200 {
                UserDefaults.standard.set(true, forKey: "pushTokenRegistered")
                print("Notification token registered successfully")
            } else {
                UserDefaults.standard.set(false, forKey: "pushTokenRegistered")
                print("Notification token registration failed with status: \(httpResponse.statusCode)")
            }
        }.resume()
    }

    // MARK: - UNUserNotificationCenterDelegate

    /// Handle notifications received while the app is in the foreground
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        // Show notification as banner even when app is in foreground
        completionHandler([.banner, .badge, .sound])
    }

    /// Handle user tapping on a notification
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let actionIdentifier = response.actionIdentifier
        let categoryIdentifier = response.notification.request.content.categoryIdentifier
        let userInfo = response.notification.request.content.userInfo

        // Handle volume adjustment actions
        if actionIdentifier == "APPROVE_VOLUME" || actionIdentifier == "DECLINE_VOLUME" {
            if let jobId = userInfo["job_id"] as? String {
                if actionIdentifier == "APPROVE_VOLUME" {
                    Task {
                        try? await APIClient.shared.approveVolumeAdjustment(jobId: jobId)
                    }
                } else {
                    Task {
                        try? await APIClient.shared.declineVolumeAdjustment(jobId: jobId)
                    }
                }
            }
            completionHandler()
            return
        }

        // Handle job tracking categories (job_en_route, job_arrived, etc.)
        if categoryIdentifier.hasPrefix("job_") {
            if let jobId = userInfo["job_id"] as? String {
                NotificationCenter.default.post(
                    name: NSNotification.Name("openJobTracking"),
                    object: nil,
                    userInfo: ["job_id": jobId]
                )
            }
            completionHandler()
            return
        }

        // Try category identifier first
        if let category = NotificationCategory(rawValue: categoryIdentifier) {
            handleNotificationAction(for: category, userInfo: userInfo)
        } else if let type = userInfo["type"] as? String {
            // Fallback: map backend push data "type" field to a category
            switch type {
            case "job_update":
                // Handle job updates - could navigate to tracking if job is in progress
                if let jobId = userInfo["job_id"] as? String {
                    NotificationCenter.default.post(
                        name: NSNotification.Name("openJobTracking"),
                        object: nil,
                        userInfo: ["job_id": jobId]
                    )
                } else {
                    handleNotificationAction(for: .driverAssigned, userInfo: userInfo)
                }
            case "new_job":
                handleNotificationAction(for: .bookingConfirmed, userInfo: userInfo)
            case "volume_adjustment":
                handleNotificationAction(for: .volumeAdjustment, userInfo: userInfo)
            default:
                break
            }
        }

        completionHandler()
    }

    // MARK: - Notification Action Handling

    /// Process a notification tap based on its category
    private func handleNotificationAction(for category: NotificationCategory, userInfo: [AnyHashable: Any]) {
        DispatchQueue.main.async {
            self.pendingDeepLink = category
        }

        // Post NotificationCenter event for volume adjustment (for foreground refresh)
        if category == .volumeAdjustment {
            NotificationCenter.default.post(name: NSNotification.Name("volumeAdjustmentReceived"), object: nil)
        }
    }
}

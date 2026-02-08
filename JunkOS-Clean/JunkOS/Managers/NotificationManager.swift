//
//  NotificationManager.swift
//  JunkOS
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
    case driverEnRoute = "driver_en_route"
    case jobCompleted = "job_completed"

    var title: String {
        switch self {
        case .bookingConfirmed:
            return "Booking Confirmed"
        case .driverEnRoute:
            return "Driver En Route"
        case .jobCompleted:
            return "Job Completed"
        }
    }
}

// MARK: - NotificationManager

class NotificationManager: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    // MARK: - Published Properties
    @Published var isPermissionGranted = false

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
        var categories = Set<UNNotificationCategory>()

        for category in NotificationCategory.allCases {
            let notificationCategory = UNNotificationCategory(
                identifier: category.rawValue,
                actions: [],
                intentIdentifiers: [],
                options: []
            )
            categories.insert(notificationCategory)
        }

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
        guard let url = URL(string: "\(baseURL)/api/notifications/register") else {
            print("Invalid notification registration URL")
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(apiKey, forHTTPHeaderField: "X-API-Key")

        let body: [String: Any] = [
            "token": token,
            "platform": "ios"
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("Error registering notification token: \(error.localizedDescription)")
                return
            }

            guard let httpResponse = response as? HTTPURLResponse else {
                print("Invalid response from notification registration")
                return
            }

            if httpResponse.statusCode == 200 {
                print("Notification token registered successfully")
            } else {
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
        let categoryIdentifier = response.notification.request.content.categoryIdentifier
        let userInfo = response.notification.request.content.userInfo

        if let category = NotificationCategory(rawValue: categoryIdentifier) {
            handleNotificationAction(for: category, userInfo: userInfo)
        }

        completionHandler()
    }

    // MARK: - Notification Action Handling

    /// Process a notification tap based on its category
    private func handleNotificationAction(for category: NotificationCategory, userInfo: [AnyHashable: Any]) {
        switch category {
        case .bookingConfirmed:
            print("User tapped booking confirmed notification")
            // TODO: Navigate to booking details
        case .driverEnRoute:
            print("User tapped driver en route notification")
            // TODO: Navigate to live tracking view
        case .jobCompleted:
            print("User tapped job completed notification")
            // TODO: Navigate to job summary / review
        }
    }
}

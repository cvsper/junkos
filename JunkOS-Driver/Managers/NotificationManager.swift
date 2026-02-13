//
//  NotificationManager.swift
//  Umuve Pro
//
//  Push notification setup, permissions, token registration, and local alerts.
//

import UserNotifications
import UIKit

extension Notification.Name {
    static let didTapPushNotification = Notification.Name("didTapPushNotification")
}

final class NotificationManager: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationManager()

    /// Whether push permission has been granted
    private(set) var isPermissionGranted = false

    private override init() {
        super.init()
        UNUserNotificationCenter.current().delegate = self
    }

    // MARK: - Permission & Registration

    /// Request notification permission and register for remote notifications on success
    func requestPermission() {
        UNUserNotificationCenter.current().requestAuthorization(
            options: [.alert, .sound, .badge]
        ) { [weak self] granted, error in
            DispatchQueue.main.async {
                self?.isPermissionGranted = granted
                if granted {
                    UIApplication.shared.registerForRemoteNotifications()
                }
                if let error {
                    print("[Push] Permission error: \(error.localizedDescription)")
                }
            }
        }
    }

    // MARK: - Device Token Handling

    /// Called from AppDelegate when APNs returns a device token
    func handleDeviceToken(_ deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        print("[Push] APNs token: \(token)")
        registerTokenWithBackend(token)
    }

    /// Called from AppDelegate when APNs registration fails
    func handleRegistrationError(_ error: Error) {
        print("[Push] Registration failed: \(error.localizedDescription)")
    }

    /// Send the token to the backend
    private func registerTokenWithBackend(_ token: String) {
        // Store the token locally so AppState can re-register after login
        UserDefaults.standard.set(token, forKey: "pushDeviceToken")

        Task {
            do {
                _ = try await DriverAPIClient.shared.registerPushToken(token)
                UserDefaults.standard.set(true, forKey: "pushTokenRegistered")
                print("[Push] Token registered with backend")
            } catch {
                UserDefaults.standard.set(false, forKey: "pushTokenRegistered")
                print("[Push] Backend registration failed: \(error.localizedDescription)")
            }
        }
    }

    // MARK: - Re-register (e.g. after login)

    /// Re-send the stored device token to the backend (call after login)
    func reRegisterTokenIfNeeded() {
        guard let token = UserDefaults.standard.string(forKey: "pushDeviceToken"),
              !token.isEmpty else { return }
        registerTokenWithBackend(token)
    }

    // MARK: - Local Notifications

    func sendJobAlert(jobAddress: String, price: String) {
        let content = UNMutableNotificationContent()
        content.title = "New Job Nearby"
        content.body = "\(jobAddress) -- \(price)"
        content.sound = .default

        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(request)
    }

    // MARK: - UNUserNotificationCenterDelegate

    /// Show banner even when app is in foreground
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .badge, .sound])
    }

    /// Handle notification tap
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo
        print("[Push] Tapped notification: \(userInfo)")
        NotificationCenter.default.post(
            name: .didTapPushNotification,
            object: nil,
            userInfo: userInfo
        )
        completionHandler()
    }
}

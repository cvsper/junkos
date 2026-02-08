//
//  NotificationManager.swift
//  JunkOS Driver
//
//  Local push notifications for job alerts when app is backgrounded.
//

import UserNotifications

final class NotificationManager {
    static let shared = NotificationManager()

    private init() {}

    func requestPermission() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
    }

    func sendJobAlert(jobAddress: String, price: String) {
        let content = UNMutableNotificationContent()
        content.title = "New Job Nearby"
        content.body = "\(jobAddress) — \(price)"
        content.sound = .default

        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(request)
    }
}

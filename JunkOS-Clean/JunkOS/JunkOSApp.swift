//
//  JunkOSApp.swift
//  JunkOS
//
//  Main app entry point
//

import SwiftUI
import UserNotifications

// MARK: - App Delegate

class AppDelegate: NSObject, UIApplicationDelegate {
    /// Shared notification manager, set by JunkOSApp on launch
    static var notificationManager: NotificationManager?

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        AppDelegate.notificationManager?.handleDeviceToken(deviceToken)
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        AppDelegate.notificationManager?.handleRegistrationError(error)
    }
}

// MARK: - App Entry Point

@main
struct JunkOSApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var bookingData = BookingData()
    @StateObject private var authManager = AuthenticationManager()
    @ObservedObject private var notificationManager = NotificationManager.shared
    @State private var showingSplash = true
    @State private var didSetupNotifications = false

    var body: some Scene {
        WindowGroup {
            Group {
                if showingSplash {
                    EnhancedWelcomeView(showingSplash: $showingSplash)
                        .environmentObject(bookingData)
                        .environmentObject(authManager)
                        .environmentObject(notificationManager)
                } else if !authManager.isAuthenticated {
                    WelcomeAuthView()
                        .environmentObject(authManager)
                        .environmentObject(notificationManager)
                } else {
                    MainTabView()
                        .environmentObject(bookingData)
                        .environmentObject(authManager)
                        .environmentObject(notificationManager)
                        .onAppear {
                            notificationManager.requestPermission()
                        }
                }
            }
            .onAppear {
                if !didSetupNotifications {
                    didSetupNotifications = true
                    // Set the notification delegate and wire to app delegate
                    UNUserNotificationCenter.current().delegate = notificationManager
                    AppDelegate.notificationManager = notificationManager
                }
            }
        }
    }
}

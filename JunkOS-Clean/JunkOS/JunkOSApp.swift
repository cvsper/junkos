//
//  JunkOSApp.swift
//  Umuve
//
//  Main app entry point
//

import SwiftUI
import UserNotifications
import Network

// MARK: - App Delegate

class AppDelegate: NSObject, UIApplicationDelegate {
    /// Shared notification manager, set by UmuveApp on launch
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
struct UmuveApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var bookingData = BookingData()
    @StateObject private var authManager = AuthenticationManager()
    @ObservedObject private var notificationManager = NotificationManager.shared
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @State private var didSetupNotifications = false
    @State private var isOffline = false

    private let networkMonitor = NWPathMonitor()
    private let networkQueue = DispatchQueue(label: "NetworkMonitor")

    var body: some Scene {
        WindowGroup {
            Group {
                if !hasCompletedOnboarding {
                    OnboardingView()
                        .environmentObject(bookingData)
                        .environmentObject(authManager)
                } else if !authManager.isAuthenticated {
                    WelcomeAuthView()
                        .environmentObject(authManager)
                        .environmentObject(notificationManager)
                } else {
                    MainTabView()
                        .environmentObject(bookingData)
                        .environmentObject(authManager)
                        .environmentObject(notificationManager)
                        .overlay(
                            Group {
                                if isOffline {
                                    VStack {
                                        HStack {
                                            Image(systemName: "wifi.slash")
                                                .font(.system(size: 12))
                                            Text("You're offline")
                                                .font(UmuveTypography.captionFont)
                                        }
                                        .foregroundColor(.white)
                                        .padding(.horizontal, UmuveSpacing.normal)
                                        .padding(.vertical, UmuveSpacing.small)
                                        .background(Color.umuveTextMuted.opacity(0.9))
                                        .cornerRadius(UmuveRadius.md)
                                        .padding(.top, UmuveSpacing.normal)
                                        Spacer()
                                    }
                                    .transition(.move(edge: .top).combined(with: .opacity))
                                }
                            }
                        )
                        .onAppear {
                            notificationManager.requestPermission()
                            Task { await authManager.refreshTokenIfNeeded() }
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

                // Start network monitoring
                networkMonitor.pathUpdateHandler = { path in
                    DispatchQueue.main.async {
                        withAnimation {
                            isOffline = (path.status != .satisfied)
                        }
                    }
                }
                networkMonitor.start(queue: networkQueue)
            }
        }
    }
}

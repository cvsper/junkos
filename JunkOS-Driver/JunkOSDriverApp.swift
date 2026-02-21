//
//  JunkOSDriverApp.swift
//  Umuve Pro
//
//  Entry point: Splash -> Auth -> Registration -> Main tabs.
//  Includes AppDelegate for push notification token handling.
//

import SwiftUI
import UserNotifications

// MARK: - App Delegate

class DriverAppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        NotificationManager.shared.handleDeviceToken(deviceToken)
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        NotificationManager.shared.handleRegistrationError(error)
    }
}

// MARK: - App Entry Point

@main
struct UmuveProApp: App {
    @UIApplicationDelegateAdaptor(DriverAppDelegate.self) private var appDelegate
    @State private var appState = AppState()
    @State private var showingSplash = true
    @AppStorage("hasCompletedDriverOnboarding") private var hasCompletedOnboarding = false

    var body: some Scene {
        WindowGroup {
            Group {
                if showingSplash {
                    SplashView()
                        .onAppear {
                            DispatchQueue.main.asyncAfter(deadline: .now() + 1.8) {
                                withAnimation(.easeInOut(duration: 0.4)) {
                                    showingSplash = false
                                }
                            }
                        }
                } else if !hasCompletedOnboarding {
                    DriverOnboardingView()
                } else if !appState.auth.isAuthenticated {
                    DriverAuthView(appState: appState)
                } else if !appState.isRegistered && appState.selectedRole == nil {
                    // Role selection before registration
                    RoleSelectionView(appState: appState)
                        .task { await appState.loadContractorProfile() }
                } else if appState.isOperator {
                    // Operator registered -- redirect to web dashboard
                    OperatorWebRedirectView(appState: appState)
                } else if !appState.isRegistered {
                    ContractorRegistrationView(appState: appState)
                } else if !appState.hasCompletedStripeConnect {
                    StripeConnectOnboardingView(appState: appState)
                } else {
                    DriverTabView(appState: appState)
                        .task {
                            // CRITICAL: Load profile on app launch to ensure contractor ID is available
                            await appState.loadContractorProfile()

                            // If already online from previous session, restart socket with correct contractor ID
                            if appState.isOnline {
                                appState.socket.disconnect()
                                appState.startLocationTracking()
                            }
                        }
                        .onAppear {
                            // Request push notification permission once authenticated and registered
                            NotificationManager.shared.requestPermission()
                        }
                }
            }
            .preferredColorScheme(.light)
        }
    }
}

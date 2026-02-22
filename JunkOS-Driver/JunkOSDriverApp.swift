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
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            Group {
                if showingSplash {
                    SplashView()
                        .task {
                            // Load contractor profile during splash if authenticated
                            // This ensures isRegistered is accurate before showing screens
                            if appState.auth.isAuthenticated {
                                await appState.loadContractorProfile()
                            }

                            // Wait minimum 1.8 seconds for splash animation
                            try? await Task.sleep(nanoseconds: 1_800_000_000)

                            // Dismiss splash after profile is loaded
                            withAnimation(.easeInOut(duration: 0.4)) {
                                showingSplash = false
                            }
                        }
                } else if !hasCompletedOnboarding {
                    DriverOnboardingView()
                } else if !appState.auth.isAuthenticated {
                    DriverAuthView(appState: appState)
                } else if appState.isOperator {
                    // Operator registered -- redirect to web dashboard
                    OperatorWebRedirectView(appState: appState)
                } else if !appState.isRegistered && appState.selectedRole != nil {
                    // Role selected but not yet registered - show registration
                    ContractorRegistrationView(appState: appState)
                } else if !appState.isRegistered {
                    // Authenticated but no profile yet - start registration directly
                    // (Skip role selection for contractors - it's the default)
                    ContractorRegistrationView(appState: appState)
                } else if !appState.hasCompletedStripeConnect {
                    StripeConnectOnboardingView(appState: appState)
                } else {
                    DriverTabView(appState: appState)
                        .task {
                            // CRITICAL: Load profile on app launch to ensure contractor ID is available
                            await appState.loadContractorProfile()

                            // Don't auto-reconnect - let driver choose to go online manually
                        }
                        .onAppear {
                            // Request push notification permission once authenticated and registered
                            NotificationManager.shared.requestPermission()
                        }
                }
            }
            .preferredColorScheme(.light)
            .onChange(of: scenePhase) { oldPhase, newPhase in
                // Go offline when app goes to background or inactive
                if newPhase == .background || newPhase == .inactive {
                    if appState.isOnline {
                        print("📱 App backgrounding - going offline")
                        Task { await appState.toggleOnline() }
                    }
                }
            }
        }
    }
}

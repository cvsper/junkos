//
//  JunkOSDriverApp.swift
//  JunkOS Driver
//
//  Entry point: Splash → Auth → Registration → Main tabs.
//

import SwiftUI

@main
struct JunkOSDriverApp: App {
    @State private var appState = AppState()
    @State private var showingSplash = true

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
                } else if !appState.auth.isAuthenticated {
                    DriverAuthView(appState: appState)
                } else if !appState.isRegistered {
                    ContractorRegistrationView(appState: appState)
                        .task { await appState.loadContractorProfile() }
                } else {
                    DriverTabView(appState: appState)
                }
            }
            .preferredColorScheme(.light)
        }
    }
}

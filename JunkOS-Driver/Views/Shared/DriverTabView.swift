//
//  DriverTabView.swift
//  JunkOS Driver
//
//  Main 4-tab layout: Home, Jobs, Earnings, Profile.
//

import SwiftUI

struct DriverTabView: View {
    @Bindable var appState: AppState
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            DashboardView(appState: appState)
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }
                .tag(0)

            JobFeedView(appState: appState)
                .tabItem {
                    Label("Jobs", systemImage: "briefcase.fill")
                }
                .tag(1)

            EarningsView(appState: appState)
                .tabItem {
                    Label("Earnings", systemImage: "dollarsign.circle.fill")
                }
                .tag(2)

            ProfileSettingsView(appState: appState)
                .tabItem {
                    Label("Profile", systemImage: "person.fill")
                }
                .tag(3)
        }
        .tint(Color.driverPrimary)
    }
}

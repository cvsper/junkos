//
//  MainTabView.swift
//  Umuve
//
//  Main tab navigation — Home, Orders, Account.
//

import SwiftUI

struct MainTabView: View {
    @EnvironmentObject var bookingData: BookingData
    @EnvironmentObject var authManager: AuthenticationManager
    @EnvironmentObject var notificationManager: NotificationManager
    @State private var selectedTab = 0
    @State private var homeNavPath = NavigationPath()

    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack(path: $homeNavPath) {
                HomeView()
            }
            .tabItem {
                Label("Home", systemImage: "house.fill")
            }
            .tag(0)

            NavigationStack {
                OrdersView()
            }
            .tabItem {
                Label("Orders", systemImage: "list.bullet.clipboard")
            }
            .tag(1)

            NavigationStack {
                AccountView()
            }
            .tabItem {
                Label("Account", systemImage: "person.circle")
            }
            .tag(2)
        }
        .tint(.umuvePrimary)
        .onChange(of: bookingData.bookingCompleted) { completed in
            if completed {
                homeNavPath = NavigationPath()
                selectedTab = 1
                bookingData.bookingCompleted = false
                bookingData.reset()
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .switchToHomeTab)) { _ in
            selectedTab = 0
        }
        .onChange(of: notificationManager.pendingDeepLink) { deepLink in
            guard let deepLink else { return }
            switch deepLink {
            case .bookingConfirmed, .driverEnRoute, .jobCompleted:
                selectedTab = 1 // Orders tab
            case .driverAssigned:
                selectedTab = 1 // Orders tab
            case .volumeAdjustment:
                selectedTab = 1 // Orders tab
            }
            notificationManager.pendingDeepLink = nil
        }
    }
}

#Preview {
    MainTabView()
        .environmentObject(BookingData())
        .environmentObject(AuthenticationManager())
}

extension Notification.Name {
    /// Posted by leaf views (e.g. OrdersView's empty state CTA) to ask
    /// MainTabView to switch back to the Home tab. Avoids having to thread
    /// a selectedTab binding through every NavigationStack.
    static let switchToHomeTab = Notification.Name("com.goumuve.umuve.switchToHomeTab")
}

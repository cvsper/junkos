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
                // Pop the entire booking flow back to root
                homeNavPath = NavigationPath()
                // Switch to Orders tab
                selectedTab = 1
                // Reset the flag
                bookingData.bookingCompleted = false
                // Reset booking data for next booking
                bookingData.reset()
            }
        }
    }
}

#Preview {
    MainTabView()
        .environmentObject(BookingData())
        .environmentObject(AuthenticationManager())
}

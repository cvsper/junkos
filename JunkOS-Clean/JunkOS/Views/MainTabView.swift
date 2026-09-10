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
    /// App-wide reconciliation of a checkout that was interrupted after the
    /// card was charged (audit F05).
    @ObservedObject private var checkoutRecovery = CheckoutRecoveryService.shared
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
        // On launch: if the last session died between "card charged" and
        // "booking confirmed", finish it in the background rather than
        // leaving the customer paid with nothing to show for it.
        .task {
            await checkoutRecovery.resumeIfNeeded()
        }
        .safeAreaInset(edge: .top) {
            checkoutRecoveryBanner
        }
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

    // MARK: - Checkout Recovery Banner

    /// Never says "payment failed": by the time this shows, Stripe has already
    /// accepted the charge. It either reports progress, confirms success, or
    /// hands over a reference for support (audit F05).
    @ViewBuilder
    private var checkoutRecoveryBanner: some View {
        switch checkoutRecovery.state {
        case .idle:
            EmptyView()

        case .finishing:
            recoveryBanner(
                icon: nil,
                tint: .umuvePrimary,
                title: "Finishing your booking\u{2026}",
                detail: "Your payment went through. We're confirming the details."
            )

        case .succeeded:
            recoveryBanner(
                icon: "checkmark.circle.fill",
                tint: .green,
                title: "Booking confirmed",
                detail: "Your payment is confirmed and your pickup is scheduled.",
                dismissable: true
            )

        case .needsSupport(let jobId, _):
            recoveryBanner(
                icon: "exclamationmark.circle.fill",
                tint: .orange,
                title: "Payment received",
                detail: "We're still confirming booking \(String(jobId.prefix(8)).uppercased()). "
                    + "Contact support@goumuve.com with that reference if you don't hear from us shortly.",
                dismissable: true
            )
        }
    }

    private func recoveryBanner(
        icon: String?,
        tint: Color,
        title: String,
        detail: String,
        dismissable: Bool = false
    ) -> some View {
        HStack(alignment: .top, spacing: UmuveSpacing.small) {
            if let icon {
                Image(systemName: icon)
                    .foregroundColor(tint)
                    .font(.system(size: 16, weight: .semibold))
            } else {
                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: tint))
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(UmuveTypography.bodySmallFont.weight(.semibold))
                    .foregroundColor(.umuveText)
                Text(detail)
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextMuted)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 0)

            if dismissable {
                Button {
                    checkoutRecovery.acknowledge()
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(.umuveTextMuted)
                }
                .accessibilityLabel("Dismiss")
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        .shadow(color: .black.opacity(0.08), radius: 6, x: 0, y: 2)
        .padding(.horizontal, UmuveSpacing.normal)
        .padding(.bottom, UmuveSpacing.small)
        .accessibilityElement(children: .combine)
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

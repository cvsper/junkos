//
//  OrdersView.swift
//  Umuve
//
//  View user's booking history.
//

import SwiftUI

struct OrdersView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @State private var bookings: [BookingResponse] = []
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        ScrollView {
            VStack(spacing: UmuveSpacing.large) {
                // Header
                VStack(spacing: UmuveSpacing.small) {
                    Text("My Bookings")
                        .font(UmuveTypography.h1Font)
                        .foregroundColor(.umuveText)

                    if let user = authManager.currentUser {
                        Text("Hi, \(user.name ?? "there")!")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveTextMuted)

                        if user.id == "guest" {
                            HStack(spacing: 8) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundColor(.umuveWarning)
                                Text("Guest bookings aren't saved")
                                    .font(UmuveTypography.bodySmallFont)
                                    .foregroundColor(.umuveWarning)
                            }
                            .padding(.horizontal, UmuveSpacing.normal)
                            .padding(.vertical, UmuveSpacing.small)
                            .background(Color.umuveWarning.opacity(0.1))
                            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
                        }
                    }
                }
                .padding(.top, UmuveSpacing.xlarge)

                // Content
                if isLoading {
                    ProgressView()
                        .tint(.umuvePrimary)
                        .padding(UmuveSpacing.huge)
                } else if bookings.isEmpty {
                    emptyState
                } else {
                    bookingsList
                }
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.bottom, UmuveSpacing.xxlarge)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.umuveBackground.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            loadBookings()
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.willEnterForegroundNotification)) { _ in
            loadBookings()
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("volumeAdjustmentReceived"))) { _ in
            Task { loadBookings() }
        }
        .onReceive(NotificationCenter.default.publisher(for: NSNotification.Name("jobStatusUpdated"))) { _ in
            loadBookings()
        }
    }

    // MARK: - Empty State
    private var emptyState: some View {
        VStack(spacing: UmuveSpacing.large) {
            ZStack {
                Circle()
                    .fill(Color.umuvePrimary.opacity(0.1))
                    .frame(width: 120, height: 120)

                Image(systemName: "calendar.badge.plus")
                    .font(.system(size: 48))
                    .foregroundColor(.umuvePrimary)
            }
            .padding(.top, UmuveSpacing.xxlarge)

            Text("No bookings yet")
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)

            Text("Book your first junk removal service to get started!")
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveTextMuted)
                .multilineTextAlignment(.center)
                .padding(.horizontal, UmuveSpacing.xlarge)
        }
        .padding(.vertical, UmuveSpacing.xxlarge)
    }

    // MARK: - Bookings List
    private var bookingsList: some View {
        VStack(spacing: UmuveSpacing.medium) {
            ForEach(bookings, id: \.bookingId) { booking in
                BookingCard(booking: booking, onRefresh: loadBookings)
            }
        }
    }

    // MARK: - API Call
    private func loadBookings() {
        guard let user = authManager.currentUser,
              let email = user.email,
              user.id != "guest" else {
            isLoading = false
            return
        }

        Task {
            do {
                let results = try await APIClient.shared.getCustomerBookings(email: email)
                await MainActor.run {
                    bookings = results
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    errorMessage = error.localizedDescription
                    print("Error loading bookings: \(error)")
                }
            }
        }
    }
}

// MARK: - Booking Card
struct BookingCard: View {
    let booking: BookingResponse
    let onRefresh: () -> Void

    private var isTrackable: Bool {
        let status = booking.status?.lowercased() ?? ""
        return ["en_route", "arrived", "started"].contains(status)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.medium) {
            // Status badge + booking ID
            HStack {
                statusBadge
                Spacer()
                Text("#\(String(booking.bookingId.prefix(8)))")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.umuveTextMuted)
            }

            // Operator delegation badge
            if booking.isDelegated {
                operatorBadge
            }

            // Driver info (when assigned)
            if let driverName = booking.driverName, !driverName.isEmpty {
                HStack(spacing: UmuveSpacing.small) {
                    Image(systemName: "person.circle.fill")
                        .font(.system(size: 14))
                        .foregroundColor(.umuveSuccess)
                    Text("Driver: \(driverName)")
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveText)
                }
            }

            // Service info
            if !booking.services.isEmpty {
                Text(booking.services.map { $0.name }.joined(separator: ", "))
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.umuveText)
            }

            // Date and time
            HStack(spacing: UmuveSpacing.small) {
                Image(systemName: "calendar")
                    .font(.system(size: 14))
                    .foregroundColor(.umuveTextMuted)
                Text(formatDate(booking.scheduledDatetime))
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
            }

            // Total
            HStack {
                Spacer()
                Text("$\(String(format: "%.2f", booking.estimatedPrice))")
                    .font(UmuveTypography.priceFont)
                    .foregroundColor(.umuvePrimary)
            }

            // Volume adjustment pending banner
            if booking.volumeAdjustmentProposed == true {
                VStack(spacing: 8) {
                    HStack(spacing: 6) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundStyle(.orange)
                        Text("Price Adjustment Required")
                            .font(.subheadline.weight(.semibold))
                    }

                    if let adjustedPrice = booking.adjustedPrice {
                        Text("New price: $\(adjustedPrice, specifier: "%.2f")")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }

                    HStack(spacing: 12) {
                        Button {
                            Task {
                                try? await APIClient.shared.approveVolumeAdjustment(jobId: booking.bookingId)
                                // Refresh bookings after action
                                await MainActor.run {
                                    onRefresh()
                                }
                            }
                        } label: {
                            Text("Approve")
                                .font(.subheadline.weight(.medium))
                                .foregroundStyle(.white)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(Color.green)
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                        }

                        Button {
                            Task {
                                try? await APIClient.shared.declineVolumeAdjustment(jobId: booking.bookingId)
                                // Refresh bookings after action
                                await MainActor.run {
                                    onRefresh()
                                }
                            }
                        } label: {
                            Text("Decline")
                                .font(.subheadline.weight(.medium))
                                .foregroundStyle(.white)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(Color.red)
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                    }
                }
                .padding(12)
                .background(Color.orange.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            // Track Driver button
            if isTrackable {
                NavigationLink(destination: JobTrackingView(
                    jobId: booking.bookingId,
                    jobAddress: booking.address ?? "Pickup location",
                    driverName: booking.driverName
                )) {
                    HStack {
                        Image(systemName: "location.fill")
                        Text("Track Driver")
                    }
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, UmuveSpacing.medium)
                    .background(Color.umuvePrimary)
                    .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
                }
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }

    private var statusBadge: some View {
        // Use job status if available, otherwise fall back to confirmation string
        let resolvedStatus = booking.status?.lowercased() ?? booking.confirmation.lowercased()
        let (text, color): (String, Color) = {
            if resolvedStatus.contains("completed") { return ("Completed", Color.umuveSuccess) }
            if resolvedStatus.contains("en_route") { return ("En Route", Color.umuveInfo) }
            if resolvedStatus.contains("arrived") { return ("Driver Arrived", Color.umuveSuccess) }
            if resolvedStatus.contains("started") { return ("In Progress", Color.umuveInfo) }
            if resolvedStatus.contains("in_progress") || resolvedStatus.contains("in progress") { return ("In Progress", Color.umuveInfo) }
            if resolvedStatus.contains("accepted") { return ("Driver Assigned", Color.umuveSuccess) }
            if resolvedStatus.contains("assigned") { return ("Assigned", Color.categoryPurple) }
            if resolvedStatus.contains("delegating") { return ("Delegating", Color.categoryOrange) }
            if resolvedStatus.contains("confirmed") { return ("Confirmed", Color.umuvePrimary) }
            if resolvedStatus.contains("cancelled") || resolvedStatus.contains("canceled") { return ("Cancelled", Color.umuveError) }
            if resolvedStatus.contains("pending") { return ("Pending", Color.umuveWarning) }
            return ("Pending", Color.umuveWarning)
        }()
        return Text(text)
            .font(UmuveTypography.captionFont)
            .foregroundColor(.white)
            .padding(.horizontal, UmuveSpacing.medium)
            .padding(.vertical, UmuveSpacing.tiny)
            .background(Capsule().fill(color))
    }

    // MARK: - Operator Badge
    private var operatorBadge: some View {
        HStack(spacing: UmuveSpacing.small) {
            Image(systemName: "person.badge.shield.checkmark.fill")
                .font(.system(size: 13))
                .foregroundColor(.categoryPurple)

            Text("Managed by \(booking.operatorName ?? "Operator")")
                .font(UmuveTypography.captionFont)
                .foregroundColor(.categoryPurple)

            if let delegatedAt = booking.delegatedAt {
                Text("· \(formatDelegatedDate(delegatedAt))")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextTertiary)
            }
        }
        .padding(.horizontal, UmuveSpacing.medium)
        .padding(.vertical, UmuveSpacing.tiny + 2)
        .background(Color.categoryPurple.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
    }

    private func formatDate(_ dateString: String) -> String {
        let inputFormatter = DateFormatter()
        inputFormatter.dateFormat = "yyyy-MM-dd HH:mm"
        if let date = inputFormatter.date(from: dateString) {
            let outputFormatter = DateFormatter()
            outputFormatter.dateStyle = .medium
            outputFormatter.timeStyle = .short
            return outputFormatter.string(from: date)
        }
        // Fallback: try ISO 8601 format
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: dateString) {
            let outputFormatter = DateFormatter()
            outputFormatter.dateStyle = .medium
            outputFormatter.timeStyle = .short
            return outputFormatter.string(from: date)
        }
        // Fallback: try date-only format
        inputFormatter.dateFormat = "yyyy-MM-dd"
        if let date = inputFormatter.date(from: dateString) {
            let outputFormatter = DateFormatter()
            outputFormatter.dateStyle = .medium
            return outputFormatter.string(from: date)
        }
        return dateString
    }

    private func formatDelegatedDate(_ dateString: String) -> String {
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = isoFormatter.date(from: dateString) {
            let outputFormatter = DateFormatter()
            outputFormatter.dateStyle = .short
            outputFormatter.timeStyle = .short
            return outputFormatter.string(from: date)
        }
        // Fallback: try without fractional seconds
        isoFormatter.formatOptions = [.withInternetDateTime]
        if let date = isoFormatter.date(from: dateString) {
            let outputFormatter = DateFormatter()
            outputFormatter.dateStyle = .short
            outputFormatter.timeStyle = .short
            return outputFormatter.string(from: date)
        }
        return dateString
    }
}

#Preview {
    NavigationStack {
        OrdersView()
            .environmentObject(AuthenticationManager())
    }
}

#Preview("Booking Card") {
    BookingCard(
        booking: BookingResponse(
            from: try! JSONDecoder().decode(
                BookingResponse.self,
                from: """
                {
                    "id": "test-123",
                    "confirmation": "confirmed",
                    "estimated_price": 150.0,
                    "scheduled_datetime": "2026-02-20 14:00",
                    "status": "pending",
                    "services": []
                }
                """.data(using: .utf8)!
            )
        ),
        onRefresh: {}
    )
    .padding()
}

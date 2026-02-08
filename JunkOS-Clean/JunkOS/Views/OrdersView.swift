//
//  OrdersView.swift
//  JunkOS
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
            VStack(spacing: JunkSpacing.large) {
                // Header
                VStack(spacing: JunkSpacing.small) {
                    Text("My Bookings")
                        .font(JunkTypography.h1Font)
                        .foregroundColor(.junkText)

                    if let user = authManager.currentUser {
                        Text("Hi, \(user.name ?? "there")!")
                            .font(JunkTypography.bodyFont)
                            .foregroundColor(.junkTextMuted)

                        if user.id == "guest" {
                            HStack(spacing: 8) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundColor(.junkWarning)
                                Text("Guest bookings aren't saved")
                                    .font(JunkTypography.bodySmallFont)
                                    .foregroundColor(.junkWarning)
                            }
                            .padding(.horizontal, JunkSpacing.normal)
                            .padding(.vertical, JunkSpacing.small)
                            .background(Color.junkWarning.opacity(0.1))
                            .clipShape(RoundedRectangle(cornerRadius: JunkRadius.sm))
                        }
                    }
                }
                .padding(.top, JunkSpacing.xlarge)

                // Content
                if isLoading {
                    ProgressView()
                        .tint(.junkPrimary)
                        .padding(JunkSpacing.huge)
                } else if bookings.isEmpty {
                    emptyState
                } else {
                    bookingsList
                }
            }
            .padding(.horizontal, JunkSpacing.large)
            .padding(.bottom, JunkSpacing.xxlarge)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.junkBackground.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            loadBookings()
        }
    }

    // MARK: - Empty State
    private var emptyState: some View {
        VStack(spacing: JunkSpacing.large) {
            ZStack {
                Circle()
                    .fill(Color.junkPrimary.opacity(0.1))
                    .frame(width: 120, height: 120)

                Image(systemName: "calendar.badge.plus")
                    .font(.system(size: 48))
                    .foregroundColor(.junkPrimary)
            }
            .padding(.top, JunkSpacing.xxlarge)

            Text("No bookings yet")
                .font(JunkTypography.h2Font)
                .foregroundColor(.junkText)

            Text("Book your first junk removal service to get started!")
                .font(JunkTypography.bodyFont)
                .foregroundColor(.junkTextMuted)
                .multilineTextAlignment(.center)
                .padding(.horizontal, JunkSpacing.xlarge)
        }
        .padding(.vertical, JunkSpacing.xxlarge)
    }

    // MARK: - Bookings List
    private var bookingsList: some View {
        VStack(spacing: JunkSpacing.medium) {
            ForEach(bookings, id: \.bookingId) { booking in
                BookingCard(booking: booking)
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

    var body: some View {
        VStack(alignment: .leading, spacing: JunkSpacing.medium) {
            // Status badge + booking ID
            HStack {
                statusBadge
                Spacer()
                Text("#\(booking.bookingId)")
                    .font(JunkTypography.captionFont)
                    .foregroundColor(.junkTextMuted)
            }

            // Service info
            Text(booking.services.map { $0.name }.joined(separator: ", "))
                .font(JunkTypography.h3Font)
                .foregroundColor(.junkText)

            // Date and time
            HStack(spacing: JunkSpacing.small) {
                Image(systemName: "calendar")
                    .font(.system(size: 14))
                    .foregroundColor(.junkTextMuted)
                Text(formatDate(booking.scheduledDatetime))
                    .font(JunkTypography.bodySmallFont)
                    .foregroundColor(.junkTextMuted)
            }

            // Total
            HStack {
                Spacer()
                Text("$\(String(format: "%.2f", booking.estimatedPrice))")
                    .font(JunkTypography.priceFont)
                    .foregroundColor(.junkPrimary)
            }
        }
        .padding(JunkSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }

    private var statusBadge: some View {
        let status = booking.confirmation.lowercased()
        let (text, color): (String, Color) = {
            if status.contains("confirmed") { return ("Confirmed", Color.junkPrimary) }
            if status.contains("completed") { return ("Completed", Color.junkSuccess) }
            if status.contains("cancelled") { return ("Cancelled", Color.junkError) }
            return ("Pending", Color.junkWarning)
        }()
        return Text(text)
            .font(JunkTypography.captionFont)
            .foregroundColor(.white)
            .padding(.horizontal, JunkSpacing.medium)
            .padding(.vertical, JunkSpacing.tiny)
            .background(Capsule().fill(color))
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
        // Fallback: try ISO format
        inputFormatter.dateFormat = "yyyy-MM-dd"
        if let date = inputFormatter.date(from: dateString) {
            let outputFormatter = DateFormatter()
            outputFormatter.dateStyle = .medium
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

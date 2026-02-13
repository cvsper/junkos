//
//  BookingSuccessView.swift
//  Umuve
//
//  Post-payment confirmation screen showing booking details
//  and "What happens next?" steps.
//

import SwiftUI

struct BookingSuccessView: View {
    @EnvironmentObject var bookingData: BookingData
    @State private var elementsVisible = false

    let customerEmail: String
    let totalAmount: Double
    let scheduledDate: String
    let scheduledTime: String

    var body: some View {
        ScrollView {
            VStack(spacing: UmuveSpacing.xxlarge) {
                // Success icon
                VStack(spacing: UmuveSpacing.normal) {
                    ZStack {
                        Circle()
                            .fill(Color.umuveSuccess.opacity(0.12))
                            .frame(width: 88, height: 88)

                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 52))
                            .foregroundStyle(Color.umuveSuccess)
                    }

                    Text("Your pickup is booked.")
                        .font(UmuveTypography.h2Font)
                        .foregroundStyle(Color.umuveText)
                        .multilineTextAlignment(.center)

                    Text("This is a no-obligation service — you'll know the exact cost before we start.")
                        .font(UmuveTypography.bodyFont)
                        .foregroundStyle(Color.umuveTextMuted)
                        .multilineTextAlignment(.center)

                    HStack(spacing: UmuveSpacing.tiny) {
                        Image(systemName: "envelope.fill")
                            .font(.system(size: 12))
                            .foregroundStyle(Color.umuveTextTertiary)
                        Text("Confirmation sent to **\(customerEmail)**")
                            .font(UmuveTypography.captionFont)
                            .foregroundStyle(Color.umuveTextMuted)
                    }
                }
                .staggeredEntrance(index: 0, isVisible: elementsVisible)

                // Booking summary card
                UmuveCard {
                    VStack(spacing: UmuveSpacing.normal) {
                        HStack {
                            Image(systemName: "calendar.badge.checkmark")
                                .foregroundStyle(Color.umuvePrimary)
                            Text("Booking Details")
                                .font(UmuveTypography.h3Font)
                                .foregroundStyle(Color.umuveText)
                            Spacer()
                        }

                        Divider()

                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Date")
                                    .font(UmuveTypography.captionFont)
                                    .foregroundStyle(Color.umuveTextMuted)
                                Text(scheduledDate)
                                    .font(UmuveTypography.bodyFont.weight(.medium))
                                    .foregroundStyle(Color.umuveText)
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: 2) {
                                Text("Time")
                                    .font(UmuveTypography.captionFont)
                                    .foregroundStyle(Color.umuveTextMuted)
                                Text(scheduledTime)
                                    .font(UmuveTypography.bodyFont.weight(.medium))
                                    .foregroundStyle(Color.umuveText)
                            }
                        }

                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Amount")
                                    .font(UmuveTypography.captionFont)
                                    .foregroundStyle(Color.umuveTextMuted)
                                Text(String(format: "$%.2f", totalAmount))
                                    .font(UmuveTypography.bodyFont.weight(.medium))
                                    .foregroundStyle(Color.umuveCTA)
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: 2) {
                                Text("Address")
                                    .font(UmuveTypography.captionFont)
                                    .foregroundStyle(Color.umuveTextMuted)
                                Text(bookingData.address.street.isEmpty ? "Your address" : bookingData.address.street)
                                    .font(UmuveTypography.bodyFont.weight(.medium))
                                    .foregroundStyle(Color.umuveText)
                                    .lineLimit(1)
                            }
                        }
                    }
                    .padding(UmuveSpacing.large)
                }
                .staggeredEntrance(index: 1, isVisible: elementsVisible)

                // What happens next
                UmuveCard {
                    VStack(alignment: .leading, spacing: UmuveSpacing.large) {
                        HStack {
                            Image(systemName: "arrow.right.circle.fill")
                                .foregroundStyle(Color.umuvePrimary)
                            Text("What happens next?")
                                .font(UmuveTypography.h3Font)
                                .foregroundStyle(Color.umuveText)
                            Spacer()
                        }

                        // Step 1
                        HStack(alignment: .top, spacing: UmuveSpacing.normal) {
                            ZStack {
                                Circle()
                                    .fill(Color.umuvePrimary.opacity(0.1))
                                    .frame(width: 36, height: 36)
                                Text("1")
                                    .font(UmuveTypography.bodyFont.weight(.bold))
                                    .foregroundStyle(Color.umuvePrimary)
                            }

                            VStack(alignment: .leading, spacing: 2) {
                                Text("We'll call to confirm")
                                    .font(UmuveTypography.bodyFont.weight(.semibold))
                                    .foregroundStyle(Color.umuveText)
                                Text("You'll get a call 15–30 minutes before your scheduled window. We'll confirm timing and go over details.")
                                    .font(UmuveTypography.bodySmallFont)
                                    .foregroundStyle(Color.umuveTextMuted)
                            }
                        }

                        // Step 2
                        HStack(alignment: .top, spacing: UmuveSpacing.normal) {
                            ZStack {
                                Circle()
                                    .fill(Color.umuvePrimary.opacity(0.1))
                                    .frame(width: 36, height: 36)
                                Text("2")
                                    .font(UmuveTypography.bodyFont.weight(.bold))
                                    .foregroundStyle(Color.umuvePrimary)
                            }

                            VStack(alignment: .leading, spacing: 2) {
                                Text("We assess and give an exact price")
                                    .font(UmuveTypography.bodyFont.weight(.semibold))
                                    .foregroundStyle(Color.umuveText)
                                Text("Our crew will look at everything on-site and provide an all-inclusive price. No obligation — if it doesn't work, there's no charge.")
                                    .font(UmuveTypography.bodySmallFont)
                                    .foregroundStyle(Color.umuveTextMuted)
                            }
                        }

                        // Step 3
                        HStack(alignment: .top, spacing: UmuveSpacing.normal) {
                            ZStack {
                                Circle()
                                    .fill(Color.umuvePrimary.opacity(0.1))
                                    .frame(width: 36, height: 36)
                                Text("3")
                                    .font(UmuveTypography.bodyFont.weight(.bold))
                                    .foregroundStyle(Color.umuvePrimary)
                            }

                            VStack(alignment: .leading, spacing: 2) {
                                Text("We take care of everything")
                                    .font(UmuveTypography.bodyFont.weight(.semibold))
                                    .foregroundStyle(Color.umuveText)
                                Text("Once you give the go-ahead, we remove your items, sweep up the area, and you're done. It's that easy.")
                                    .font(UmuveTypography.bodySmallFont)
                                    .foregroundStyle(Color.umuveTextMuted)
                            }
                        }
                    }
                    .padding(UmuveSpacing.large)
                }
                .staggeredEntrance(index: 2, isVisible: elementsVisible)

                // Reminder note
                HStack(spacing: UmuveSpacing.small) {
                    Image(systemName: "bell.badge.fill")
                        .font(.system(size: 14))
                        .foregroundStyle(Color.umuvePrimary)
                    Text("We'll send a reminder **24 hours before** your appointment.")
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundStyle(Color.umuveTextMuted)
                }
                .padding(UmuveSpacing.normal)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.umuvePrimary.opacity(0.06))
                .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
                .staggeredEntrance(index: 3, isVisible: elementsVisible)

                // Done button
                Button {
                    HapticManager.shared.mediumTap()
                    bookingData.bookingCompleted = true
                } label: {
                    Text("Done")
                }
                .buttonStyle(UmuvePrimaryButtonStyle())
                .staggeredEntrance(index: 4, isVisible: elementsVisible)

                Spacer().frame(height: UmuveSpacing.large)
            }
            .padding(UmuveSpacing.large)
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .navigationBarBackButtonHidden(true)
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            withAnimation(AnimationConstants.smoothSpring) {
                elementsVisible = true
            }
            HapticManager.shared.success()
        }
    }
}

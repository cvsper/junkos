//
//  BookingSuccessView.swift
//  JunkOS
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
            VStack(spacing: JunkSpacing.xxlarge) {
                // Success icon
                VStack(spacing: JunkSpacing.normal) {
                    ZStack {
                        Circle()
                            .fill(Color.junkSuccess.opacity(0.12))
                            .frame(width: 88, height: 88)

                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 52))
                            .foregroundStyle(Color.junkSuccess)
                    }

                    Text("Your pickup is booked.")
                        .font(JunkTypography.h2Font)
                        .foregroundStyle(Color.junkText)
                        .multilineTextAlignment(.center)

                    Text("This is a no-obligation service — you'll know the exact cost before we start.")
                        .font(JunkTypography.bodyFont)
                        .foregroundStyle(Color.junkTextMuted)
                        .multilineTextAlignment(.center)

                    HStack(spacing: JunkSpacing.tiny) {
                        Image(systemName: "envelope.fill")
                            .font(.system(size: 12))
                            .foregroundStyle(Color.junkTextTertiary)
                        Text("Confirmation sent to **\(customerEmail)**")
                            .font(JunkTypography.captionFont)
                            .foregroundStyle(Color.junkTextMuted)
                    }
                }
                .staggeredEntrance(index: 0, isVisible: elementsVisible)

                // Booking summary card
                JunkCard {
                    VStack(spacing: JunkSpacing.normal) {
                        HStack {
                            Image(systemName: "calendar.badge.checkmark")
                                .foregroundStyle(Color.junkPrimary)
                            Text("Booking Details")
                                .font(JunkTypography.h3Font)
                                .foregroundStyle(Color.junkText)
                            Spacer()
                        }

                        Divider()

                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Date")
                                    .font(JunkTypography.captionFont)
                                    .foregroundStyle(Color.junkTextMuted)
                                Text(scheduledDate)
                                    .font(JunkTypography.bodyFont.weight(.medium))
                                    .foregroundStyle(Color.junkText)
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: 2) {
                                Text("Time")
                                    .font(JunkTypography.captionFont)
                                    .foregroundStyle(Color.junkTextMuted)
                                Text(scheduledTime)
                                    .font(JunkTypography.bodyFont.weight(.medium))
                                    .foregroundStyle(Color.junkText)
                            }
                        }

                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Amount")
                                    .font(JunkTypography.captionFont)
                                    .foregroundStyle(Color.junkTextMuted)
                                Text(String(format: "$%.2f", totalAmount))
                                    .font(JunkTypography.bodyFont.weight(.medium))
                                    .foregroundStyle(Color.junkCTA)
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: 2) {
                                Text("Address")
                                    .font(JunkTypography.captionFont)
                                    .foregroundStyle(Color.junkTextMuted)
                                Text(bookingData.address.street.isEmpty ? "Your address" : bookingData.address.street)
                                    .font(JunkTypography.bodyFont.weight(.medium))
                                    .foregroundStyle(Color.junkText)
                                    .lineLimit(1)
                            }
                        }
                    }
                    .padding(JunkSpacing.large)
                }
                .staggeredEntrance(index: 1, isVisible: elementsVisible)

                // What happens next
                JunkCard {
                    VStack(alignment: .leading, spacing: JunkSpacing.large) {
                        HStack {
                            Image(systemName: "arrow.right.circle.fill")
                                .foregroundStyle(Color.junkPrimary)
                            Text("What happens next?")
                                .font(JunkTypography.h3Font)
                                .foregroundStyle(Color.junkText)
                            Spacer()
                        }

                        // Step 1
                        HStack(alignment: .top, spacing: JunkSpacing.normal) {
                            ZStack {
                                Circle()
                                    .fill(Color.junkPrimary.opacity(0.1))
                                    .frame(width: 36, height: 36)
                                Text("1")
                                    .font(JunkTypography.bodyFont.weight(.bold))
                                    .foregroundStyle(Color.junkPrimary)
                            }

                            VStack(alignment: .leading, spacing: 2) {
                                Text("We'll call to confirm")
                                    .font(JunkTypography.bodyFont.weight(.semibold))
                                    .foregroundStyle(Color.junkText)
                                Text("You'll get a call 15–30 minutes before your scheduled window. We'll confirm timing and go over details.")
                                    .font(JunkTypography.bodySmallFont)
                                    .foregroundStyle(Color.junkTextMuted)
                            }
                        }

                        // Step 2
                        HStack(alignment: .top, spacing: JunkSpacing.normal) {
                            ZStack {
                                Circle()
                                    .fill(Color.junkPrimary.opacity(0.1))
                                    .frame(width: 36, height: 36)
                                Text("2")
                                    .font(JunkTypography.bodyFont.weight(.bold))
                                    .foregroundStyle(Color.junkPrimary)
                            }

                            VStack(alignment: .leading, spacing: 2) {
                                Text("We assess and give an exact price")
                                    .font(JunkTypography.bodyFont.weight(.semibold))
                                    .foregroundStyle(Color.junkText)
                                Text("Our crew will look at everything on-site and provide an all-inclusive price. No obligation — if it doesn't work, there's no charge.")
                                    .font(JunkTypography.bodySmallFont)
                                    .foregroundStyle(Color.junkTextMuted)
                            }
                        }

                        // Step 3
                        HStack(alignment: .top, spacing: JunkSpacing.normal) {
                            ZStack {
                                Circle()
                                    .fill(Color.junkPrimary.opacity(0.1))
                                    .frame(width: 36, height: 36)
                                Text("3")
                                    .font(JunkTypography.bodyFont.weight(.bold))
                                    .foregroundStyle(Color.junkPrimary)
                            }

                            VStack(alignment: .leading, spacing: 2) {
                                Text("We take care of everything")
                                    .font(JunkTypography.bodyFont.weight(.semibold))
                                    .foregroundStyle(Color.junkText)
                                Text("Once you give the go-ahead, we remove your items, sweep up the area, and you're done. It's that easy.")
                                    .font(JunkTypography.bodySmallFont)
                                    .foregroundStyle(Color.junkTextMuted)
                            }
                        }
                    }
                    .padding(JunkSpacing.large)
                }
                .staggeredEntrance(index: 2, isVisible: elementsVisible)

                // Reminder note
                HStack(spacing: JunkSpacing.small) {
                    Image(systemName: "bell.badge.fill")
                        .font(.system(size: 14))
                        .foregroundStyle(Color.junkPrimary)
                    Text("We'll send a reminder **24 hours before** your appointment.")
                        .font(JunkTypography.bodySmallFont)
                        .foregroundStyle(Color.junkTextMuted)
                }
                .padding(JunkSpacing.normal)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.junkPrimary.opacity(0.06))
                .clipShape(RoundedRectangle(cornerRadius: JunkRadius.md))
                .staggeredEntrance(index: 3, isVisible: elementsVisible)

                // Done button
                Button {
                    HapticManager.shared.mediumTap()
                    bookingData.bookingCompleted = true
                } label: {
                    Text("Done")
                }
                .buttonStyle(JunkPrimaryButtonStyle())
                .staggeredEntrance(index: 4, isVisible: elementsVisible)

                Spacer().frame(height: JunkSpacing.large)
            }
            .padding(JunkSpacing.large)
        }
        .background(Color.junkBackground.ignoresSafeArea())
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

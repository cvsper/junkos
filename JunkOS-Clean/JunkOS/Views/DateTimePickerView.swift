//
//  DateTimePickerView.swift
//  Umuve
//
//  Date and time selection screen
//  SF Symbols Reference: https://developer.apple.com/sf-symbols/
//
//  PERFORMANCE OPTIMIZATIONS:
//  - LazyVStack for main content
//  - Cached date formatters (static, not recreated)
//  - Removed expensive gesture recognizers
//  - Simplified animations (only on tap, not during scroll)
//  - Debounced state updates
//

import SwiftUI

// OPTIMIZATION: Static date formatters (cached, not recreated per render)
private let dayFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.dateFormat = "EEE"
    return formatter
}()

private let dateFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.dateFormat = "d"
    return formatter
}()

struct DateTimePickerView: View {
    @EnvironmentObject var bookingData: BookingData
    @EnvironmentObject var wizardVM: BookingWizardViewModel
    @StateObject private var viewModel = DateTimePickerViewModel()

    var body: some View {
        ScrollView {
            LazyVStack(spacing: UmuveSpacing.xxlarge) {
                // Header (no progress bar - wizard handles that)
                VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                    Text("Pick a Date & Time")
                        .font(UmuveTypography.h1Font)
                        .foregroundColor(.umuveText)

                    Text("Choose when you would like us to come pick up your items.")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, UmuveSpacing.normal)

                // Empty state if nothing selected
                if viewModel.selectedDate == nil {
                    DateTimeEmptyState()
                }

                // Date picker
                dateSelector

                // Time slots (only show after date is selected)
                if viewModel.selectedDate != nil {
                    timeSlotSection
                }

                // Help tip
                if viewModel.selectedTimeSlot == nil && viewModel.selectedDate != nil {
                    helpTip
                }

                Spacer()
            }
            .padding(UmuveSpacing.large)
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .safeAreaInset(edge: .bottom) {
            continueButton
        }
        .onAppear {
            // Sync with bookingData
            viewModel.selectedDate = bookingData.selectedDate
            viewModel.selectedTimeSlot = bookingData.selectedTimeSlot
        }
        .onChange(of: viewModel.selectedDate) { newValue in
            // Debounced update to prevent cascading renders
            DispatchQueue.main.async {
                bookingData.selectedDate = newValue
            }
        }
        .onChange(of: viewModel.selectedTimeSlot) { newValue in
            // Debounced update
            DispatchQueue.main.async {
                bookingData.selectedTimeSlot = newValue
            }
        }
    }
    
    // MARK: - Section Label
    private func sectionLabel(icon: String, title: String, accent: Color) -> some View {
        HStack(spacing: UmuveSpacing.small) {
            ZStack {
                RoundedRectangle(cornerRadius: UmuveRadius.sm)
                    .fill(accent.opacity(0.18))
                    .frame(width: 32, height: 32)

                Image(systemName: icon)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(accent)
            }

            Text(title)
                .font(UmuveTypography.h3Font)
                .foregroundColor(.umuveText)

            Spacer()
        }
    }

    // MARK: - Date Selector
    private var dateSelector: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            sectionLabel(icon: "calendar", title: "Select Date", accent: .categoryBlue)

            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: UmuveSpacing.medium) {
                    ForEach(viewModel.getAvailableDates(), id: \.self) { date in
                        DateCard(
                            date: date,
                            isSelected: viewModel.isDateSelected(date)
                        ) {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                viewModel.selectDate(date)
                            }
                        }
                    }
                }
                .padding(.vertical, UmuveSpacing.tiny)
            }
        }
    }

    // MARK: - Time Slot Section
    private var timeSlotSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            sectionLabel(icon: "clock.fill", title: "Select Time", accent: .categoryOrange)

            LazyVStack(spacing: UmuveSpacing.medium) {
                ForEach(viewModel.availableTimeSlots) { slot in
                    TimeSlotCard(
                        slot: slot,
                        isSelected: viewModel.isTimeSlotSelected(slot.id)
                    ) {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            viewModel.selectTimeSlot(slot.id)
                        }
                    }
                }
            }
        }
    }

    // MARK: - Help Tip
    private var helpTip: some View {
        HStack(alignment: .top, spacing: UmuveSpacing.normal) {
            ZStack {
                RoundedRectangle(cornerRadius: UmuveRadius.sm)
                    .fill(Color.categoryYellow.opacity(0.22))
                    .frame(width: 40, height: 40)

                Image(systemName: "clock.fill")
                    .font(.system(size: 18))
                    .foregroundColor(.categoryYellow)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Pick a time slot")
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)

                Text("Morning slots are most popular")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
            }

            Spacer(minLength: 0)
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuveBorder, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 4)
    }
    
    // MARK: - Continue Button
    private var continueButton: some View {
        Button {
            wizardVM.completeCurrentStep()
        } label: {
            Text("Continue →")
        }
        .buttonStyle(UmuvePrimaryButtonStyle())
        .padding(UmuveSpacing.large)
        .background(Color.umuveBackground)
        .disabled(!viewModel.hasSelectedDateTime)
        .opacity(viewModel.hasSelectedDateTime ? 1 : 0.5)
    }
}

// MARK: - Date Card (OPTIMIZED)
struct DateCard: View {
    let date: Date
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            VStack(spacing: UmuveSpacing.tiny) {
                Text(dayFormatter.string(from: date).uppercased())
                    .font(UmuveTypography.smallFont)
                    .tracking(0.5)
                    .foregroundColor(isSelected ? .white.opacity(0.9) : .umuveTextMuted)

                Text(dateFormatter.string(from: date))
                    .font(UmuveTypography.h2Font)
                    .foregroundColor(isSelected ? .white : .umuveText)
            }
            .frame(width: 64, height: 84)
            .background(
                Group {
                    if isSelected {
                        LinearGradient(
                            colors: [Color.umuvePrimary, Color.umuvePrimaryDark],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    } else {
                        Color.umuveWhite
                    }
                }
            )
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .strokeBorder(isSelected ? Color.clear : Color.umuveBorder, lineWidth: 1)
            )
            .shadow(
                color: isSelected ? Color.umuvePrimary.opacity(0.3) : .black.opacity(0.06),
                radius: isSelected ? 10 : 6,
                x: 0,
                y: isSelected ? 6 : 3
            )
            .scaleEffect(isSelected ? 1.02 : 1.0)
        }
        .buttonStyle(PlainButtonStyle())
    }
}

// MARK: - Time Slot Card (OPTIMIZED)
struct TimeSlotCard: View {
    let slot: TimeSlot
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: {
            if slot.isAvailable {
                onTap()
            }
        }) {
            HStack(spacing: UmuveSpacing.normal) {
                ZStack {
                    RoundedRectangle(cornerRadius: UmuveRadius.sm)
                        .fill(slot.isAvailable ? Color.umuvePrimary.opacity(0.12) : Color.umuveBorder.opacity(0.3))
                        .frame(width: 44, height: 44)

                    Image(systemName: "clock")
                        .font(.system(size: 18, weight: .medium))
                        .foregroundColor(slot.isAvailable ? .umuvePrimary : .umuveTextTertiary)
                }

                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: UmuveSpacing.small) {
                        Text(slot.time)
                            .font(UmuveTypography.bodyFont.weight(.semibold))
                            .foregroundColor(slot.isAvailable ? .umuveText : .umuveTextMuted)

                        if slot.isRecommended && slot.isAvailable {
                            Text("RECOMMENDED")
                                .font(UmuveTypography.smallFont)
                                .tracking(0.5)
                                .foregroundColor(.white)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(Color.umuveCTA)
                                .clipShape(Capsule())
                        }
                    }

                    if !slot.isAvailable {
                        Text("Not available")
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.umuveTextMuted)
                    }
                }

                Spacer()

                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.umuvePrimary)
                }
            }
            .padding(UmuveSpacing.normal)
            .background(slot.isAvailable ? Color.umuveWhite : Color.umuveWhite.opacity(0.5))
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
            .overlay(
                RoundedRectangle(cornerRadius: UmuveRadius.lg)
                    .strokeBorder(
                        isSelected ? Color.umuvePrimary : Color.umuveBorder,
                        lineWidth: isSelected ? 2 : 1
                    )
            )
            .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 4)
            .scaleEffect(isSelected ? 1.02 : 1.0)
        }
        .buttonStyle(PlainButtonStyle())
        .disabled(!slot.isAvailable)
    }
}

// MARK: - Preview
struct DateTimePickerView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            DateTimePickerView()
                .environmentObject(BookingData())
        }
    }
}

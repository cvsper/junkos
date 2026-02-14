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
                VStack(spacing: UmuveSpacing.small) {
                    Text("Choose Date & Time")
                        .font(UmuveTypography.h1Font)
                        .foregroundColor(.umuveText)

                    Text("When should we come?")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
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
    
    // MARK: - Date Selector
    private var dateSelector: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.medium) {
            Text("Select Date")
                .font(UmuveTypography.h3Font)
                .foregroundColor(.umuveText)
            
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
            }
        }
    }
    
    // MARK: - Time Slot Section
    private var timeSlotSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.medium) {
            Text("Select Time")
                .font(UmuveTypography.h3Font)
                .foregroundColor(.umuveText)
            
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
        HStack(alignment: .top, spacing: UmuveSpacing.medium) {
            // SF Symbol: clock.fill for time
            // https://developer.apple.com/design/human-interface-guidelines/sf-symbols
            Image(systemName: "clock.fill")
                .font(.system(size: 24))
                .foregroundColor(.umuveCTA)
            
            VStack(alignment: .leading, spacing: 4) {
                Text("Pick a time slot")
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)
                
                Text("Morning slots are most popular")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
            }
            
            Spacer()
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveCTA.opacity(0.1))
        .cornerRadius(12)
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
            VStack(spacing: UmuveSpacing.small) {
                Text(dayFormatter.string(from: date))
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(isSelected ? .white : .umuveTextMuted)
                
                Text(dateFormatter.string(from: date))
                    .font(UmuveTypography.h2Font)
                    .foregroundColor(isSelected ? .white : .umuveText)
            }
            .frame(width: 70, height: 80)
            .background(isSelected ? Color.umuvePrimary : Color.umuveWhite)
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.umuvePrimary : Color.umuveBorder, lineWidth: 2)
            )
            // OPTIMIZATION: Animation only on selection, not during scroll
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
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(slot.time)
                            .font(UmuveTypography.bodyFont.weight(.semibold))
                            .foregroundColor(slot.isAvailable ? .umuveText : .umuveTextMuted)
                        
                        if slot.isRecommended && slot.isAvailable {
                            Text("RECOMMENDED")
                                .font(UmuveTypography.smallFont)
                                .foregroundColor(.white)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.umuveCTA)
                                .cornerRadius(8)
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
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.umuvePrimary : Color.umuveBorder, lineWidth: 2)
            )
            // OPTIMIZATION: Simple scale animation only on selection
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

//
//  DateTimePickerView.swift
//  JunkOS
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
    @StateObject private var viewModel = DateTimePickerViewModel()
    
    var body: some View {
        ScrollView {
            LazyVStack(spacing: JunkSpacing.xxlarge) {
                // Header
                ScreenHeader(
                    title: "Choose Date & Time",
                    subtitle: "When should we come?",
                    progress: 0.8
                )
                
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
                
                // Booking summary preview (when date & time selected)
                if viewModel.hasSelectedDateTime {
                    BookingSummaryPreview(
                        address: bookingData.address.fullAddress,
                        services: bookingData.selectedServices,
                        date: bookingData.selectedDate,
                        timeSlot: bookingData.selectedTimeSlot,
                        photoCount: bookingData.photos.count
                    )
                }
                
                Spacer()
            }
            .padding(JunkSpacing.large)
        }
        .background(Color.junkBackground.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
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
        VStack(alignment: .leading, spacing: JunkSpacing.medium) {
            Text("Select Date")
                .font(JunkTypography.h3Font)
                .foregroundColor(.junkText)
            
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: JunkSpacing.medium) {
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
        VStack(alignment: .leading, spacing: JunkSpacing.medium) {
            Text("Select Time")
                .font(JunkTypography.h3Font)
                .foregroundColor(.junkText)
            
            LazyVStack(spacing: JunkSpacing.medium) {
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
        HStack(alignment: .top, spacing: JunkSpacing.medium) {
            // SF Symbol: clock.fill for time
            // https://developer.apple.com/design/human-interface-guidelines/sf-symbols
            Image(systemName: "clock.fill")
                .font(.system(size: 24))
                .foregroundColor(.junkCTA)
            
            VStack(alignment: .leading, spacing: 4) {
                Text("Pick a time slot")
                    .font(JunkTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.junkText)
                
                Text("Morning slots are most popular")
                    .font(JunkTypography.bodySmallFont)
                    .foregroundColor(.junkTextMuted)
            }
            
            Spacer()
        }
        .padding(JunkSpacing.normal)
        .background(Color.junkCTA.opacity(0.1))
        .cornerRadius(12)
    }
    
    // MARK: - Continue Button
    private var continueButton: some View {
        NavigationLink(
            destination: ConfirmationView().environmentObject(bookingData),
            label: {
                Text("Continue →")
            }
        )
        .buttonStyle(JunkPrimaryButtonStyle())
        .padding(JunkSpacing.large)
        .background(Color.junkBackground)
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
            VStack(spacing: JunkSpacing.small) {
                Text(dayFormatter.string(from: date))
                    .font(JunkTypography.bodySmallFont)
                    .foregroundColor(isSelected ? .white : .junkTextMuted)
                
                Text(dateFormatter.string(from: date))
                    .font(JunkTypography.h2Font)
                    .foregroundColor(isSelected ? .white : .junkText)
            }
            .frame(width: 70, height: 80)
            .background(isSelected ? Color.junkPrimary : Color.junkWhite)
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.junkPrimary : Color.junkBorder, lineWidth: 2)
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
                            .font(JunkTypography.bodyFont.weight(.semibold))
                            .foregroundColor(slot.isAvailable ? .junkText : .junkTextMuted)
                        
                        if slot.isRecommended && slot.isAvailable {
                            Text("RECOMMENDED")
                                .font(JunkTypography.smallFont)
                                .foregroundColor(.white)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.junkCTA)
                                .cornerRadius(8)
                        }
                    }
                    
                    if !slot.isAvailable {
                        Text("Not available")
                            .font(JunkTypography.bodySmallFont)
                            .foregroundColor(.junkTextMuted)
                    }
                }
                
                Spacer()
                
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.junkPrimary)
                }
            }
            .padding(JunkSpacing.normal)
            .background(slot.isAvailable ? Color.junkWhite : Color.junkWhite.opacity(0.5))
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.junkPrimary : Color.junkBorder, lineWidth: 2)
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

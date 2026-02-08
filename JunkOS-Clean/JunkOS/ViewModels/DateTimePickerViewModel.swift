//
//  DateTimePickerViewModel.swift
//  JunkOS
//
//  ViewModel for DateTimePickerView
//

import SwiftUI
import Combine

class DateTimePickerViewModel: ObservableObject {
    // MARK: - Published Properties
    @Published var selectedDate: Date?
    @Published var selectedTimeSlot: String?
    @Published var estimatedPrice: Double?
    @Published var availableTimeSlots: [TimeSlot] = TimeSlot.slots
    @Published var isLoadingQuote: Bool = false
    @Published var quoteError: String?
    
    private let apiClient = APIClient.shared
    
    // MARK: - Public Methods
    
    /// Fetch quote from API
    @MainActor
    func fetchQuote(serviceIds: [String], zipCode: String) async {
        isLoadingQuote = true
        quoteError = nil
        
        do {
            let quote = try await apiClient.getQuote(serviceIds: serviceIds, zipCode: zipCode)
            estimatedPrice = quote.estimatedPrice
            
            // Parse available time slots from API
            parseTimeSlots(quote.availableTimeSlots)
            
        } catch {
            quoteError = error.localizedDescription
            print("Error fetching quote: \(error)")
            // Keep local time slots on error
        }
        
        isLoadingQuote = false
    }
    
    /// Parse time slots from API strings
    private func parseTimeSlots(_ apiSlots: [String]) {
        // API returns slots like "2024-01-15 09:00"
        // Convert them to TimeSlot objects
        // For now, keep the local slots - in a real app you'd parse these properly
        availableTimeSlots = TimeSlot.slots
    }
    
    /// Select a date
    func selectDate(_ date: Date) {
        HapticManager.shared.selection()
        selectedDate = date
    }
    
    /// Select a time slot
    func selectTimeSlot(_ slotId: String) {
        guard let slot = availableTimeSlots.first(where: { $0.id == slotId }),
              slot.isAvailable else {
            return
        }
        
        HapticManager.shared.selection()
        selectedTimeSlot = slotId
    }
    
    /// Check if date and time are selected
    var hasSelectedDateTime: Bool {
        selectedDate != nil && selectedTimeSlot != nil
    }
    
    /// Get available dates (next 7 days)
    func getAvailableDates() -> [Date] {
        (0..<7).compactMap { offset in
            Calendar.current.date(byAdding: .day, value: offset, to: Date())
        }
    }
    
    /// Check if a date is selected
    func isDateSelected(_ date: Date) -> Bool {
        guard let selectedDate = selectedDate else { return false }
        return Calendar.current.isDate(selectedDate, inSameDayAs: date)
    }
    
    /// Check if a time slot is selected
    func isTimeSlotSelected(_ slotId: String) -> Bool {
        selectedTimeSlot == slotId
    }
    
    /// Format date for display
    func formatDate(_ date: Date, style: DateFormatter.Style = .medium) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = style
        return formatter.string(from: date)
    }
    
    /// Get time slot by ID
    func getTimeSlot(by id: String) -> TimeSlot? {
        availableTimeSlots.first(where: { $0.id == id })
    }
    
    /// Get formatted date time for API
    func getFormattedDateTime() -> String? {
        guard let date = selectedDate,
              let timeSlotId = selectedTimeSlot,
              let timeSlot = getTimeSlot(by: timeSlotId) else {
            return nil
        }
        
        // Parse time from slot (e.g., "8:00 AM - 10:00 AM" -> "08:00")
        let timeString = timeSlot.time.components(separatedBy: " - ").first ?? "09:00"
        
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        let dateString = dateFormatter.string(from: date)
        
        return "\(dateString) \(timeString)"
    }
}

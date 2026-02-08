//
//  DateTimePickerViewModelTests.swift
//  JunkOSTests
//
//  Unit tests for DateTimePickerViewModel
//

import XCTest
@testable import JunkOS

@MainActor
final class DateTimePickerViewModelTests: XCTestCase {
    
    var viewModel: DateTimePickerViewModel!
    
    override func setUp() {
        super.setUp()
        viewModel = DateTimePickerViewModel()
    }
    
    override func tearDown() {
        viewModel = nil
        super.tearDown()
    }
    
    // MARK: - Initialization Tests
    
    func testInitialization() {
        // Then
        XCTAssertNotNil(viewModel)
        XCTAssertNil(viewModel.selectedDate)
        XCTAssertNil(viewModel.selectedTimeSlot)
        XCTAssertFalse(viewModel.hasSelectedDateTime)
    }
    
    func testAvailableTimeSlotsNotEmpty() {
        // Then
        XCTAssertFalse(viewModel.availableTimeSlots.isEmpty)
        XCTAssertEqual(viewModel.availableTimeSlots.count, TimeSlot.slots.count)
    }
    
    // MARK: - Date Selection Tests
    
    func testSelectValidDate() {
        // Given - tomorrow's date
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        
        // When
        viewModel.selectDate(tomorrow)
        
        // Then
        XCTAssertNotNil(viewModel.selectedDate)
        XCTAssertTrue(viewModel.isDateSelected(tomorrow))
    }
    
    func testSelectToday() {
        // Given - today's date
        let today = Date()
        
        // When
        viewModel.selectDate(today)
        
        // Then
        XCTAssertNotNil(viewModel.selectedDate)
        XCTAssertTrue(viewModel.isDateSelected(today))
    }
    
    func testDateSelectionChanges() {
        // Given - select first date
        let date1 = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        viewModel.selectDate(date1)
        XCTAssertTrue(viewModel.isDateSelected(date1))
        
        // When - select different date
        let date2 = Calendar.current.date(byAdding: .day, value: 2, to: Date())!
        viewModel.selectDate(date2)
        
        // Then - only second date should be selected
        XCTAssertFalse(viewModel.isDateSelected(date1))
        XCTAssertTrue(viewModel.isDateSelected(date2))
    }
    
    // MARK: - Time Slot Tests
    
    func testSelectAvailableTimeSlot() {
        // Given - available time slot
        let availableSlot = TimeSlot.slots.first(where: { $0.isAvailable })!
        
        // When
        viewModel.selectTimeSlot(availableSlot.id)
        
        // Then
        XCTAssertEqual(viewModel.selectedTimeSlot, availableSlot.id)
        XCTAssertTrue(viewModel.isTimeSlotSelected(availableSlot.id))
    }
    
    func testRejectUnavailableTimeSlot() {
        // Given - unavailable time slot
        let unavailableSlot = TimeSlot.slots.first(where: { !$0.isAvailable })!
        
        // When
        viewModel.selectTimeSlot(unavailableSlot.id)
        
        // Then - should not be selected
        XCTAssertNil(viewModel.selectedTimeSlot)
        XCTAssertFalse(viewModel.isTimeSlotSelected(unavailableSlot.id))
    }
    
    func testTimeSlotSelectionChanges() {
        // Given - select first available slot
        let slot1 = TimeSlot.slots.filter({ $0.isAvailable })[0]
        viewModel.selectTimeSlot(slot1.id)
        XCTAssertTrue(viewModel.isTimeSlotSelected(slot1.id))
        
        // When - select different slot
        let slot2 = TimeSlot.slots.filter({ $0.isAvailable })[1]
        viewModel.selectTimeSlot(slot2.id)
        
        // Then - only second slot should be selected
        XCTAssertFalse(viewModel.isTimeSlotSelected(slot1.id))
        XCTAssertTrue(viewModel.isTimeSlotSelected(slot2.id))
    }
    
    // MARK: - Validation Tests
    
    func testHasSelectedDateTimeWhenBothSelected() {
        // Given
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        let availableSlot = TimeSlot.slots.first(where: { $0.isAvailable })!
        
        // When
        viewModel.selectDate(tomorrow)
        viewModel.selectTimeSlot(availableSlot.id)
        
        // Then
        XCTAssertTrue(viewModel.hasSelectedDateTime)
    }
    
    func testHasSelectedDateTimeWhenOnlyDateSelected() {
        // Given
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        
        // When
        viewModel.selectDate(tomorrow)
        
        // Then
        XCTAssertFalse(viewModel.hasSelectedDateTime)
    }
    
    func testHasSelectedDateTimeWhenOnlyTimeSelected() {
        // Given
        let availableSlot = TimeSlot.slots.first(where: { $0.isAvailable })!
        
        // When
        viewModel.selectTimeSlot(availableSlot.id)
        
        // Then
        XCTAssertFalse(viewModel.hasSelectedDateTime)
    }
    
    func testHasSelectedDateTimeWhenNeitherSelected() {
        // Given - nothing selected
        
        // Then
        XCTAssertFalse(viewModel.hasSelectedDateTime)
    }
    
    // MARK: - Available Dates Tests
    
    func testGetAvailableDates() {
        // When
        let availableDates = viewModel.getAvailableDates()
        
        // Then
        XCTAssertEqual(availableDates.count, 7, "Should return 7 days")
        
        // Verify dates are sequential
        for i in 0..<availableDates.count {
            let expectedDate = Calendar.current.date(byAdding: .day, value: i, to: Date())!
            let calendar = Calendar.current
            XCTAssertTrue(
                calendar.isDate(availableDates[i], inSameDayAs: expectedDate),
                "Date at index \(i) should match expected date"
            )
        }
    }
    
    // MARK: - Date Formatting Tests
    
    func testFormatDate() {
        // Given
        let date = Date()
        
        // When
        let formattedDate = viewModel.formatDate(date)
        
        // Then
        XCTAssertFalse(formattedDate.isEmpty)
        // Verify it contains some part of the date
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        XCTAssertEqual(formattedDate, formatter.string(from: date))
    }
    
    func testFormatDateWithCustomStyle() {
        // Given
        let date = Date()
        let style: DateFormatter.Style = .short
        
        // When
        let formattedDate = viewModel.formatDate(date, style: style)
        
        // Then
        XCTAssertFalse(formattedDate.isEmpty)
        let formatter = DateFormatter()
        formatter.dateStyle = style
        XCTAssertEqual(formattedDate, formatter.string(from: date))
    }
    
    // MARK: - Time Slot Query Tests
    
    func testGetTimeSlotById() {
        // Given
        let expectedSlot = TimeSlot.slots.first!
        
        // When
        let slot = viewModel.getTimeSlot(by: expectedSlot.id)
        
        // Then
        XCTAssertNotNil(slot)
        XCTAssertEqual(slot?.id, expectedSlot.id)
        XCTAssertEqual(slot?.time, expectedSlot.time)
    }
    
    func testGetTimeSlotByInvalidId() {
        // When
        let slot = viewModel.getTimeSlot(by: "invalid_id")
        
        // Then
        XCTAssertNil(slot)
    }
    
    // MARK: - Is Date Selected Tests
    
    func testIsDateSelectedForUnselectedDate() {
        // Given
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        
        // Then
        XCTAssertFalse(viewModel.isDateSelected(tomorrow))
    }
    
    func testIsDateSelectedForSelectedDate() {
        // Given
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        viewModel.selectDate(tomorrow)
        
        // Then
        XCTAssertTrue(viewModel.isDateSelected(tomorrow))
    }
    
    func testIsDateSelectedForDifferentDate() {
        // Given
        let date1 = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        let date2 = Calendar.current.date(byAdding: .day, value: 2, to: Date())!
        viewModel.selectDate(date1)
        
        // Then
        XCTAssertTrue(viewModel.isDateSelected(date1))
        XCTAssertFalse(viewModel.isDateSelected(date2))
    }
}

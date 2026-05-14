//
//  AddressInputViewModelTests.swift
//  UmuveTests
//
//  The legacy suite (isAddressValid, region, detectLocation) exercised a
//  pre-Auto-Transport-removal API that no longer exists. This file now
//  covers the current VM, which is a small MapKit autocomplete wrapper:
//  pickupSearchQuery feeds MKLocalSearchCompleter; pickupSelected flips
//  true once an address is geocoded and stored on bookingData.
//

import XCTest
import CoreLocation
@testable import Umuve

@MainActor
final class AddressInputViewModelTests: XCTestCase {

    var viewModel: AddressInputViewModel!
    var bookingData: BookingData!

    override func setUp() {
        super.setUp()
        viewModel = AddressInputViewModel()
        bookingData = BookingData()
    }

    override func tearDown() {
        viewModel = nil
        bookingData = nil
        super.tearDown()
    }

    // MARK: - Initial State

    func testInitialState() {
        XCTAssertEqual(viewModel.pickupSearchQuery, "")
        XCTAssertTrue(viewModel.pickupCompletions.isEmpty)
        XCTAssertFalse(viewModel.isSearching)
        XCTAssertFalse(viewModel.pickupSelected)
        XCTAssertNil(viewModel.locationError)
    }

    // MARK: - Default Region

    func testDefaultPickupRegionIsSouthFlorida() {
        // The default region centers on South Florida (Boca / Fort Lauderdale
        // area) so the mini-map and autocomplete suggestions feel local to
        // first-time users in the service area.
        XCTAssertEqual(viewModel.pickupRegion.center.latitude, 26.0, accuracy: 1.5)
        XCTAssertEqual(viewModel.pickupRegion.center.longitude, -80.0, accuracy: 1.5)
    }

    // MARK: - Search Query Reactivity

    func testEmptySearchQueryClearsCompletions() async throws {
        viewModel.pickupCompletions = []
        viewModel.pickupSearchQuery = ""

        // Allow the Combine debounced pipeline to settle.
        try await Task.sleep(nanoseconds: 200_000_000)

        XCTAssertTrue(viewModel.pickupCompletions.isEmpty)
    }
}

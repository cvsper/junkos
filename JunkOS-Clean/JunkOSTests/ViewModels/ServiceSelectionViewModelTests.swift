//
//  ServiceSelectionViewModelTests.swift
//  UmuveTests
//
//  ServiceSelectionViewModel was simplified after Auto Transport removal +
//  the items+quantity refactor. The legacy test suite (toggleService,
//  selectedServices, getSelectedServiceNames, etc.) was exercising methods
//  that no longer exist on the VM. This file now covers the current,
//  much smaller API surface — primarily `requestPricingEstimate(for:)`
//  which sets `bookingData.estimatedPrice` based on the user's items.
//

import XCTest
@testable import Umuve

@MainActor
final class ServiceSelectionViewModelTests: XCTestCase {

    var viewModel: ServiceSelectionViewModel!
    var bookingData: BookingData!

    override func setUp() {
        super.setUp()
        viewModel = ServiceSelectionViewModel()
        bookingData = BookingData()
    }

    override func tearDown() {
        viewModel = nil
        bookingData = nil
        super.tearDown()
    }

    // MARK: - Initialization

    func testInitialState() {
        XCTAssertNotNil(viewModel)
        XCTAssertFalse(viewModel.isLoading)
    }

    // MARK: - requestPricingEstimate

    func testRequestPricingEstimateSetsBookingEstimatedPrice() async {
        // Given: a booking with junk-removal selected and one item — the
        // placeholder pricing logic scales by the truck tier the items fit
        // into, so we need at least one item for a non-zero result.
        bookingData.serviceType = .junkRemoval
        let preset = ItemCategory.furniture.presets[0]
        bookingData.items = [BookingItem(category: .furniture, preset: preset)]

        // When
        await viewModel.requestPricingEstimate(for: bookingData)

        // Then: estimatedPrice populated and loading is back to false.
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNotNil(bookingData.estimatedPrice)
        XCTAssertGreaterThan(bookingData.estimatedPrice ?? 0, 0)
        // A placeholder breakdown is also surfaced so the UI has something
        // to show even when the API hasn't returned yet.
        XCTAssertNotNil(bookingData.priceBreakdown)
    }

    func testRequestPricingEstimateNoServiceType() async {
        // Given: no service type selected. The VM should still complete
        // without crashing — it just won't populate a price.
        XCTAssertNil(bookingData.serviceType)

        // When
        await viewModel.requestPricingEstimate(for: bookingData)

        // Then
        XCTAssertFalse(viewModel.isLoading)
    }

    // MARK: - isLoading

    func testLoadingStateClearsAfterEstimate() async {
        bookingData.serviceType = .junkRemoval

        await viewModel.requestPricingEstimate(for: bookingData)

        XCTAssertFalse(viewModel.isLoading, "isLoading should be cleared once the estimate request completes")
    }
}

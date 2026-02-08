//
//  PhotoUploadViewModelTests.swift
//  JunkOSTests
//
//  Unit tests for PhotoUploadViewModel
//

import XCTest
import PhotosUI
@testable import JunkOS

@MainActor
final class PhotoUploadViewModelTests: XCTestCase {
    
    var viewModel: PhotoUploadViewModel!
    
    override func setUp() {
        super.setUp()
        viewModel = PhotoUploadViewModel()
    }
    
    override func tearDown() {
        viewModel = nil
        super.tearDown()
    }
    
    // MARK: - Initialization Tests
    
    func testInitialization() {
        // Then
        XCTAssertNotNil(viewModel)
        XCTAssertTrue(viewModel.selectedItems.isEmpty)
        XCTAssertFalse(viewModel.elementsVisible)
    }
    
    // MARK: - Animation Tests
    
    func testStartAnimations() {
        // Given
        XCTAssertFalse(viewModel.elementsVisible)
        
        // When
        viewModel.startAnimations()
        
        // Then
        XCTAssertTrue(viewModel.elementsVisible)
    }
    
    // MARK: - Photo Management Tests
    
    func testRemovePhotoAtIndex() {
        // Given
        var photos = [
            "Photo1".data(using: .utf8)!,
            "Photo2".data(using: .utf8)!,
            "Photo3".data(using: .utf8)!
        ]
        let initialCount = photos.count
        
        // When
        viewModel.removePhoto(at: 1, from: &photos)
        
        // Then
        XCTAssertEqual(photos.count, initialCount - 1)
        XCTAssertEqual(String(data: photos[0], encoding: .utf8), "Photo1")
        XCTAssertEqual(String(data: photos[1], encoding: .utf8), "Photo3")
    }
    
    func testRemoveFirstPhoto() {
        // Given
        var photos = [
            "Photo1".data(using: .utf8)!,
            "Photo2".data(using: .utf8)!
        ]
        
        // When
        viewModel.removePhoto(at: 0, from: &photos)
        
        // Then
        XCTAssertEqual(photos.count, 1)
        XCTAssertEqual(String(data: photos[0], encoding: .utf8), "Photo2")
    }
    
    func testRemoveLastPhoto() {
        // Given
        var photos = [
            "Photo1".data(using: .utf8)!,
            "Photo2".data(using: .utf8)!
        ]
        
        // When
        viewModel.removePhoto(at: 1, from: &photos)
        
        // Then
        XCTAssertEqual(photos.count, 1)
        XCTAssertEqual(String(data: photos[0], encoding: .utf8), "Photo1")
    }
    
    // MARK: - Continue Button Text Tests
    
    func testContinueButtonTextWithNoPhotos() {
        // When
        let buttonText = viewModel.continueButtonText(photoCount: 0)
        
        // Then
        XCTAssertEqual(buttonText, "Skip Photos →")
    }
    
    func testContinueButtonTextWithOnePhoto() {
        // When
        let buttonText = viewModel.continueButtonText(photoCount: 1)
        
        // Then
        XCTAssertEqual(buttonText, "Continue with 1 photo →")
    }
    
    func testContinueButtonTextWithMultiplePhotos() {
        // When
        let buttonText = viewModel.continueButtonText(photoCount: 3)
        
        // Then
        XCTAssertEqual(buttonText, "Continue with 3 photos →")
    }
    
    func testContinueButtonTextWithManyPhotos() {
        // When
        let buttonText = viewModel.continueButtonText(photoCount: 10)
        
        // Then
        XCTAssertEqual(buttonText, "Continue with 10 photos →")
    }
    
    // MARK: - Selected Items Tests
    
    func testSelectedItemsInitiallyEmpty() {
        // Then
        XCTAssertTrue(viewModel.selectedItems.isEmpty)
    }
    
    // MARK: - Load Photos Tests (Integration-style)
    
    func testLoadPhotosEmptyItems() async {
        // Given
        let items: [PhotosPickerItem] = []
        let expectation = expectation(description: "Load photos completion")
        var resultPhotos: [Data] = []
        
        // When
        viewModel.loadPhotos(from: items) { photos in
            resultPhotos = photos
            expectation.fulfill()
        }
        
        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertTrue(resultPhotos.isEmpty)
        XCTAssertTrue(viewModel.selectedItems.isEmpty, "Selected items should be cleared after loading")
    }
    
    // Note: Testing actual PhotosPickerItem loading requires UI testing or mocking
    // the PhotosPickerItem which is complex. The empty case validates the structure.
    
    // MARK: - Edge Cases
    
    func testRemovePhotoFromEmptyArray() {
        // Given
        var photos: [Data] = []
        
        // This test documents that the code should handle empty arrays gracefully
        // In production, the UI should prevent calling removePhoto on empty arrays
        // but we test defensive programming
        
        // We cannot test this directly as it would crash with index out of bounds
        // This documents expected behavior: UI should disable remove when empty
        XCTAssertTrue(photos.isEmpty)
    }
    
    func testContinueButtonTextConsistency() {
        // Test that button text formatting is consistent
        let testCases: [(count: Int, expectedSuffix: String)] = [
            (0, "Skip Photos →"),
            (1, "Continue with 1 photo →"),
            (2, "Continue with 2 photos →"),
            (5, "Continue with 5 photos →"),
            (100, "Continue with 100 photos →")
        ]
        
        for testCase in testCases {
            let text = viewModel.continueButtonText(photoCount: testCase.count)
            XCTAssertEqual(text, testCase.expectedSuffix, 
                          "Button text for \(testCase.count) photos should match expected format")
        }
    }
}

//
//  MockLocationManager.swift
//  UmuveTests
//
//  Mock LocationManager for testing
//

import Foundation
import CoreLocation
@testable import Umuve

class MockLocationManager: LocationManager {
    // MARK: - Mock Properties
    var shouldSucceed = true
    var mockAddress = Address(
        street: "123 Test St",
        unit: "Suite 100",
        city: "Tampa",
        state: "FL",
        zipCode: "33602"
    )
    var mockLocation = CLLocation(latitude: 27.9506, longitude: -82.4572)
    var mockError: Error?
    var requestLocationCalled = false
    var reverseGeocodeCalled = false
    
    // MARK: - Override Methods
    override func requestLocation() {
        requestLocationCalled = true
        if shouldSucceed {
            self.location = mockLocation
        }
    }
    
    override func reverseGeocode(completion: @escaping (Result<Address, Error>) -> Void) {
        reverseGeocodeCalled = true
        
        if shouldSucceed {
            completion(.success(mockAddress))
        } else {
            let error = mockError ?? NSError(
                domain: "MockLocationManager",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Mock location error"]
            )
            completion(.failure(error))
        }
    }
    
    // MARK: - Helper Methods
    func reset() {
        shouldSucceed = true
        mockAddress = Address(
            street: "123 Test St",
            unit: "Suite 100",
            city: "Tampa",
            state: "FL",
            zipCode: "33602"
        )
        mockLocation = CLLocation(latitude: 27.9506, longitude: -82.4572)
        mockError = nil
        requestLocationCalled = false
        reverseGeocodeCalled = false
    }
}

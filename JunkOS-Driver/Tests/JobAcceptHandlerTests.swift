import CoreLocation
import XCTest
@testable import JunkOS_Driver

final class JobAcceptHandlerTests: XCTestCase {
    func testDestinationCoordinateReturnsJobCoordinate() throws {
        let coordinate = try JobAcceptHandler.destinationCoordinate(for: makeJob(lat: 33.749, lng: -84.388))

        XCTAssertEqual(coordinate.latitude, 33.749, accuracy: 0.0001)
        XCTAssertEqual(coordinate.longitude, -84.388, accuracy: 0.0001)
    }

    func testDestinationCoordinateThrowsWhenCoordinateMissing() {
        XCTAssertThrowsError(
            try JobAcceptHandler.destinationCoordinate(for: makeJob(lat: nil, lng: nil))
        ) { error in
            XCTAssertEqual(
                error as? JobAcceptHandlerError,
                .missingDestinationCoordinate(jobId: "job-123")
            )
        }
    }

    private func makeJob(lat: Double?, lng: Double?) -> DriverJob {
        DriverJob(
            id: "job-123",
            customerId: "customer-123",
            driverId: nil,
            status: "accepted",
            address: "123 Demo St, Atlanta, GA",
            lat: lat,
            lng: lng,
            items: nil,
            volumeEstimate: nil,
            photos: [],
            beforePhotos: [],
            afterPhotos: [],
            scheduledAt: nil,
            startedAt: nil,
            completedAt: nil,
            basePrice: 100,
            itemTotal: 0,
            volumePrice: 0,
            serviceFee: 10,
            surgeMultiplier: 1,
            totalPrice: 110,
            notes: nil,
            createdAt: nil,
            updatedAt: nil,
            distanceKm: nil
        )
    }
}

import XCTest
@testable import JunkOS_Driver

/// Regression guards for the unified active-job flow.
///
/// After unification, the map (`LiveMapViewModel`) owns only accept → en route →
/// navigation, then hands off to `ActiveJobView` for the photo-gated
/// start/complete + completion flow. These tests lock in the VM invariants that
/// the hand-off and cover-dismiss depend on:
///   1. a single active job at a time (a new alert must not hijack one in progress)
///   2. full teardown when the job clears (so the map returns cleanly to idle)
/// and document that the photoless map-side complete path no longer exists.
final class LiveMapViewModelTests: XCTestCase {

    // MARK: - Single-job invariant

    func testShowJobAlertWhenIdleArmsTheAlert() {
        let vm = LiveMapViewModel()
        vm.showJobAlert(makeJob(status: "broadcasting"))

        XCTAssertNotNil(vm.incomingJobAlert, "An incoming alert should arm when idle")
        XCTAssertEqual(vm.alertCountdown, 30)
    }

    func testShowJobAlertIsSuppressedWhileAJobIsActive() {
        let vm = LiveMapViewModel()
        vm.acceptedJob = makeJob(id: "active-1", status: "arrived")

        vm.showJobAlert(makeJob(id: "incoming-2", status: "broadcasting"))

        // The driver is mid-job (handed off to ActiveJobView). A new alert must
        // not appear and hijack the in-progress job.
        XCTAssertNil(vm.incomingJobAlert,
                     "No new alert should arm while a job is active")
        XCTAssertEqual(vm.acceptedJob?.id, "active-1")
    }

    // MARK: - Teardown invariant (what cover-dismiss relies on)

    func testClearAcceptedJobTearsDownAllJobState() {
        let vm = LiveMapViewModel()
        vm.acceptedJob = makeJob(id: "done-1", status: "started")
        vm.routeETA = "12 min"
        vm.startNavigation()
        XCTAssertTrue(vm.isNavigating)

        vm.clearAcceptedJob()

        // On completion ("Back to Dashboard" → activeJob = nil), LiveMapView calls
        // clearAcceptedJob(); the map must return to a fully idle state.
        XCTAssertNil(vm.acceptedJob)
        XCTAssertNil(vm.route)
        XCTAssertNil(vm.routeETA)
        XCTAssertFalse(vm.isNavigating)
        XCTAssertTrue(vm.navigationSteps.isEmpty)
        XCTAssertEqual(vm.currentStepIndex, 0)
    }

    func testStopNavigationResetsNavigationState() {
        let vm = LiveMapViewModel()
        vm.startNavigation()
        vm.stopNavigation()

        XCTAssertFalse(vm.isNavigating)
        XCTAssertTrue(vm.navigationSteps.isEmpty)
        XCTAssertEqual(vm.currentStepIndex, 0)
        XCTAssertTrue(vm.isFollowingNavigationCamera)
    }

    // MARK: - Fixture

    private func makeJob(id: String = "job-123", status: String) -> DriverJob {
        DriverJob(
            id: id,
            customerId: "customer-123",
            driverId: nil,
            status: status,
            address: "123 Demo St, West Palm Beach, FL",
            lat: 26.7153,
            lng: -80.0534,
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

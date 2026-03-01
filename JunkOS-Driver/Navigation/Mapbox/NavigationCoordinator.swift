//
//  NavigationCoordinator.swift
//  Umuve Pro
//
//  Coordinates Mapbox navigation presentation, camera mode, and voice state.
//

import CoreLocation
import Foundation
import Observation

enum NavigationCoordinatorError: LocalizedError, Equatable {
    case mapboxUnavailable
    case routeRequestUnavailable

    var errorDescription: String? {
        switch self {
        case .mapboxUnavailable:
            return "Mapbox Navigation SDK is not linked into this build."
        case .routeRequestUnavailable:
            return "No active route request is available."
        }
    }
}

@MainActor
@Observable
final class NavigationCoordinator {
    enum CameraMode: String {
        case following
        case overview
    }

    enum State: Equatable {
        case idle
        case preparing
        case active
    }

    var state: State = .idle
    var cameraMode: CameraMode = .following
    var isMuted = false
    var shouldPresentNavigation = false
    var lastErrorMessage: String?
    private(set) var routeRequest: NavigationRouteRequest?

    weak var boundViewController: DriverNavigationViewController?

    var isMapboxRuntimeAvailable: Bool {
        #if canImport(MapboxMaps) && canImport(MapboxNavigationCore) && canImport(MapboxNavigationUIKit)
        return true
        #else
        return false
        #endif
    }

    func prepareNavigation(for job: DriverJob, currentLocation: CLLocationCoordinate2D?) throws {
        _ = try MapboxConfig.resolveAccessToken()
        routeRequest = try JobAcceptHandler.makeRouteRequest(for: job, currentLocation: currentLocation)
        cameraMode = .following
        isMuted = false
        lastErrorMessage = nil
        state = .preparing
        shouldPresentNavigation = true
    }

    func markNavigationReady() {
        state = .active
        lastErrorMessage = nil
    }

    func failNavigation(_ error: Error) {
        state = .idle
        shouldPresentNavigation = false
        lastErrorMessage = error.localizedDescription
    }

    func stopNavigation() {
        boundViewController?.stopNavigationSession()
        routeRequest = nil
        state = .idle
        cameraMode = .following
        shouldPresentNavigation = false
        lastErrorMessage = nil
    }

    func toggleMute() {
        isMuted.toggle()
        boundViewController?.setVoiceMuted(isMuted)
    }

    func toggleCameraMode() {
        let nextMode: CameraMode = cameraMode == .following ? .overview : .following
        setCameraMode(nextMode)
    }

    func setCameraMode(_ mode: CameraMode) {
        cameraMode = mode
        boundViewController?.applyCameraMode(mode, animated: true)
    }
}

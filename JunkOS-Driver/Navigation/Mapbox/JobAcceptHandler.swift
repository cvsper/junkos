//
//  JobAcceptHandler.swift
//  Umuve Pro
//
//  Bridges accepted jobs into in-app navigation requests.
//

import CoreLocation
import Foundation

enum JobAcceptHandlerError: LocalizedError, Equatable {
    case missingCurrentLocation
    case missingDestinationCoordinate(jobId: String)

    var errorDescription: String? {
        switch self {
        case .missingCurrentLocation:
            return "Current location is unavailable. Wait for GPS lock and try again."
        case .missingDestinationCoordinate:
            return "This job is missing destination coordinates."
        }
    }
}

struct NavigationRouteRequest {
    let jobId: String
    let origin: CLLocationCoordinate2D
    let destination: CLLocationCoordinate2D
}

enum JobAcceptHandler {
    static func destinationCoordinate(for job: DriverJob) throws -> CLLocationCoordinate2D {
        guard let lat = job.lat, let lng = job.lng else {
            throw JobAcceptHandlerError.missingDestinationCoordinate(jobId: job.id)
        }

        return CLLocationCoordinate2D(latitude: lat, longitude: lng)
    }

    static func makeRouteRequest(
        for job: DriverJob,
        currentLocation: CLLocationCoordinate2D?
    ) throws -> NavigationRouteRequest {
        guard let currentLocation else {
            throw JobAcceptHandlerError.missingCurrentLocation
        }

        return NavigationRouteRequest(
            jobId: job.id,
            origin: currentLocation,
            destination: try destinationCoordinate(for: job)
        )
    }
}

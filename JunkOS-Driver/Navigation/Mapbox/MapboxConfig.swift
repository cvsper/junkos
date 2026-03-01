//
//  MapboxConfig.swift
//  Umuve Pro
//
//  Centralized Mapbox token resolution and runtime validation.
//

import Foundation

enum MapboxConfigError: LocalizedError, Equatable {
    case missingAccessToken
    case missingTruckModel(name: String)

    var errorDescription: String? {
        switch self {
        case .missingAccessToken:
            return "Mapbox access token is missing. Set MAPBOX_PUBLIC_ACCESS_TOKEN or MBXAccessToken."
        case .missingTruckModel(let name):
            return "Missing \(name).glb in the app bundle."
        }
    }
}

enum MapboxConfig {
    static let infoPlistTokenKey = "MBXAccessToken"
    static let environmentTokenKey = "MAPBOX_PUBLIC_ACCESS_TOKEN"

    static func resolveAccessToken(
        environment: [String: String],
        infoDictionary: [String: Any]
    ) throws -> String {
        let candidates = [
            environment[environmentTokenKey],
            infoDictionary[infoPlistTokenKey] as? String,
        ]

        if let token = candidates
            .compactMap({ $0?.trimmingCharacters(in: .whitespacesAndNewlines) })
            .first(where: { !$0.isEmpty }) {
            return token
        }

        throw MapboxConfigError.missingAccessToken
    }

    static func resolveAccessToken(
        bundle: Bundle = .main,
        processInfo: ProcessInfo = .processInfo
    ) throws -> String {
        try resolveAccessToken(
            environment: processInfo.environment,
            infoDictionary: bundle.infoDictionary ?? [:]
        )
    }
}

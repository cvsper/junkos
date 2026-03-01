//
//  CustomPuckSetup.swift
//  Umuve Pro
//
//  Configures the custom 3D red truck puck.
//

import Foundation

#if canImport(MapboxMaps)
import MapboxMaps

enum CustomPuckSetup {
    static func redTruckPuckConfiguration(
        bundle: Bundle = .main,
        modelName: String = "red_truck",
        modelExtension: String = "glb"
    ) throws -> Puck3DConfiguration {
        guard let modelURL = bundle.url(forResource: modelName, withExtension: modelExtension) else {
            throw MapboxConfigError.missingTruckModel(name: modelName)
        }

        let model = Model(uri: modelURL, orientation: [0, 0, 90])

        return Puck3DConfiguration(
            model: model,
            modelScale: .constant([1.15, 1.15, 1.15]),
            modelRotation: .constant([0, 0, 90]),
            modelOpacity: .constant(1),
            layerPosition: .default
        )
    }

    static func apply(to mapView: MapView, bundle: Bundle = .main) throws {
        mapView.location.options.puckBearing = .heading
        mapView.location.options.puckBearingEnabled = true
        mapView.location.options.puckType = .puck3D(
            try redTruckPuckConfiguration(bundle: bundle)
        )
    }
}
#endif

//
//  TruckAnnotation.swift
//  Umuve Pro
//
//  Custom MKAnnotation for smooth 3D truck tracking
//

import MapKit

/// Custom annotation for the driver's truck with heading support
class TruckAnnotation: NSObject, MKAnnotation {
    // MKAnnotation requirements
    @objc dynamic var coordinate: CLLocationCoordinate2D
    var title: String?

    // Custom properties
    var heading: CLLocationDirection = 0
    var speed: CLLocationSpeed = 0

    init(coordinate: CLLocationCoordinate2D, heading: CLLocationDirection = 0) {
        self.coordinate = coordinate
        self.heading = heading
        self.title = "You"
        super.init()
    }

    /// Smoothly update coordinate with animation
    func updateCoordinate(_ newCoordinate: CLLocationCoordinate2D, animated: Bool = true) {
        if animated {
            // Use KVO-compliant property for smooth animation
            UIView.animate(withDuration: 0.7, delay: 0, options: [.curveLinear], animations: {
                self.coordinate = newCoordinate
            })
        } else {
            coordinate = newCoordinate
        }
    }
}

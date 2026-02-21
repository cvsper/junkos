//
//  TruckAnnotationView.swift
//  Umuve Pro
//
//  Custom annotation view with truck icon and smooth rotation
//

import MapKit
import UIKit

class TruckAnnotationView: MKAnnotationView {
    static let reuseIdentifier = "TruckAnnotationView"

    private let truckImageView = UIImageView()
    private var currentHeading: CLLocationDirection = 0

    override init(annotation: MKAnnotation?, reuseIdentifier: String?) {
        super.init(annotation: annotation, reuseIdentifier: reuseIdentifier)
        setupView()
    }

    required init?(coder aDecoder: NSCoder) {
        super.init(coder: aDecoder)
        setupView()
    }

    private func setupView() {
        // Configure annotation view
        frame = CGRect(x: 0, y: 0, width: 50, height: 50)
        centerOffset = CGPoint(x: 0, y: -frame.height / 2)

        // Configure truck image view
        truckImageView.contentMode = .scaleAspectFit
        truckImageView.frame = bounds

        // Try to load custom truck icon, fallback to SF Symbol
        if let truckImage = UIImage(named: "truck_icon") {
            truckImageView.image = truckImage
        } else {
            // Fallback to SF Symbol with tint
            let config = UIImage.SymbolConfiguration(pointSize: 32, weight: .semibold)
            truckImageView.image = UIImage(systemName: "truck.box.fill", withConfiguration: config)?
                .withTintColor(UIColor(red: 0.863, green: 0.149, blue: 0.149, alpha: 1.0), renderingMode: .alwaysOriginal)
        }

        addSubview(truckImageView)

        // Enable interaction
        isEnabled = false
        canShowCallout = false

        // Layer properties for smooth animation
        layer.anchorPoint = CGPoint(x: 0.5, y: 0.5)
    }

    override func prepareForReuse() {
        super.prepareForReuse()
        currentHeading = 0
        transform = .identity
    }

    /// Update truck heading with smooth rotation
    /// - Parameters:
    ///   - heading: New heading in degrees (0-360, 0 = North)
    ///   - animated: Whether to animate the rotation
    func updateHeading(_ heading: CLLocationDirection, animated: Bool = true) {
        // Ignore invalid headings or very small changes
        guard heading >= 0 && heading < 360 else { return }

        // Calculate heading difference (handle 360° wrap)
        var headingDelta = heading - currentHeading
        if headingDelta > 180 {
            headingDelta -= 360
        } else if headingDelta < -180 {
            headingDelta += 360
        }

        // Ignore tiny changes to prevent jitter
        guard abs(headingDelta) > 2 else { return }

        currentHeading = heading

        // Convert to radians (MapKit uses North = 0°, clockwise)
        let radians = heading * .pi / 180

        if animated {
            // Smooth rotation with timing curve
            UIView.animate(
                withDuration: 0.5,
                delay: 0,
                options: [.curveEaseInOut, .beginFromCurrentState],
                animations: {
                    self.transform = CGAffineTransform(rotationAngle: radians)
                }
            )
        } else {
            transform = CGAffineTransform(rotationAngle: radians)
        }
    }

    /// Update coordinate with smooth movement
    override func setCoordinate(_ newCoordinate: CLLocationCoordinate2D) {
        // Smooth coordinate updates handled by MKMapView animation
        super.setCoordinate(newCoordinate)
    }
}

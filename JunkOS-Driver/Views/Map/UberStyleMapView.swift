//
//  UberStyleMapView.swift
//  Umuve Pro
//
//  3D Uber-style map with smooth tracking, camera follow, and custom truck annotation
//

import SwiftUI
import MapKit

struct UberStyleMapView: UIViewRepresentable {
    @Binding var userLocation: CLLocation?
    var nearbyJobs: [DriverJob]
    var route: MKRoute?
    var truckType: String?

    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView()
        mapView.delegate = context.coordinator

        // Enable 3D features
        mapView.mapType = .mutedStandard
        mapView.showsBuildings = true
        mapView.showsUserLocation = false // We'll use custom annotation

        // Enable rotation and pitch
        mapView.isPitchEnabled = true
        mapView.isRotateEnabled = true
        mapView.isZoomEnabled = true
        mapView.isScrollEnabled = true

        // Register custom annotation view
        mapView.register(
            TruckAnnotationView.self,
            forAnnotationViewWithReuseIdentifier: TruckAnnotationView.reuseIdentifier
        )

        return mapView
    }

    func updateUIView(_ mapView: MKMapView, context: Context) {
        context.coordinator.updateLocation(userLocation, in: mapView)
        context.coordinator.updateNearbyJobs(nearbyJobs, in: mapView)
        context.coordinator.updateRoute(route, in: mapView)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    // MARK: - Coordinator

    class Coordinator: NSObject, MKMapViewDelegate {
        private var truckAnnotation: TruckAnnotation?
        private var isInitialPositionSet = false
        private var lastUpdateTime: Date = Date()
        private var previousCoordinate: CLLocationCoordinate2D?
        private var previousHeading: CLLocationDirection = 0

        // Jitter prevention
        private let minimumUpdateInterval: TimeInterval = 0.1 // 100ms
        private let minimumDistanceThreshold: CLLocationDistance = 5.0 // 5 meters
        private let headingChangeThreshold: CLLocationDirection = 5.0 // 5 degrees

        // MARK: - Location Updates

        func updateLocation(_ location: CLLocation?, in mapView: MKMapView) {
            guard let location = location else { return }

            // Throttle updates to prevent jitter
            let now = Date()
            guard now.timeIntervalSince(lastUpdateTime) >= minimumUpdateInterval else { return }
            lastUpdateTime = now

            let newCoordinate = location.coordinate
            let newHeading = location.course >= 0 ? location.course : previousHeading

            // Filter out noisy/invalid coordinates
            guard CLLocationCoordinate2DIsValid(newCoordinate),
                  newCoordinate.latitude != 0 || newCoordinate.longitude != 0 else { return }

            // Check if movement is significant enough
            if let previous = previousCoordinate {
                let distance = location.distance(from: CLLocation(latitude: previous.latitude, longitude: previous.longitude))
                guard distance >= minimumDistanceThreshold else { return }
            }

            // Create or update truck annotation
            if truckAnnotation == nil {
                setupTruckAnnotation(at: newCoordinate, heading: newHeading, in: mapView)
            } else {
                updateTruckPosition(to: newCoordinate, heading: newHeading, in: mapView)
            }

            // Update camera to follow truck (Uber-style)
            updateCameraPosition(for: newCoordinate, heading: newHeading, in: mapView)

            previousCoordinate = newCoordinate
            previousHeading = newHeading
        }

        private func setupTruckAnnotation(at coordinate: CLLocationCoordinate2D, heading: CLLocationDirection, in mapView: MKMapView) {
            let annotation = TruckAnnotation(coordinate: coordinate, heading: heading)
            truckAnnotation = annotation
            mapView.addAnnotation(annotation)

            // Set initial 3D camera position
            let camera = MKMapCamera()
            camera.centerCoordinate = coordinate
            camera.centerCoordinateDistance = 800 // meters altitude
            camera.pitch = 60 // 3D pitch angle
            camera.heading = heading

            mapView.setCamera(camera, animated: false)
            isInitialPositionSet = true
        }

        private func updateTruckPosition(to newCoordinate: CLLocationCoordinate2D, heading: CLLocationDirection, in mapView: MKMapView) {
            guard let annotation = truckAnnotation else { return }

            // Smooth coordinate update with animation
            UIView.animate(withDuration: 0.7, delay: 0, options: [.curveLinear]) {
                annotation.coordinate = newCoordinate
            }

            // Update heading with smooth rotation
            if abs(heading - previousHeading) > headingChangeThreshold {
                if let annotationView = mapView.view(for: annotation) as? TruckAnnotationView {
                    annotationView.updateHeading(heading, animated: true)
                }
                annotation.heading = heading
            }
        }

        private func updateCameraPosition(for coordinate: CLLocationCoordinate2D, heading: CLLocationDirection, in mapView: MKMapView) {
            guard isInitialPositionSet else { return }

            // Calculate camera position slightly behind and above the truck (Uber-style)
            let camera = MKMapCamera()
            camera.centerCoordinate = coordinate

            // Position camera with offset (truck appears in lower third of screen)
            let verticalOffset = 0.00015 // Adjust based on zoom level
            let headingRadians = heading * .pi / 180
            let offsetLat = coordinate.latitude - (verticalOffset * cos(headingRadians))
            let offsetLng = coordinate.longitude - (verticalOffset * sin(headingRadians))

            camera.centerCoordinate = CLLocationCoordinate2D(latitude: offsetLat, longitude: offsetLng)
            camera.centerCoordinateDistance = 600 // meters altitude (closer for better 3D effect)
            camera.pitch = 58 // Sweet spot for 3D view
            camera.heading = heading

            // Smooth camera movement
            UIView.animate(withDuration: 0.8, delay: 0, options: [.curveEaseInOut, .beginFromCurrentState], animations: {
                mapView.setCamera(camera, animated: false)
            })
        }

        // MARK: - Nearby Jobs

        private var jobAnnotations: [MKPointAnnotation] = []

        func updateNearbyJobs(_ jobs: [DriverJob], in mapView: MKMapView) {
            // Remove old job annotations
            mapView.removeAnnotations(jobAnnotations)
            jobAnnotations.removeAll()

            // Add new job markers
            for job in jobs {
                guard let lat = job.lat, let lng = job.lng else { continue }
                let annotation = MKPointAnnotation()
                annotation.coordinate = CLLocationCoordinate2D(latitude: lat, longitude: lng)
                annotation.title = job.formattedPrice
                jobAnnotations.append(annotation)
            }

            mapView.addAnnotations(jobAnnotations)
        }

        // MARK: - Route

        private var currentRouteOverlay: MKPolyline?

        func updateRoute(_ route: MKRoute?, in mapView: MKMapView) {
            // Remove old route
            if let overlay = currentRouteOverlay {
                mapView.removeOverlay(overlay)
            }

            // Add new route
            if let route = route {
                currentRouteOverlay = route.polyline
                mapView.addOverlay(route.polyline)
            } else {
                currentRouteOverlay = nil
            }
        }

        // MARK: - MKMapViewDelegate

        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            // Custom truck annotation
            if annotation is TruckAnnotation {
                let view = mapView.dequeueReusableAnnotationView(
                    withIdentifier: TruckAnnotationView.reuseIdentifier,
                    for: annotation
                ) as! TruckAnnotationView

                // Set initial heading
                if let truckAnnotation = annotation as? TruckAnnotation {
                    view.updateHeading(truckAnnotation.heading, animated: false)
                }

                return view
            }

            // Job markers (standard pins)
            if annotation is MKPointAnnotation {
                let identifier = "JobMarker"
                let view = mapView.dequeueReusableAnnotationView(withIdentifier: identifier)
                    ?? MKMarkerAnnotationView(annotation: annotation, reuseIdentifier: identifier)

                if let markerView = view as? MKMarkerAnnotationView {
                    markerView.markerTintColor = UIColor(red: 0.863, green: 0.149, blue: 0.149, alpha: 1.0) // red-600
                    markerView.glyphText = "$"
                }

                return view
            }

            return nil
        }

        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            // Route polyline renderer
            if let polyline = overlay as? MKPolyline {
                let renderer = MKPolylineRenderer(polyline: polyline)
                renderer.strokeColor = UIColor(red: 0.863, green: 0.149, blue: 0.149, alpha: 1.0) // red-600
                renderer.lineWidth = 5.0
                renderer.lineCap = .round
                return renderer
            }

            return MKOverlayRenderer(overlay: overlay)
        }
    }
}

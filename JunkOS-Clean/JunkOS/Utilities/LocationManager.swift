//
//  LocationManager.swift
//  JunkOS
//
//  Simple location manager for address auto-detection
//

import CoreLocation
import SwiftUI

class LocationManager: NSObject, ObservableObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    @Published var location: CLLocation?
    @Published var authorizationStatus: CLAuthorizationStatus = .notDetermined
    
    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        authorizationStatus = manager.authorizationStatus
    }
    
    func requestLocation() {
        switch authorizationStatus {
        case .notDetermined:
            manager.requestWhenInUseAuthorization()
        case .authorizedWhenInUse, .authorizedAlways:
            manager.requestLocation()
        default:
            break
        }
    }
    
    func reverseGeocode(completion: @escaping (Result<Address, Error>) -> Void) {
        guard let location = location else {
            completion(.failure(NSError(domain: "LocationManager", code: -1, userInfo: [NSLocalizedDescriptionKey: "No location available"])))
            return
        }
        
        let geocoder = CLGeocoder()
        geocoder.reverseGeocodeLocation(location) { placemarks, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            
            guard let placemark = placemarks?.first else {
                completion(.failure(NSError(domain: "LocationManager", code: -2, userInfo: [NSLocalizedDescriptionKey: "No placemark found"])))
                return
            }
            
            let address = Address(
                street: [placemark.subThoroughfare, placemark.thoroughfare].compactMap { $0 }.joined(separator: " "),
                unit: placemark.subLocality ?? "",
                city: placemark.locality ?? "",
                state: placemark.administrativeArea ?? "",
                zipCode: placemark.postalCode ?? ""
            )
            
            completion(.success(address))
        }
    }
    
    // MARK: - CLLocationManagerDelegate
    
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        authorizationStatus = manager.authorizationStatus
        if authorizationStatus == .authorizedWhenInUse || authorizationStatus == .authorizedAlways {
            manager.requestLocation()
        }
    }
    
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        location = locations.last
    }
    
    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        print("Location error: \(error.localizedDescription)")
    }
}

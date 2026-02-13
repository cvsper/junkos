//
//  AddressInputViewModel.swift
//  Umuve
//
//  ViewModel for AddressInputView
//

import SwiftUI
import MapKit
import CoreLocation
import Combine

class AddressInputViewModel: ObservableObject {
    // MARK: - Published Properties
    @Published var region = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 27.9506, longitude: -82.4572), // Tampa
        span: MKCoordinateSpan(latitudeDelta: 0.05, longitudeDelta: 0.05)
    )
    @Published var elementsVisible = false
    @Published var isLoadingLocation = false
    @Published var locationError: String?
    
    // MARK: - Dependencies
    let locationManager: LocationManager
    
    // MARK: - Private Properties
    private var cancellables = Set<AnyCancellable>()
    private var locationCompletion: ((Result<Address, Error>) -> Void)?
    private var locationTimeoutTask: DispatchWorkItem?
    
    // MARK: - Initialization
    init(locationManager: LocationManager = LocationManager()) {
        self.locationManager = locationManager
        setupLocationObserver()
    }
    
    // MARK: - Private Methods
    
    /// Setup observer for location updates
    private func setupLocationObserver() {
        // Observe location updates
        locationManager.$location
            .compactMap { $0 }
            .sink { [weak self] location in
                self?.handleLocationUpdate(location)
            }
            .store(in: &cancellables)
        
        // Observe authorization status changes
        locationManager.$authorizationStatus
            .sink { [weak self] status in
                self?.handleAuthorizationChange(status)
            }
            .store(in: &cancellables)
    }
    
    /// Handle location update
    private func handleLocationUpdate(_ location: CLLocation) {
        // Cancel timeout
        locationTimeoutTask?.cancel()
        
        // Update map region
        region.center = location.coordinate
        
        // Perform reverse geocoding if we have a pending completion
        if locationCompletion != nil {
            locationManager.reverseGeocode { [weak self] result in
                guard let self = self else { return }
                self.isLoadingLocation = false
                
                switch result {
                case .success(let address):
                    HapticManager.shared.success()
                    self.locationError = nil
                    self.locationCompletion?(.success(address))
                    
                case .failure(let error):
                    HapticManager.shared.error()
                    self.locationError = "Unable to determine your address. Please enter it manually."
                    self.locationCompletion?(.failure(error))
                }
                
                self.locationCompletion = nil
            }
        }
    }
    
    /// Handle authorization status changes
    private func handleAuthorizationChange(_ status: CLAuthorizationStatus) {
        if status == .denied || status == .restricted {
            isLoadingLocation = false
            locationError = "Location access denied. Please enable in Settings."
            HapticManager.shared.error()
            
            let error = NSError(
                domain: "LocationManager",
                code: -3,
                userInfo: [NSLocalizedDescriptionKey: "Location access denied"]
            )
            locationCompletion?(.failure(error))
            locationCompletion = nil
        }
    }
    
    // MARK: - Public Methods
    
    /// Start entrance animations
    func startAnimations() {
        withAnimation(AnimationConstants.smoothSpring) {
            elementsVisible = true
        }
    }
    
    /// Request location and perform reverse geocoding
    func detectLocation(completion: @escaping (Result<Address, Error>) -> Void) {
        // Check if already loading
        guard !isLoadingLocation else { return }
        
        isLoadingLocation = true
        locationError = nil
        locationCompletion = completion
        
        // Set timeout (10 seconds)
        let timeoutTask = DispatchWorkItem { [weak self] in
            guard let self = self else { return }
            self.isLoadingLocation = false
            self.locationError = "Location request timed out. Please try again or enter manually."
            HapticManager.shared.error()
            
            let error = NSError(
                domain: "LocationManager",
                code: -4,
                userInfo: [NSLocalizedDescriptionKey: "Location request timed out"]
            )
            self.locationCompletion?(.failure(error))
            self.locationCompletion = nil
        }
        locationTimeoutTask = timeoutTask
        DispatchQueue.main.asyncAfter(deadline: .now() + 10.0, execute: timeoutTask)
        
        // Request location
        locationManager.requestLocation()
    }
    
    /// Validate address completeness
    func isAddressValid(street: String, city: String, zipCode: String) -> Bool {
        !street.isEmpty && !city.isEmpty && !zipCode.isEmpty
    }
}

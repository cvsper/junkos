//
//  AddressInputViewModel.swift
//  Umuve
//
//  ViewModel for AddressInputView with MapKit autocomplete
//

import SwiftUI
import MapKit
import CoreLocation
import Combine

// MARK: - Search Mode
enum SearchMode {
    case pickup
    case dropoff
}

// MARK: - AddressInputViewModel
class AddressInputViewModel: NSObject, ObservableObject {
    // MARK: - Published Properties

    // Search queries
    @Published var pickupSearchQuery = ""
    @Published var dropoffSearchQuery = ""

    // Autocomplete results
    @Published var pickupCompletions: [MKLocalSearchCompletion] = []
    @Published var dropoffCompletions: [MKLocalSearchCompletion] = []

    // UI state
    @Published var isSearching = false
    @Published var pickupSelected = false
    @Published var dropoffSelected = false

    // Map regions
    @Published var pickupRegion = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194), // US center
        span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
    )
    @Published var dropoffRegion = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194),
        span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
    )

    // Calculation results
    @Published var calculatedDistance: Double?
    @Published var locationError: String?

    // MARK: - Private Properties
    private let completer = MKLocalSearchCompleter()
    private var searchMode: SearchMode = .pickup
    private var cancellables = Set<AnyCancellable>()
    private let locationManager = CLLocationManager()

    // MARK: - Initialization
    override init() {
        super.init()

        // Configure completer
        completer.delegate = self
        completer.resultTypes = .address

        // Setup debounced search for pickup
        $pickupSearchQuery
            .debounce(for: .milliseconds(300), scheduler: DispatchQueue.main)
            .removeDuplicates()
            .sink { [weak self] query in
                self?.updateCompleterQuery(query: query, mode: .pickup)
            }
            .store(in: &cancellables)

        // Setup debounced search for dropoff
        $dropoffSearchQuery
            .debounce(for: .milliseconds(300), scheduler: DispatchQueue.main)
            .removeDuplicates()
            .sink { [weak self] query in
                self?.updateCompleterQuery(query: query, mode: .dropoff)
            }
            .store(in: &cancellables)
    }

    // MARK: - Private Methods

    /// Update completer query based on search mode
    private func updateCompleterQuery(query: String, mode: SearchMode) {
        searchMode = mode

        // Clear completions if query is empty
        guard !query.isEmpty else {
            DispatchQueue.main.async { [weak self] in
                switch mode {
                case .pickup:
                    self?.pickupCompletions = []
                case .dropoff:
                    self?.dropoffCompletions = []
                }
            }
            return
        }

        // Update completer
        isSearching = true
        completer.queryFragment = query
    }

    // MARK: - Public Methods

    /// Select pickup address from autocomplete
    func selectPickupAddress(_ completion: MKLocalSearchCompletion, bookingData: BookingData) {
        geocodeCompletion(completion) { [weak self] result in
            guard let self = self else { return }

            switch result {
            case .success(let placemark):
                DispatchQueue.main.async {
                    // Update address
                    bookingData.address.street = [
                        placemark.subThoroughfare,
                        placemark.thoroughfare
                    ].compactMap { $0 }.joined(separator: " ")
                    bookingData.address.city = placemark.locality ?? ""
                    bookingData.address.state = placemark.administrativeArea ?? "FL"
                    bookingData.address.zipCode = placemark.postalCode ?? ""

                    // Update coordinate
                    bookingData.pickupCoordinate = placemark.location?.coordinate

                    // Update map region
                    if let coordinate = placemark.location?.coordinate {
                        self.pickupRegion = MKCoordinateRegion(
                            center: coordinate,
                            span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
                        )
                    }

                    // Mark as selected
                    self.pickupSelected = true
                    self.pickupCompletions = []
                    self.locationError = nil
                }

            case .failure(let error):
                DispatchQueue.main.async {
                    self.locationError = "Could not geocode address: \(error.localizedDescription)"
                }
            }
        }
    }

    /// Select dropoff address from autocomplete
    func selectDropoffAddress(_ completion: MKLocalSearchCompletion, bookingData: BookingData) {
        geocodeCompletion(completion) { [weak self] result in
            guard let self = self else { return }

            switch result {
            case .success(let placemark):
                DispatchQueue.main.async {
                    // Update dropoff address
                    bookingData.dropoffAddress.street = [
                        placemark.subThoroughfare,
                        placemark.thoroughfare
                    ].compactMap { $0 }.joined(separator: " ")
                    bookingData.dropoffAddress.city = placemark.locality ?? ""
                    bookingData.dropoffAddress.state = placemark.administrativeArea ?? "FL"
                    bookingData.dropoffAddress.zipCode = placemark.postalCode ?? ""

                    // Update coordinate
                    bookingData.dropoffCoordinate = placemark.location?.coordinate

                    // Update map region
                    if let coordinate = placemark.location?.coordinate {
                        self.dropoffRegion = MKCoordinateRegion(
                            center: coordinate,
                            span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
                        )
                    }

                    // Mark as selected
                    self.dropoffSelected = true
                    self.dropoffCompletions = []
                    self.locationError = nil
                }

            case .failure(let error):
                DispatchQueue.main.async {
                    self.locationError = "Could not geocode address: \(error.localizedDescription)"
                }
            }
        }
    }

    /// Geocode a completion to get full address and coordinates
    private func geocodeCompletion(_ completion: MKLocalSearchCompletion, handler: @escaping (Result<CLPlacemark, Error>) -> Void) {
        let searchRequest = MKLocalSearch.Request(completion: completion)
        let search = MKLocalSearch(request: searchRequest)

        search.start { response, error in
            if let error = error {
                handler(.failure(error))
                return
            }

            guard let mapItem = response?.mapItems.first,
                  let placemark = mapItem.placemark as CLPlacemark? else {
                let error = NSError(
                    domain: "AddressInputViewModel",
                    code: -1,
                    userInfo: [NSLocalizedDescriptionKey: "No results found"]
                )
                handler(.failure(error))
                return
            }

            handler(.success(placemark))
        }
    }

    /// Calculate distance between pickup and dropoff
    func calculateDistance(bookingData: BookingData) {
        guard let pickupCoord = bookingData.pickupCoordinate,
              let dropoffCoord = bookingData.dropoffCoordinate else {
            locationError = "Both addresses required for distance calculation"
            return
        }

        let pickupLocation = CLLocation(latitude: pickupCoord.latitude, longitude: pickupCoord.longitude)
        let dropoffLocation = CLLocation(latitude: dropoffCoord.latitude, longitude: dropoffCoord.longitude)

        // Calculate distance in meters
        let distanceMeters = pickupLocation.distance(from: dropoffLocation)

        // Convert to miles
        let distanceMiles = distanceMeters / 1609.34

        // Update bookingData and local state
        bookingData.estimatedDistance = distanceMiles
        calculatedDistance = distanceMiles
    }

    /// Detect current location and set as pickup address
    func detectCurrentLocation(bookingData: BookingData) {
        locationManager.requestWhenInUseAuthorization()

        guard let currentLocation = locationManager.location else {
            locationError = "Could not get current location"
            return
        }

        // Reverse geocode
        let geocoder = CLGeocoder()
        geocoder.reverseGeocodeLocation(currentLocation) { [weak self] placemarks, error in
            guard let self = self else { return }

            if let error = error {
                DispatchQueue.main.async {
                    self.locationError = "Could not determine address: \(error.localizedDescription)"
                }
                return
            }

            guard let placemark = placemarks?.first else {
                DispatchQueue.main.async {
                    self.locationError = "No address found for current location"
                }
                return
            }

            DispatchQueue.main.async {
                // Update address
                bookingData.address.street = [
                    placemark.subThoroughfare,
                    placemark.thoroughfare
                ].compactMap { $0 }.joined(separator: " ")
                bookingData.address.city = placemark.locality ?? ""
                bookingData.address.state = placemark.administrativeArea ?? "FL"
                bookingData.address.zipCode = placemark.postalCode ?? ""

                // Update coordinate
                bookingData.pickupCoordinate = currentLocation.coordinate

                // Update map region
                self.pickupRegion = MKCoordinateRegion(
                    center: currentLocation.coordinate,
                    span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
                )

                // Mark as selected
                self.pickupSelected = true
                self.pickupSearchQuery = bookingData.address.fullAddress
                self.locationError = nil
            }
        }
    }

    /// Set active search mode (for manual control if needed)
    func setSearchMode(_ mode: SearchMode) {
        searchMode = mode
    }
}

// MARK: - MKLocalSearchCompleterDelegate
extension AddressInputViewModel: MKLocalSearchCompleterDelegate {
    func completerDidUpdateResults(_ completer: MKLocalSearchCompleter) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }

            self.isSearching = false

            // Update appropriate completions array based on current search mode
            switch self.searchMode {
            case .pickup:
                self.pickupCompletions = completer.results
            case .dropoff:
                self.dropoffCompletions = completer.results
            }
        }
    }

    func completer(_ completer: MKLocalSearchCompleter, didFailWithError error: Error) {
        DispatchQueue.main.async { [weak self] in
            self?.isSearching = false
            self?.locationError = "Search failed: \(error.localizedDescription)"
        }
    }
}

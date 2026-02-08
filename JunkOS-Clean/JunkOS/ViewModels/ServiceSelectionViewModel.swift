//
//  ServiceSelectionViewModel.swift
//  JunkOS
//
//  ViewModel for ServiceSelectionView
//

import SwiftUI
import Combine

class ServiceSelectionViewModel: ObservableObject {
    // MARK: - Published Properties
    @Published var selectedServices: Set<String> = []
    @Published var serviceDetails: String = ""
    @Published var availableServices: [Service] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    
    private let apiClient = APIClient.shared
    
    // MARK: - Initialization
    
    init() {
        Task {
            await loadServices()
        }
    }
    
    // MARK: - Public Methods
    
    /// Load services from API
    @MainActor
    func loadServices() async {
        isLoading = true
        errorMessage = nil
        
        do {
            let apiServices = try await apiClient.getServices()
            availableServices = apiServices.map { $0.toService() }
            
            // If no services from API, fallback to local services
            if availableServices.isEmpty {
                availableServices = Service.all
            }
        } catch {
            errorMessage = error.localizedDescription
            // Fallback to local services on error
            availableServices = Service.all
            print("Error loading services: \(error)")
        }
        
        isLoading = false
    }
    
    /// Toggle service selection
    func toggleService(_ serviceId: String) {
        HapticManager.shared.lightTap()
        
        if selectedServices.contains(serviceId) {
            selectedServices.remove(serviceId)
        } else {
            selectedServices.insert(serviceId)
        }
    }
    
    /// Check if any service is selected
    var hasSelectedServices: Bool {
        !selectedServices.isEmpty
    }
    
    /// Check if a specific service is selected
    func isSelected(_ serviceId: String) -> Bool {
        selectedServices.contains(serviceId)
    }
    
    /// Get selected service names
    func getSelectedServiceNames() -> [String] {
        selectedServices.compactMap { serviceId in
            availableServices.first(where: { $0.id == serviceId })?.name
        }
    }
}

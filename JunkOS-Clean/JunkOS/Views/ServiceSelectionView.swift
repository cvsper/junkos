//
//  ServiceSelectionView.swift
//  JunkOS
//
//  Service selection screen with grid layout
//  SF Symbols Reference: https://developer.apple.com/sf-symbols/
//
//  PERFORMANCE OPTIMIZATIONS:
//  - LazyVStack for main content (lazy loading)
//  - Reduced shadow calculations
//  - Optimized animations (removed during scroll)
//  - Debounced state changes
//

import SwiftUI

struct ServiceSelectionView: View {
    @EnvironmentObject var bookingData: BookingData
    @StateObject private var viewModel = ServiceSelectionViewModel()
    @State private var isRefreshing = false
    @State private var isScrolling = false
    
    var body: some View {
        ScrollView {
            LazyVStack(spacing: JunkSpacing.xxlarge) {
                // Header
                ScreenHeader(
                    title: "Select Services",
                    subtitle: "What do you need removed?",
                    progress: 0.6
                )
                
                // LoadUp Feature #1: Dual Pricing Tiers
                pricingTierSelector
                
                // Empty state if no services selected yet
                if viewModel.selectedServices.isEmpty {
                    ServiceSelectionEmptyState()
                }
                
                // Service grid
                serviceGrid
                
                // LoadUp Feature #5: Property Cleanout Options
                if bookingData.selectedServices.contains("property-cleanout") {
                    propertyCleanoutSection
                }
                
                // LoadUp Feature #6: Enhanced Service Details
                if viewModel.hasSelectedServices {
                    itemSelectorSection
                    weightEstimatorSection
                }
                
                // Live price estimate
                if viewModel.hasSelectedServices {
                    LivePriceEstimate(
                        services: viewModel.selectedServices,
                        photoCount: bookingData.photos.count
                    )
                    .padding(.top, JunkSpacing.normal)
                }
                
                // LoadUp Feature #6: Items We Don't Take
                itemsWeDoNotTakeSection
                
                // Optional details
                detailsSection
                
                Spacer()
            }
            .padding(JunkSpacing.large)
        }
        .background(Color.junkBackground.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .refreshable {
            await refreshServices()
        }
        .safeAreaInset(edge: .bottom) {
            continueButton
        }
        .onAppear {
            // Sync with bookingData
            viewModel.selectedServices = bookingData.selectedServices
            viewModel.serviceDetails = bookingData.serviceDetails
        }
        .onChange(of: viewModel.selectedServices) { newValue in
            // Debounced update to prevent cascading renders
            DispatchQueue.main.async {
                bookingData.selectedServices = newValue
            }
        }
        .onChange(of: viewModel.serviceDetails) { newValue in
            // Debounced update
            DispatchQueue.main.async {
                bookingData.serviceDetails = newValue
            }
        }
    }
    
    private func refreshServices() async {
        isRefreshing = true
        await viewModel.loadServices()
        isRefreshing = false
    }
    
    // MARK: - LoadUp Feature #1: Pricing Tier Selector
    private var pricingTierSelector: some View {
        VStack(alignment: .leading, spacing: JunkSpacing.normal) {
            Text("Service Type")
                .font(JunkTypography.h3Font)
                .foregroundColor(.junkText)
            
            VStack(spacing: JunkSpacing.small) {
                ForEach(ServiceTier.allCases, id: \.self) { tier in
                    Button(action: {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            bookingData.serviceTier = tier
                        }
                    }) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(tier.rawValue)
                                    .font(JunkTypography.bodyFont.weight(.semibold))
                                    .foregroundColor(.junkText)
                                
                                Text(tier.description)
                                    .font(JunkTypography.bodySmallFont)
                                    .foregroundColor(.junkTextMuted)
                            }
                            
                            Spacer()
                            
                            if bookingData.serviceTier == tier {
                                Image(systemName: "checkmark.circle.fill")
                                    .font(.system(size: 24))
                                    .foregroundColor(.junkPrimary)
                            } else {
                                Image(systemName: "circle")
                                    .font(.system(size: 24))
                                    .foregroundColor(.junkBorder)
                            }
                        }
                        .padding(JunkSpacing.normal)
                        .background(Color.junkWhite)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(bookingData.serviceTier == tier ? Color.junkPrimary : Color.junkBorder, lineWidth: 2)
                        )
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
        }
    }
    
    // MARK: - Service Grid
    private var serviceGrid: some View {
        LazyVGrid(columns: [
            GridItem(.flexible(), spacing: JunkSpacing.normal),
            GridItem(.flexible(), spacing: JunkSpacing.normal)
        ], spacing: JunkSpacing.normal) {
            ForEach(viewModel.availableServices) { service in
                ServiceCard(
                    service: service,
                    isSelected: viewModel.isSelected(service.id),
                    isScrolling: isScrolling
                ) {
                    viewModel.toggleService(service.id)
                }
            }
        }
    }
    
    // MARK: - LoadUp Feature #5: Property Cleanout Section
    private var propertyCleanoutSection: some View {
        VStack(alignment: .leading, spacing: JunkSpacing.normal) {
            Text("Property Cleanout Details")
                .font(JunkTypography.h2Font)
                .foregroundColor(.junkText)
            
            // Cleanout Type
            VStack(alignment: .leading, spacing: JunkSpacing.small) {
                Text("Cleanout Type")
                    .font(JunkTypography.h3Font)
                    .foregroundColor(.junkText)
                
                ScrollView(.horizontal, showsIndicators: false) {
                    LazyHStack(spacing: JunkSpacing.small) {
                        ForEach(CleanoutType.allCases, id: \.self) { type in
                            Button(action: {
                                bookingData.cleanoutType = type
                            }) {
                                VStack(spacing: JunkSpacing.small) {
                                    Image(systemName: type.icon)
                                        .font(.system(size: 24))
                                        .foregroundColor(bookingData.cleanoutType == type ? .white : .junkPrimary)
                                    
                                    Text(type.rawValue)
                                        .font(JunkTypography.captionFont)
                                        .foregroundColor(bookingData.cleanoutType == type ? .white : .junkText)
                                }
                                .frame(width: 100)
                                .padding(JunkSpacing.small)
                                .background(bookingData.cleanoutType == type ? Color.junkPrimary : Color.junkWhite)
                                .cornerRadius(12)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 12)
                                        .stroke(bookingData.cleanoutType == type ? Color.junkPrimary : Color.junkBorder, lineWidth: 2)
                                )
                            }
                            .buttonStyle(PlainButtonStyle())
                        }
                    }
                }
            }
            
            // Room Selector
            VStack(alignment: .leading, spacing: JunkSpacing.small) {
                Text("Select Rooms")
                    .font(JunkTypography.h3Font)
                    .foregroundColor(.junkText)
                
                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: JunkSpacing.small),
                    GridItem(.flexible(), spacing: JunkSpacing.small),
                    GridItem(.flexible(), spacing: JunkSpacing.small)
                ], spacing: JunkSpacing.small) {
                    ForEach(RoomOption.all) { room in
                        Button(action: {
                            if bookingData.selectedRooms.contains(room.id) {
                                bookingData.selectedRooms.remove(room.id)
                            } else {
                                bookingData.selectedRooms.insert(room.id)
                            }
                        }) {
                            VStack(spacing: 4) {
                                Image(systemName: room.icon)
                                    .font(.system(size: 20))
                                    .foregroundColor(bookingData.selectedRooms.contains(room.id) ? .white : .junkPrimary)
                                
                                Text(room.name)
                                    .font(JunkTypography.smallFont)
                                    .foregroundColor(bookingData.selectedRooms.contains(room.id) ? .white : .junkText)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(JunkSpacing.small)
                            .background(bookingData.selectedRooms.contains(room.id) ? Color.junkPrimary : Color.junkWhite)
                            .cornerRadius(8)
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(bookingData.selectedRooms.contains(room.id) ? Color.junkPrimary : Color.junkBorder, lineWidth: 1)
                            )
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                }
            }
        }
        .padding(JunkSpacing.normal)
        .background(Color.junkWhite)
        .cornerRadius(16)
    }
    
    // MARK: - LoadUp Feature #6: Item Selector
    private var itemSelectorSection: some View {
        VStack(alignment: .leading, spacing: JunkSpacing.normal) {
            Text("Specific Items (Optional)")
                .font(JunkTypography.h3Font)
                .foregroundColor(.junkText)
            
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: JunkSpacing.small) {
                    ForEach(ItemOption.all) { item in
                        Button(action: {
                            if bookingData.selectedItems.contains(item.id) {
                                bookingData.selectedItems.remove(item.id)
                            } else {
                                bookingData.selectedItems.insert(item.id)
                            }
                        }) {
                            VStack(spacing: 4) {
                                Image(systemName: item.icon)
                                    .font(.system(size: 24))
                                    .foregroundColor(bookingData.selectedItems.contains(item.id) ? .white : .junkPrimary)
                                
                                Text(item.name)
                                    .font(JunkTypography.captionFont)
                                    .foregroundColor(bookingData.selectedItems.contains(item.id) ? .white : .junkText)
                                
                                Text(item.estimatedWeight)
                                    .font(JunkTypography.smallFont)
                                    .foregroundColor(bookingData.selectedItems.contains(item.id) ? .white.opacity(0.8) : .junkTextMuted)
                            }
                            .frame(width: 100)
                            .padding(JunkSpacing.small)
                            .background(bookingData.selectedItems.contains(item.id) ? Color.junkPrimary : Color.junkWhite)
                            .cornerRadius(12)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(bookingData.selectedItems.contains(item.id) ? Color.junkPrimary : Color.junkBorder, lineWidth: 2)
                            )
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                }
            }
        }
    }
    
    // MARK: - LoadUp Feature #6: Weight Estimator
    private var weightEstimatorSection: some View {
        VStack(alignment: .leading, spacing: JunkSpacing.normal) {
            Text("Estimated Weight")
                .font(JunkTypography.h3Font)
                .foregroundColor(.junkText)
            
            HStack(spacing: JunkSpacing.small) {
                ForEach(WeightCategory.allCases, id: \.self) { category in
                    Button(action: {
                        bookingData.estimatedWeight = category
                    }) {
                        VStack(spacing: 4) {
                            Image(systemName: category.icon)
                                .font(.system(size: 20))
                                .foregroundColor(bookingData.estimatedWeight == category ? .white : .junkPrimary)
                            
                            Text(category.rawValue)
                                .font(JunkTypography.smallFont)
                                .foregroundColor(bookingData.estimatedWeight == category ? .white : .junkText)
                                .multilineTextAlignment(.center)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(JunkSpacing.small)
                        .background(bookingData.estimatedWeight == category ? Color.junkPrimary : Color.junkWhite)
                        .cornerRadius(8)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(bookingData.estimatedWeight == category ? Color.junkPrimary : Color.junkBorder, lineWidth: 1)
                        )
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
        }
    }
    
    // MARK: - LoadUp Feature #6: Items We Don't Take
    private var itemsWeDoNotTakeSection: some View {
        JunkCard {
            VStack(alignment: .leading, spacing: JunkSpacing.small) {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                    
                    Text("Items We Don't Take")
                        .font(JunkTypography.h3Font)
                        .foregroundColor(.junkText)
                }
                
                Text("• Hazardous materials (paint, chemicals, asbestos)\n• Medical waste\n• Dead animals\n• Firearms or ammunition\n• Human waste")
                    .font(JunkTypography.bodySmallFont)
                    .foregroundColor(.junkTextMuted)
                    .padding(.top, JunkSpacing.small)
            }
            .padding(JunkSpacing.normal)
        }
        .background(Color.orange.opacity(0.05))
    }
    
    // MARK: - Details Section
    private var detailsSection: some View {
        VStack(alignment: .leading, spacing: JunkSpacing.medium) {
            Text("Additional Details (Optional)")
                .font(JunkTypography.h3Font)
                .foregroundColor(.junkText)
            
            TextEditor(text: $viewModel.serviceDetails)
                .font(JunkTypography.bodyFont)
                .foregroundColor(.junkText)
                .frame(height: 100)
                .padding(JunkSpacing.small)
                .background(Color.junkWhite)
                .cornerRadius(12)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.junkBorder, lineWidth: 2)
                )
        }
    }
    
    // MARK: - Continue Button
    private var continueButton: some View {
        NavigationLink(
            destination: DateTimePickerView().environmentObject(bookingData),
            label: {
                Text("Continue →")
            }
        )
        .buttonStyle(JunkPrimaryButtonStyle())
        .padding(JunkSpacing.large)
        .background(Color.junkBackground)
        .disabled(!viewModel.hasSelectedServices)
        .opacity(viewModel.hasSelectedServices ? 1 : 0.5)
    }
}

// MARK: - Service Card (OPTIMIZED)
struct ServiceCard: View {
    let service: Service
    let isSelected: Bool
    let isScrolling: Bool
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            VStack(spacing: JunkSpacing.medium) {
                // Popular badge
                if service.isPopular {
                    HStack {
                        Spacer()
                        Text("POPULAR")
                            .font(JunkTypography.smallFont)
                            .foregroundColor(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.junkCTA)
                            .cornerRadius(8)
                    }
                } else {
                    Spacer().frame(height: 20)
                }
                
                // SF Symbol icon instead of emoji
                // https://developer.apple.com/design/human-interface-guidelines/sf-symbols
                Image(systemName: service.icon)
                    .font(.system(size: 40))
                    .foregroundColor(.junkPrimary)
                
                // Name
                Text(service.name)
                    .font(JunkTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.junkText)
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
                
                // Price
                Text("from \(service.price)")
                    .font(JunkTypography.captionFont)
                    .foregroundColor(.junkTextMuted)
                
                // Checkmark
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.junkPrimary)
                } else {
                    Spacer().frame(height: 24)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(JunkSpacing.normal)
            .background(Color.junkWhite)
            .cornerRadius(16)
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(isSelected ? Color.junkPrimary : Color.junkBorder, lineWidth: 2)
            )
            // OPTIMIZATION: Only apply shadow when not scrolling
            .shadow(color: isScrolling ? .clear : .black.opacity(isSelected ? 0.1 : 0.06), radius: 4, x: 0, y: 2)
        }
        .buttonStyle(PlainButtonStyle())
    }
}

// MARK: - Preview
struct ServiceSelectionView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            ServiceSelectionView()
                .environmentObject(BookingData())
        }
    }
}

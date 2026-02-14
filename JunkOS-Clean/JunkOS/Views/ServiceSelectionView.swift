//
//  ServiceSelectionView.swift
//  Umuve
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
    @State private var serviceDetails: String = ""
    
    var body: some View {
        ScrollView {
            LazyVStack(spacing: UmuveSpacing.xxlarge) {
                // Header
                ScreenHeader(
                    title: "Select Services",
                    subtitle: "What do you need removed?",
                    progress: 0.6
                )
                
                // LoadUp Feature #1: Dual Pricing Tiers
                pricingTierSelector
                
                // Empty state if no services selected yet
                if bookingData.selectedServices.isEmpty {
                    ServiceSelectionEmptyState()
                }
                
                // Service grid
                serviceGrid
                
                // LoadUp Feature #5: Property Cleanout Options
                if bookingData.selectedServices.contains("property-cleanout") {
                    propertyCleanoutSection
                }
                
                // LoadUp Feature #6: Enhanced Service Details
                if !bookingData.selectedServices.isEmpty {
                    itemSelectorSection
                    weightEstimatorSection
                }
                
                // LoadUp Feature #6: Items We Don't Take
                itemsWeDoNotTakeSection
                
                // Optional details
                detailsSection
                
                Spacer()
            }
            .padding(UmuveSpacing.large)
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) {
            continueButton
        }
        .onAppear {
            // Legacy view - use bookingData directly
            serviceDetails = bookingData.serviceDetails
        }
    }
    
    // MARK: - LoadUp Feature #1: Pricing Tier Selector
    private var pricingTierSelector: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("Service Type")
                .font(UmuveTypography.h3Font)
                .foregroundColor(.umuveText)
            
            VStack(spacing: UmuveSpacing.small) {
                ForEach(ServiceTier.allCases, id: \.self) { tier in
                    Button(action: {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            bookingData.serviceTier = tier
                        }
                    }) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(tier.rawValue)
                                    .font(UmuveTypography.bodyFont.weight(.semibold))
                                    .foregroundColor(.umuveText)
                                
                                Text(tier.description)
                                    .font(UmuveTypography.bodySmallFont)
                                    .foregroundColor(.umuveTextMuted)
                            }
                            
                            Spacer()
                            
                            if bookingData.serviceTier == tier {
                                Image(systemName: "checkmark.circle.fill")
                                    .font(.system(size: 24))
                                    .foregroundColor(.umuvePrimary)
                            } else {
                                Image(systemName: "circle")
                                    .font(.system(size: 24))
                                    .foregroundColor(.umuveBorder)
                            }
                        }
                        .padding(UmuveSpacing.normal)
                        .background(Color.umuveWhite)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(bookingData.serviceTier == tier ? Color.umuvePrimary : Color.umuveBorder, lineWidth: 2)
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
            GridItem(.flexible(), spacing: UmuveSpacing.normal),
            GridItem(.flexible(), spacing: UmuveSpacing.normal)
        ], spacing: UmuveSpacing.normal) {
            ForEach(Service.all) { service in
                ServiceCard(
                    service: service,
                    isSelected: bookingData.selectedServices.contains(service.id),
                    isScrolling: isScrolling
                ) {
                    if bookingData.selectedServices.contains(service.id) {
                        bookingData.selectedServices.remove(service.id)
                    } else {
                        bookingData.selectedServices.insert(service.id)
                    }
                }
            }
        }
    }
    
    // MARK: - LoadUp Feature #5: Property Cleanout Section
    private var propertyCleanoutSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("Property Cleanout Details")
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)
            
            // Cleanout Type
            VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                Text("Cleanout Type")
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.umuveText)
                
                ScrollView(.horizontal, showsIndicators: false) {
                    LazyHStack(spacing: UmuveSpacing.small) {
                        ForEach(CleanoutType.allCases, id: \.self) { type in
                            Button(action: {
                                bookingData.cleanoutType = type
                            }) {
                                VStack(spacing: UmuveSpacing.small) {
                                    Image(systemName: type.icon)
                                        .font(.system(size: 24))
                                        .foregroundColor(bookingData.cleanoutType == type ? .white : .umuvePrimary)
                                    
                                    Text(type.rawValue)
                                        .font(UmuveTypography.captionFont)
                                        .foregroundColor(bookingData.cleanoutType == type ? .white : .umuveText)
                                }
                                .frame(width: 100)
                                .padding(UmuveSpacing.small)
                                .background(bookingData.cleanoutType == type ? Color.umuvePrimary : Color.umuveWhite)
                                .cornerRadius(12)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 12)
                                        .stroke(bookingData.cleanoutType == type ? Color.umuvePrimary : Color.umuveBorder, lineWidth: 2)
                                )
                            }
                            .buttonStyle(PlainButtonStyle())
                        }
                    }
                }
            }
            
            // Room Selector
            VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                Text("Select Rooms")
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.umuveText)
                
                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: UmuveSpacing.small),
                    GridItem(.flexible(), spacing: UmuveSpacing.small),
                    GridItem(.flexible(), spacing: UmuveSpacing.small)
                ], spacing: UmuveSpacing.small) {
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
                                    .foregroundColor(bookingData.selectedRooms.contains(room.id) ? .white : .umuvePrimary)
                                
                                Text(room.name)
                                    .font(UmuveTypography.smallFont)
                                    .foregroundColor(bookingData.selectedRooms.contains(room.id) ? .white : .umuveText)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(UmuveSpacing.small)
                            .background(bookingData.selectedRooms.contains(room.id) ? Color.umuvePrimary : Color.umuveWhite)
                            .cornerRadius(8)
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(bookingData.selectedRooms.contains(room.id) ? Color.umuvePrimary : Color.umuveBorder, lineWidth: 1)
                            )
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                }
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .cornerRadius(16)
    }
    
    // MARK: - LoadUp Feature #6: Item Selector
    private var itemSelectorSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("Specific Items (Optional)")
                .font(UmuveTypography.h3Font)
                .foregroundColor(.umuveText)
            
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: UmuveSpacing.small) {
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
                                    .foregroundColor(bookingData.selectedItems.contains(item.id) ? .white : .umuvePrimary)
                                
                                Text(item.name)
                                    .font(UmuveTypography.captionFont)
                                    .foregroundColor(bookingData.selectedItems.contains(item.id) ? .white : .umuveText)
                                
                                Text(item.estimatedWeight)
                                    .font(UmuveTypography.smallFont)
                                    .foregroundColor(bookingData.selectedItems.contains(item.id) ? .white.opacity(0.8) : .umuveTextMuted)
                            }
                            .frame(width: 100)
                            .padding(UmuveSpacing.small)
                            .background(bookingData.selectedItems.contains(item.id) ? Color.umuvePrimary : Color.umuveWhite)
                            .cornerRadius(12)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(bookingData.selectedItems.contains(item.id) ? Color.umuvePrimary : Color.umuveBorder, lineWidth: 2)
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
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("Estimated Weight")
                .font(UmuveTypography.h3Font)
                .foregroundColor(.umuveText)
            
            HStack(spacing: UmuveSpacing.small) {
                ForEach(WeightCategory.allCases, id: \.self) { category in
                    Button(action: {
                        bookingData.estimatedWeight = category
                    }) {
                        VStack(spacing: 4) {
                            Image(systemName: category.icon)
                                .font(.system(size: 20))
                                .foregroundColor(bookingData.estimatedWeight == category ? .white : .umuvePrimary)
                            
                            Text(category.rawValue)
                                .font(UmuveTypography.smallFont)
                                .foregroundColor(bookingData.estimatedWeight == category ? .white : .umuveText)
                                .multilineTextAlignment(.center)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(UmuveSpacing.small)
                        .background(bookingData.estimatedWeight == category ? Color.umuvePrimary : Color.umuveWhite)
                        .cornerRadius(8)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(bookingData.estimatedWeight == category ? Color.umuvePrimary : Color.umuveBorder, lineWidth: 1)
                        )
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
        }
    }
    
    // MARK: - LoadUp Feature #6: Items We Don't Take
    private var itemsWeDoNotTakeSection: some View {
        UmuveCard {
            VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                    
                    Text("Items We Don't Take")
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)
                }
                
                Text("• Hazardous materials (paint, chemicals, asbestos)\n• Medical waste\n• Dead animals\n• Firearms or ammunition\n• Human waste")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
                    .padding(.top, UmuveSpacing.small)
            }
            .padding(UmuveSpacing.normal)
        }
        .background(Color.orange.opacity(0.05))
    }
    
    // MARK: - Details Section
    private var detailsSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.medium) {
            Text("Additional Details (Optional)")
                .font(UmuveTypography.h3Font)
                .foregroundColor(.umuveText)
            
            TextEditor(text: $serviceDetails)
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveText)
                .frame(height: 100)
                .padding(UmuveSpacing.small)
                .background(Color.umuveWhite)
                .cornerRadius(12)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.umuveBorder, lineWidth: 2)
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
        .buttonStyle(UmuvePrimaryButtonStyle())
        .padding(UmuveSpacing.large)
        .background(Color.umuveBackground)
        .disabled(bookingData.selectedServices.isEmpty)
        .opacity(bookingData.selectedServices.isEmpty ? 0.5 : 1)
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
            VStack(spacing: UmuveSpacing.medium) {
                // Popular badge
                if service.isPopular {
                    HStack {
                        Spacer()
                        Text("POPULAR")
                            .font(UmuveTypography.smallFont)
                            .foregroundColor(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.umuveCTA)
                            .cornerRadius(8)
                    }
                } else {
                    Spacer().frame(height: 20)
                }
                
                // SF Symbol icon instead of emoji
                // https://developer.apple.com/design/human-interface-guidelines/sf-symbols
                Image(systemName: service.icon)
                    .font(.system(size: 40))
                    .foregroundColor(.umuvePrimary)
                
                // Name
                Text(service.name)
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
                
                // Price
                Text("from \(service.price)")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.umuveTextMuted)
                
                // Checkmark
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.umuvePrimary)
                } else {
                    Spacer().frame(height: 24)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(UmuveSpacing.normal)
            .background(Color.umuveWhite)
            .cornerRadius(16)
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(isSelected ? Color.umuvePrimary : Color.umuveBorder, lineWidth: 2)
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

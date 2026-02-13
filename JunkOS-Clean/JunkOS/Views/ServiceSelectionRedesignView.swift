//
//  ServiceSelectionRedesignView.swift
//  Umuve
//
//  Redesigned service selection (LoadUp-inspired)
//

import SwiftUI

struct ServiceSelectionRedesignView: View {
    @EnvironmentObject var bookingData: BookingData
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            VStack(spacing: UmuveSpacing.large) {
                // Address display (editable)
                addressHeader

                // Service category cards
                serviceCategoryCards
            }
            .padding(UmuveSpacing.large)
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(true)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button(action: { dismiss() }) {
                    Image(systemName: "chevron.left")
                        .foregroundColor(.umuveText)
                }
            }
            ToolbarItem(placement: .principal) {
                Text("Select Service")
                    .font(UmuveTypography.h3Font)
            }
        }
    }

    // MARK: - Address Header
    private var addressHeader: some View {
        HStack {
            Image(systemName: "mappin.circle.fill")
                .font(.system(size: 24))
                .foregroundColor(.umuvePrimary)

            VStack(alignment: .leading, spacing: 2) {
                Text("Service Location")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.umuveTextMuted)

                Text(bookingData.address.fullAddress.isEmpty ? "No address set" : bookingData.address.fullAddress)
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)
                    .lineLimit(1)
            }

            Spacer()

            Button(action: { dismiss() }) {
                Text("Edit")
                    .font(UmuveTypography.bodySmallFont.weight(.semibold))
                    .foregroundColor(.umuvePrimary)
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        .shadow(color: .black.opacity(0.06), radius: 4, x: 0, y: 2)
    }

    // MARK: - Service Category Cards
    private var serviceCategoryCards: some View {
        VStack(spacing: UmuveSpacing.normal) {
            ServiceDetailCard(
                title: "Junk Removal",
                description: "Furniture, appliances, and general junk",
                icon: "trash.fill",
                color: .categoryBlue,
                subItems: ["Furniture", "Appliances", "Electronics", "General Junk"]
            )

            ServiceDetailCard(
                title: "Donation Pickups",
                description: "Gently used items for charity",
                icon: "heart.fill",
                color: .categoryPink,
                subItems: ["Clothing", "Books", "Toys", "Home Goods"]
            )

            ServiceDetailCard(
                title: "Moving Labor",
                description: "Heavy lifting and loading help",
                icon: "figure.strengthtraining.traditional",
                color: .categoryYellow,
                subItems: ["Furniture Moving", "Loading/Unloading", "Packing Help", "Rearranging"]
            )

            ServiceDetailCard(
                title: "Property Cleanout",
                description: "Full property or estate cleanout",
                icon: "house.fill",
                color: .categoryGreen,
                subItems: ["Estate Cleanout", "Foreclosure", "Eviction", "Garage Cleanout"]
            )
        }
    }
}

// MARK: - Service Detail Card
struct ServiceDetailCard: View {
    let title: String
    let description: String
    let icon: String
    let color: Color
    let subItems: [String]
    @EnvironmentObject var bookingData: BookingData

    var body: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            // Header with icon
            HStack(spacing: UmuveSpacing.normal) {
                ZStack {
                    RoundedRectangle(cornerRadius: UmuveRadius.md)
                        .fill(color.opacity(0.2))
                        .frame(width: 60, height: 60)

                    Image(systemName: icon)
                        .font(.system(size: 28))
                        .foregroundColor(color)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)

                    Text(description)
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveTextMuted)
                        .lineLimit(2)
                }

                Spacer()
            }

            // Sub-items list
            VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                ForEach(subItems, id: \.self) { item in
                    HStack(spacing: UmuveSpacing.small) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 14))
                            .foregroundColor(color)

                        Text(item)
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.umuveTextMuted)
                    }
                }
            }
            .padding(.horizontal, UmuveSpacing.small)

            // Book Now button
            NavigationLink(destination: PhotoUploadView().environmentObject(bookingData)) {
                HStack {
                    Text("Book Now")
                        .font(UmuveTypography.bodyFont.weight(.semibold))
                        .foregroundColor(.white)

                    Image(systemName: "arrow.right")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(.white)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(
                    LinearGradient(
                        colors: [color, color.opacity(0.8)],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
                .shadow(color: color.opacity(0.3), radius: 6, x: 0, y: 4)
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .shadow(color: .black.opacity(0.08), radius: 8, x: 0, y: 4)
    }
}

// MARK: - Preview
struct ServiceSelectionRedesignView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            ServiceSelectionRedesignView()
                .environmentObject(BookingData())
        }
    }
}

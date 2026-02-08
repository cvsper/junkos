//
//  ServiceSelectionRedesignView.swift
//  JunkOS
//
//  Redesigned service selection (LoadUp-inspired)
//

import SwiftUI

struct ServiceSelectionRedesignView: View {
    @EnvironmentObject var bookingData: BookingData
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            VStack(spacing: JunkSpacing.large) {
                // Address display (editable)
                addressHeader

                // Service category cards
                serviceCategoryCards
            }
            .padding(JunkSpacing.large)
        }
        .background(Color.junkBackground.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(true)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button(action: { dismiss() }) {
                    Image(systemName: "chevron.left")
                        .foregroundColor(.junkText)
                }
            }
            ToolbarItem(placement: .principal) {
                Text("Select Service")
                    .font(JunkTypography.h3Font)
            }
        }
    }

    // MARK: - Address Header
    private var addressHeader: some View {
        HStack {
            Image(systemName: "mappin.circle.fill")
                .font(.system(size: 24))
                .foregroundColor(.junkPrimary)

            VStack(alignment: .leading, spacing: 2) {
                Text("Service Location")
                    .font(JunkTypography.captionFont)
                    .foregroundColor(.junkTextMuted)

                Text(bookingData.address.fullAddress.isEmpty ? "No address set" : bookingData.address.fullAddress)
                    .font(JunkTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.junkText)
                    .lineLimit(1)
            }

            Spacer()

            Button(action: { dismiss() }) {
                Text("Edit")
                    .font(JunkTypography.bodySmallFont.weight(.semibold))
                    .foregroundColor(.junkPrimary)
            }
        }
        .padding(JunkSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.md))
        .shadow(color: .black.opacity(0.06), radius: 4, x: 0, y: 2)
    }

    // MARK: - Service Category Cards
    private var serviceCategoryCards: some View {
        VStack(spacing: JunkSpacing.normal) {
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
        VStack(alignment: .leading, spacing: JunkSpacing.normal) {
            // Header with icon
            HStack(spacing: JunkSpacing.normal) {
                ZStack {
                    RoundedRectangle(cornerRadius: JunkRadius.md)
                        .fill(color.opacity(0.2))
                        .frame(width: 60, height: 60)

                    Image(systemName: icon)
                        .font(.system(size: 28))
                        .foregroundColor(color)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(JunkTypography.h3Font)
                        .foregroundColor(.junkText)

                    Text(description)
                        .font(JunkTypography.bodySmallFont)
                        .foregroundColor(.junkTextMuted)
                        .lineLimit(2)
                }

                Spacer()
            }

            // Sub-items list
            VStack(alignment: .leading, spacing: JunkSpacing.small) {
                ForEach(subItems, id: \.self) { item in
                    HStack(spacing: JunkSpacing.small) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 14))
                            .foregroundColor(color)

                        Text(item)
                            .font(JunkTypography.bodySmallFont)
                            .foregroundColor(.junkTextMuted)
                    }
                }
            }
            .padding(.horizontal, JunkSpacing.small)

            // Book Now button
            NavigationLink(destination: PhotoUploadView().environmentObject(bookingData)) {
                HStack {
                    Text("Book Now")
                        .font(JunkTypography.bodyFont.weight(.semibold))
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
                .clipShape(RoundedRectangle(cornerRadius: JunkRadius.md))
                .shadow(color: color.opacity(0.3), radius: 6, x: 0, y: 4)
            }
        }
        .padding(JunkSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
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

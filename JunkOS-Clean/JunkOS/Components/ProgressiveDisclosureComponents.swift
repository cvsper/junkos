//
//  ProgressiveDisclosureComponents.swift
//  Umuve
//
//  Live price estimates and progressive information reveal
//

import SwiftUI

// MARK: - Price Calculator
class PriceCalculator {
    static func calculateEstimate(
        services: Set<String>,
        photoCount: Int
    ) -> Double {
        let basePrice: Double = 89.00
        let servicePrice: Double = Double(services.count) * 45.00
        let photoMultiplier: Double = photoCount > 5 ? 1.15 : 1.0
        
        return (basePrice + servicePrice) * photoMultiplier
    }
    
    static func formatPrice(_ price: Double) -> String {
        return String(format: "$%.0f", price)
    }
}

// MARK: - Live Price Estimate Banner
struct LivePriceEstimate: View {
    let services: Set<String>
    let photoCount: Int
    @State private var isExpanded = false
    @State private var animationTrigger = 0
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    
    private var estimate: Double {
        PriceCalculator.calculateEstimate(services: services, photoCount: photoCount)
    }
    
    var body: some View {
        if !services.isEmpty {
            VStack(spacing: 0) {
                // Main banner
                Button(action: {
                    withAnimation(.spring(response: 0.3)) {
                        isExpanded.toggle()
                    }
                }) {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Estimated Total")
                                .font(UmuveTypography.captionFont)
                                .foregroundColor(.umuveTextMuted)
                            
                            Text(PriceCalculator.formatPrice(estimate))
                                .font(UmuveTypography.h2Font)
                                .foregroundColor(.umuveText)
                        }
                        
                        Spacer()
                        
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .foregroundColor(.umuvePrimary)
                            .font(.system(size: 16, weight: .semibold))
                    }
                    .padding(UmuveSpacing.normal)
                }
                .buttonStyle(PlainButtonStyle())
                .background(Color.umuveWhite)
                .cornerRadius(isExpanded ? 0 : 12, corners: [.allCorners])
                .cornerRadius(isExpanded ? 12 : 0, corners: [.topLeft, .topRight])
                .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
                .bounce(trigger: animationTrigger)
                .accessibilityLabel("Estimated total \(PriceCalculator.formatPrice(estimate))")
                .accessibilityHint(isExpanded ? "Double tap to collapse details" : "Double tap to expand details")
                
                // Breakdown (expandable)
                if isExpanded {
                    VStack(spacing: UmuveSpacing.small) {
                        Divider()
                            .padding(.horizontal, UmuveSpacing.normal)
                        
                        VStack(spacing: UmuveSpacing.small) {
                            PriceRow(label: "Base Rate", value: "$89")
                            PriceRow(label: "\(services.count) Service(s)", value: "$\(services.count * 45)")
                            
                            if photoCount > 5 {
                                PriceRow(label: "Volume Adjustment", value: "+15%", isHighlight: true)
                            }
                        }
                        .padding(.horizontal, UmuveSpacing.normal)
                        .padding(.vertical, UmuveSpacing.small)
                        
                        Text("*Final price may vary based on actual volume")
                            .font(UmuveTypography.smallFont)
                            .foregroundColor(.umuveTextMuted)
                            .padding(.horizontal, UmuveSpacing.normal)
                            .padding(.bottom, UmuveSpacing.normal)
                    }
                    .background(Color.umuveWhite)
                    .cornerRadius(12, corners: [.bottomLeft, .bottomRight])
                    .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 4)
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }
            }
            .onChange(of: services.count) { _ in
                animationTrigger += 1
            }
            .onChange(of: photoCount) { _ in
                animationTrigger += 1
            }
        }
    }
}

// MARK: - Price Row
struct PriceRow: View {
    let label: String
    let value: String
    let isHighlight: Bool
    
    init(label: String, value: String, isHighlight: Bool = false) {
        self.label = label
        self.value = value
        self.isHighlight = isHighlight
    }
    
    var body: some View {
        HStack {
            Text(label)
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(isHighlight ? .umuvePrimary : .umuveText)
            
            Spacer()
            
            Text(value)
                .font(UmuveTypography.bodySmallFont.weight(.semibold))
                .foregroundColor(isHighlight ? .umuvePrimary : .umuveText)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(label): \(value)")
    }
}

// MARK: - Booking Summary Preview
struct BookingSummaryPreview: View {
    let address: String
    let services: Set<String>
    let date: Date?
    let timeSlot: String?
    let photoCount: Int
    
    private var estimate: Double {
        PriceCalculator.calculateEstimate(services: services, photoCount: photoCount)
    }
    
    private var dateString: String {
        guard let date = date else { return "Not selected" }
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return formatter.string(from: date)
    }
    
    var body: some View {
        UmuveCard {
            VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
                // Header
                HStack {
                    Image(systemName: "doc.text.fill")
                        .foregroundColor(.umuvePrimary)
                        .font(.system(size: 24))
                    
                    Text("Booking Summary")
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)
                }
                .padding(.bottom, UmuveSpacing.small)
                
                Divider()
                
                // Details
                VStack(spacing: UmuveSpacing.medium) {
                    SummaryRow(icon: "mappin.circle.fill", label: "Address", value: address)
                    SummaryRow(icon: "square.grid.2x2", label: "Services", value: "\(services.count) selected")
                    SummaryRow(icon: "photo", label: "Photos", value: "\(photoCount) attached")
                    SummaryRow(icon: "calendar", label: "Date", value: dateString)
                    
                    if let timeSlot = timeSlot {
                        SummaryRow(icon: "clock", label: "Time", value: timeSlot)
                    }
                }
                
                Divider()
                
                // Total
                HStack {
                    Text("Estimated Total")
                        .font(UmuveTypography.bodyFont.weight(.semibold))
                        .foregroundColor(.umuveText)
                    
                    Spacer()
                    
                    Text(PriceCalculator.formatPrice(estimate))
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuvePrimary)
                }
            }
            .padding(UmuveSpacing.normal)
        }
        .accessibilityElement(children: .contain)
    }
}

// MARK: - Summary Row
struct SummaryRow: View {
    let icon: String
    let label: String
    let value: String
    
    var body: some View {
        HStack(spacing: UmuveSpacing.medium) {
            Image(systemName: icon)
                .foregroundColor(.umuvePrimary)
                .font(.system(size: 18))
                .frame(width: 24)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextMuted)
                
                Text(value)
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveText)
            }
            
            Spacer()
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(label): \(value)")
    }
}

// MARK: - Corner Radius Extension
extension View {
    func cornerRadius(_ radius: CGFloat, corners: UIRectCorner) -> some View {
        clipShape(RoundedCorner(radius: radius, corners: corners))
    }
}

struct RoundedCorner: Shape {
    var radius: CGFloat = .infinity
    var corners: UIRectCorner = .allCorners
    
    func path(in rect: CGRect) -> Path {
        let path = UIBezierPath(
            roundedRect: rect,
            byRoundingCorners: corners,
            cornerRadii: CGSize(width: radius, height: radius)
        )
        return Path(path.cgPath)
    }
}

// MARK: - Preview
struct ProgressiveDisclosureComponents_Previews: PreviewProvider {
    static var previews: some View {
        ScrollView {
            VStack(spacing: 30) {
                LivePriceEstimate(
                    services: ["furniture", "electronics"],
                    photoCount: 3
                )
                
                BookingSummaryPreview(
                    address: "123 Main St, Miami, FL 33101",
                    services: ["furniture", "electronics", "yard"],
                    date: Date(),
                    timeSlot: "10:00 AM - 12:00 PM",
                    photoCount: 5
                )
            }
            .padding()
        }
        .background(Color.umuveBackground)
    }
}

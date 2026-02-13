//
//  TrustComponents.swift
//  Umuve
//
//  Trust badges, reviews, and social proof components
//

import SwiftUI

// MARK: - Customer Review Model
struct CustomerReview: Identifiable {
    let id = UUID()
    let name: String
    let rating: Int
    let comment: String
    let date: String
    let location: String
}

// MARK: - Sample Reviews
extension CustomerReview {
    static let sampleReviews = [
        CustomerReview(
            name: "Sarah M.",
            rating: 5,
            comment: "Amazing service! They removed my old furniture in under 2 hours. Super professional and eco-friendly.",
            date: "2 days ago",
            location: "Miami, FL"
        ),
        CustomerReview(
            name: "James K.",
            rating: 5,
            comment: "Best junk removal experience ever. Instant quote, same-day pickup, and great pricing. Highly recommend!",
            date: "1 week ago",
            location: "Fort Lauderdale, FL"
        ),
        CustomerReview(
            name: "Linda R.",
            rating: 5,
            comment: "They hauled away years of garage clutter. The team was courteous and efficient. Will use again!",
            date: "2 weeks ago",
            location: "West Palm Beach, FL"
        ),
        CustomerReview(
            name: "Michael P.",
            rating: 5,
            comment: "Quick booking, fair prices, and they recycled everything they could. A+ service!",
            date: "3 weeks ago",
            location: "Boca Raton, FL"
        )
    ]
}

// MARK: - Review Card
struct ReviewCard: View {
    let review: CustomerReview
    @Environment(\.dynamicTypeSize) var dynamicTypeSize
    
    var body: some View {
        UmuveCard {
            VStack(alignment: .leading, spacing: UmuveSpacing.medium) {
                // Header with name and rating
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(review.name)
                            .font(UmuveTypography.bodyFont.weight(.semibold))
                            .foregroundColor(.umuveText)
                        
                        Text("\(review.location) • \(review.date)")
                            .font(UmuveTypography.smallFont)
                            .foregroundColor(.umuveTextMuted)
                    }
                    
                    Spacer()
                    
                    // Star rating
                    HStack(spacing: 2) {
                        ForEach(0..<5) { index in
                            Image(systemName: index < review.rating ? "star.fill" : "star")
                                .font(.system(size: 14))
                                .foregroundColor(index < review.rating ? .yellow : .umuveBorder)
                        }
                    }
                }
                
                // Comment
                Text(review.comment)
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveText)
                    .lineLimit(3)
                
                // Verified badge
                HStack(spacing: 4) {
                    Image(systemName: "checkmark.seal.fill")
                        .font(.system(size: 12))
                        .foregroundColor(.umuveCTA)
                    Text("Verified Customer")
                        .font(UmuveTypography.smallFont)
                        .foregroundColor(.umuveTextMuted)
                }
            }
            .padding(UmuveSpacing.normal)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(review.rating) star review from \(review.name). \(review.comment)")
    }
}

// MARK: - Reviews Section
struct ReviewsSection: View {
    let reviews: [CustomerReview]
    
    init(reviews: [CustomerReview] = CustomerReview.sampleReviews.prefix(3).map { $0 }) {
        self.reviews = reviews
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            // Section header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("What Our Customers Say")
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)
                    
                    HStack(spacing: 4) {
                        HStack(spacing: 2) {
                            ForEach(0..<5) { _ in
                                Image(systemName: "star.fill")
                                    .font(.system(size: 12))
                                    .foregroundColor(.yellow)
                            }
                        }
                        Text("4.9/5")
                            .font(UmuveTypography.captionFont)
                            .foregroundColor(.umuveTextMuted)
                        Text("(2,547 reviews)")
                            .font(UmuveTypography.smallFont)
                            .foregroundColor(.umuveTextMuted)
                    }
                }
                
                Spacer()
            }
            .padding(.bottom, UmuveSpacing.small)
            
            // Reviews
            ForEach(reviews) { review in
                ReviewCard(review: review)
            }
        }
        .accessibilityElement(children: .contain)
    }
}

// MARK: - Trust Badge
struct TrustBadge: View {
    let icon: String
    let text: String
    let color: Color
    
    var body: some View {
        HStack(spacing: UmuveSpacing.small) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(color)
            
            Text(text)
                .font(UmuveTypography.captionFont)
                .foregroundColor(.umuveText)
        }
        .padding(.horizontal, UmuveSpacing.medium)
        .padding(.vertical, UmuveSpacing.small)
        .background(color.opacity(0.1))
        .cornerRadius(20)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(text)
    }
}

// MARK: - Trust Badges Bar
struct TrustBadgesBar: View {
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: UmuveSpacing.medium) {
                TrustBadge(icon: "shield.checkered", text: "Licensed & Insured", color: .umuveCTA)
                TrustBadge(icon: "star.fill", text: "5-Star Rated", color: .yellow)
                TrustBadge(icon: "leaf.fill", text: "Eco-Friendly", color: .green)
                TrustBadge(icon: "clock.fill", text: "Same-Day Available", color: .umuvePrimary)
            }
            .padding(.horizontal, UmuveSpacing.large)
        }
        .accessibilityElement(children: .contain)
    }
}

// MARK: - Live Bookings Counter
struct LiveBookingsCounter: View {
    @State private var count = 127
    @State private var isAnimating = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    
    var body: some View {
        HStack(spacing: UmuveSpacing.small) {
            // Pulse indicator
            Circle()
                .fill(Color.umuveCTA)
                .frame(width: 8, height: 8)
                .overlay(
                    Circle()
                        .fill(Color.umuveCTA.opacity(0.3))
                        .scaleEffect(isAnimating ? 2 : 1)
                        .opacity(isAnimating ? 0 : 1)
                )
            
            Text("\(count) bookings today")
                .font(UmuveTypography.captionFont)
                .foregroundColor(.umuveTextMuted)
        }
        .padding(.horizontal, UmuveSpacing.normal)
        .padding(.vertical, UmuveSpacing.small)
        .background(Color.umuveWhite)
        .cornerRadius(20)
        .shadow(color: .black.opacity(0.06), radius: 4, x: 0, y: 2)
        .onAppear {
            if !reduceMotion {
                startPulseAnimation()
                startCounterAnimation()
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(count) bookings made today")
        .accessibilityAddTraits(.updatesFrequently)
    }
    
    private func startPulseAnimation() {
        withAnimation(
            Animation.easeInOut(duration: 2)
                .repeatForever(autoreverses: false)
        ) {
            isAnimating = true
        }
    }
    
    private func startCounterAnimation() {
        Timer.scheduledTimer(withTimeInterval: Double.random(in: 5...10), repeats: true) { _ in
            withAnimation(.easeInOut) {
                count += 1
            }
        }
    }
}

// MARK: - Preview
struct TrustComponents_Previews: PreviewProvider {
    static var previews: some View {
        ScrollView {
            VStack(spacing: 30) {
                ReviewCard(review: CustomerReview.sampleReviews[0])
                ReviewsSection()
                TrustBadgesBar()
                LiveBookingsCounter()
            }
            .padding()
        }
        .background(Color.umuveBackground)
    }
}

//
//  TrustComponents.swift
//  JunkOS
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
        JunkCard {
            VStack(alignment: .leading, spacing: JunkSpacing.medium) {
                // Header with name and rating
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(review.name)
                            .font(JunkTypography.bodyFont.weight(.semibold))
                            .foregroundColor(.junkText)
                        
                        Text("\(review.location) • \(review.date)")
                            .font(JunkTypography.smallFont)
                            .foregroundColor(.junkTextMuted)
                    }
                    
                    Spacer()
                    
                    // Star rating
                    HStack(spacing: 2) {
                        ForEach(0..<5) { index in
                            Image(systemName: index < review.rating ? "star.fill" : "star")
                                .font(.system(size: 14))
                                .foregroundColor(index < review.rating ? .yellow : .junkBorder)
                        }
                    }
                }
                
                // Comment
                Text(review.comment)
                    .font(JunkTypography.bodySmallFont)
                    .foregroundColor(.junkText)
                    .lineLimit(3)
                
                // Verified badge
                HStack(spacing: 4) {
                    Image(systemName: "checkmark.seal.fill")
                        .font(.system(size: 12))
                        .foregroundColor(.junkCTA)
                    Text("Verified Customer")
                        .font(JunkTypography.smallFont)
                        .foregroundColor(.junkTextMuted)
                }
            }
            .padding(JunkSpacing.normal)
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
        VStack(alignment: .leading, spacing: JunkSpacing.normal) {
            // Section header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("What Our Customers Say")
                        .font(JunkTypography.h3Font)
                        .foregroundColor(.junkText)
                    
                    HStack(spacing: 4) {
                        HStack(spacing: 2) {
                            ForEach(0..<5) { _ in
                                Image(systemName: "star.fill")
                                    .font(.system(size: 12))
                                    .foregroundColor(.yellow)
                            }
                        }
                        Text("4.9/5")
                            .font(JunkTypography.captionFont)
                            .foregroundColor(.junkTextMuted)
                        Text("(2,547 reviews)")
                            .font(JunkTypography.smallFont)
                            .foregroundColor(.junkTextMuted)
                    }
                }
                
                Spacer()
            }
            .padding(.bottom, JunkSpacing.small)
            
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
        HStack(spacing: JunkSpacing.small) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(color)
            
            Text(text)
                .font(JunkTypography.captionFont)
                .foregroundColor(.junkText)
        }
        .padding(.horizontal, JunkSpacing.medium)
        .padding(.vertical, JunkSpacing.small)
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
            HStack(spacing: JunkSpacing.medium) {
                TrustBadge(icon: "shield.checkered", text: "Licensed & Insured", color: .junkCTA)
                TrustBadge(icon: "star.fill", text: "5-Star Rated", color: .yellow)
                TrustBadge(icon: "leaf.fill", text: "Eco-Friendly", color: .green)
                TrustBadge(icon: "clock.fill", text: "Same-Day Available", color: .junkPrimary)
            }
            .padding(.horizontal, JunkSpacing.large)
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
        HStack(spacing: JunkSpacing.small) {
            // Pulse indicator
            Circle()
                .fill(Color.junkCTA)
                .frame(width: 8, height: 8)
                .overlay(
                    Circle()
                        .fill(Color.junkCTA.opacity(0.3))
                        .scaleEffect(isAnimating ? 2 : 1)
                        .opacity(isAnimating ? 0 : 1)
                )
            
            Text("\(count) bookings today")
                .font(JunkTypography.captionFont)
                .foregroundColor(.junkTextMuted)
        }
        .padding(.horizontal, JunkSpacing.normal)
        .padding(.vertical, JunkSpacing.small)
        .background(Color.junkWhite)
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
        .background(Color.junkBackground)
    }
}

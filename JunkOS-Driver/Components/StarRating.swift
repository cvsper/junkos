//
//  StarRating.swift
//  JunkOS Driver
//
//  5-star display component.
//

import SwiftUI

struct StarRating: View {
    let rating: Double
    let maxRating: Int = 5

    var body: some View {
        HStack(spacing: 2) {
            ForEach(1...maxRating, id: \.self) { star in
                Image(systemName: starImage(for: star))
                    .font(.system(size: 14))
                    .foregroundStyle(star <= Int(rating.rounded()) ? Color.statusPending : Color.driverBorder)
            }
        }
    }

    private func starImage(for star: Int) -> String {
        let diff = rating - Double(star - 1)
        if diff >= 1 { return "star.fill" }
        if diff >= 0.5 { return "star.leadinghalf.filled" }
        return "star"
    }
}

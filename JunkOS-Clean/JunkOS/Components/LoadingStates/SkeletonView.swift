//
//  SkeletonView.swift
//  Umuve
//
//  Skeleton loading components with shimmer effect
//

import SwiftUI

// MARK: - Shimmer Effect Modifier
struct ShimmerEffect: ViewModifier {
    @State private var phase: CGFloat = 0
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    
    func body(content: Content) -> some View {
        content
            .overlay(
                GeometryReader { geometry in
                    if !reduceMotion {
                        LinearGradient(
                            gradient: Gradient(colors: [
                                .clear,
                                Color.white.opacity(0.3),
                                .clear
                            ]),
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                        .frame(width: geometry.size.width * 2)
                        .offset(x: -geometry.size.width + (geometry.size.width * 2 * phase))
                    }
                }
            )
            .onAppear {
                if !reduceMotion {
                    withAnimation(
                        Animation.linear(duration: 1.5)
                            .repeatForever(autoreverses: false)
                    ) {
                        phase = 1
                    }
                }
            }
    }
}

extension View {
    func shimmer() -> some View {
        modifier(ShimmerEffect())
    }
}

// MARK: - Skeleton Card
struct SkeletonCard: View {
    let height: CGFloat
    let cornerRadius: CGFloat
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    
    init(height: CGFloat = 120, cornerRadius: CGFloat = 16) {
        self.height = height
        self.cornerRadius = cornerRadius
    }
    
    var body: some View {
        RoundedRectangle(cornerRadius: cornerRadius)
            .fill(Color.umuveBorder.opacity(0.3))
            .frame(height: height)
            .shimmer()
            .accessibilityLabel("Loading content")
            .accessibilityAddTraits(.updatesFrequently)
    }
}

// MARK: - Skeleton Text
struct SkeletonText: View {
    let width: CGFloat?
    let height: CGFloat
    
    init(width: CGFloat? = nil, height: CGFloat = 16) {
        self.width = width
        self.height = height
    }
    
    var body: some View {
        RoundedRectangle(cornerRadius: 4)
            .fill(Color.umuveBorder.opacity(0.3))
            .frame(width: width, height: height)
            .shimmer()
            .accessibilityHidden(true)
    }
}

// MARK: - Skeleton Service Card
struct SkeletonServiceCard: View {
    var body: some View {
        VStack(spacing: UmuveSpacing.medium) {
            // Icon placeholder
            Circle()
                .fill(Color.umuveBorder.opacity(0.3))
                .frame(width: 50, height: 50)
            
            // Title placeholder
            SkeletonText(width: 80, height: 14)
            
            // Price placeholder
            SkeletonText(width: 60, height: 12)
        }
        .frame(maxWidth: .infinity)
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .cornerRadius(16)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.umuveBorder, lineWidth: 2)
        )
        .shimmer()
        .accessibilityLabel("Loading service option")
    }
}

// MARK: - Branded Loading Spinner
struct JunkLoadingSpinner: View {
    @State private var isRotating = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    
    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.umuveBorder, lineWidth: 4)
                .frame(width: 50, height: 50)
            
            Circle()
                .trim(from: 0, to: 0.7)
                .stroke(
                    LinearGradient(
                        colors: [Color.umuvePrimary, Color.umuveSecondary],
                        startPoint: .leading,
                        endPoint: .trailing
                    ),
                    style: StrokeStyle(lineWidth: 4, lineCap: .round)
                )
                .frame(width: 50, height: 50)
                .rotationEffect(Angle(degrees: isRotating ? 360 : 0))
                .animation(
                    reduceMotion ? .none :
                    Animation.linear(duration: 1).repeatForever(autoreverses: false),
                    value: isRotating
                )
        }
        .onAppear {
            if !reduceMotion {
                isRotating = true
            }
        }
        .accessibilityLabel("Loading")
        .accessibilityAddTraits(.updatesFrequently)
    }
}

// MARK: - Full Screen Loading View
struct LoadingView: View {
    let message: String
    
    init(message: String = "Loading...") {
        self.message = message
    }
    
    var body: some View {
        VStack(spacing: UmuveSpacing.large) {
            JunkLoadingSpinner()
            
            Text(message)
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveTextMuted)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.umuveBackground)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(message)")
    }
}

// MARK: - Preview
struct SkeletonView_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 20) {
            SkeletonCard()
            SkeletonText()
            SkeletonText(width: 150)
            SkeletonServiceCard()
            JunkLoadingSpinner()
            LoadingView()
        }
        .padding()
    }
}

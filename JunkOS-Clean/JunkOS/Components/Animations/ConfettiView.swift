//
//  ConfettiView.swift
//  Umuve
//
//  Confetti animation for celebrations
//

import SwiftUI

// MARK: - Confetti Piece
struct ConfettiPiece: Identifiable {
    let id = UUID()
    var x: CGFloat
    var y: CGFloat
    var rotation: Double
    var scale: CGFloat
    var color: Color
    var velocity: CGFloat
    var angularVelocity: Double
}

// MARK: - Confetti View
struct ConfettiView: View {
    @State private var pieces: [ConfettiPiece] = []
    @State private var isAnimating = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    
    let colors: [Color] = [
        .umuvePrimary,
        .umuveSecondary,
        .umuveCTA,
        .pink,
        .orange,
        .yellow
    ]
    
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                ForEach(pieces) { piece in
                    Rectangle()
                        .fill(piece.color)
                        .frame(width: 10, height: 10)
                        .rotationEffect(.degrees(piece.rotation))
                        .scaleEffect(piece.scale)
                        .position(x: piece.x, y: piece.y)
                }
            }
            .onAppear {
                if !reduceMotion {
                    generateConfetti(in: geometry.size)
                    animateConfetti()
                }
            }
        }
        .ignoresSafeArea()
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
    
    private func generateConfetti(in size: CGSize) {
        pieces = (0..<50).map { _ in
            ConfettiPiece(
                x: CGFloat.random(in: 0...size.width),
                y: -20,
                rotation: Double.random(in: 0...360),
                scale: CGFloat.random(in: 0.5...1.5),
                color: colors.randomElement() ?? .umuvePrimary,
                velocity: CGFloat.random(in: 2...5),
                angularVelocity: Double.random(in: -10...10)
            )
        }
    }
    
    private func animateConfetti() {
        Timer.scheduledTimer(withTimeInterval: 0.03, repeats: true) { timer in
            guard !pieces.isEmpty else {
                timer.invalidate()
                return
            }
            
            pieces = pieces.compactMap { piece in
                var newPiece = piece
                newPiece.y += piece.velocity
                newPiece.rotation += piece.angularVelocity
                
                // Remove pieces that have fallen off screen
                if newPiece.y > UIScreen.main.bounds.height + 50 {
                    return nil
                }
                
                return newPiece
            }
        }
    }
}

// MARK: - Success Checkmark Animation
struct SuccessCheckmark: View {
    @State private var trimEnd: CGFloat = 0
    @State private var scale: CGFloat = 0
    @State private var opacity: Double = 0
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    
    var body: some View {
        ZStack {
            Circle()
                .fill(Color.umuveCTA)
                .frame(width: 100, height: 100)
                .scaleEffect(scale)
                .opacity(opacity)
            
            Image(systemName: "checkmark")
                .font(.system(size: 50, weight: .bold))
                .foregroundColor(.white)
                .scaleEffect(scale)
                .opacity(opacity)
        }
        .onAppear {
            if reduceMotion {
                // Instant appearance for reduced motion
                scale = 1
                opacity = 1
            } else {
                // Animated appearance
                withAnimation(.spring(response: 0.5, dampingFraction: 0.6)) {
                    scale = 1
                    opacity = 1
                }
            }
        }
        .accessibilityLabel("Success")
        .accessibilityAddTraits(.isStaticText)
    }
}

// MARK: - Pulse Animation
struct PulseAnimation: ViewModifier {
    @State private var isAnimating = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    
    func body(content: Content) -> some View {
        content
            .scaleEffect(isAnimating ? 1.05 : 1.0)
            .onAppear {
                if !reduceMotion {
                    withAnimation(
                        Animation.easeInOut(duration: 1.0)
                            .repeatForever(autoreverses: true)
                    ) {
                        isAnimating = true
                    }
                }
            }
    }
}

extension View {
    func pulse() -> some View {
        modifier(PulseAnimation())
    }
}

// MARK: - Bounce Animation
struct BounceAnimation: ViewModifier {
    @State private var isAnimating = false
    let trigger: Int
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    
    func body(content: Content) -> some View {
        content
            .scaleEffect(isAnimating ? 1.1 : 1.0)
            .onChange(of: trigger) { _ in
                if !reduceMotion {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.5)) {
                        isAnimating = true
                    }
                    
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.5)) {
                            isAnimating = false
                        }
                    }
                }
            }
    }
}

// MARK: - Preview
struct ConfettiView_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.umuveBackground.ignoresSafeArea()
            
            VStack(spacing: 40) {
                SuccessCheckmark()
                
                Text("Pulse Animation")
                    .padding()
                    .background(Color.umuvePrimary)
                    .foregroundColor(.white)
                    .cornerRadius(8)
                    .pulse()
                
                Text("Tap me for bounce")
                    .padding()
                    .background(Color.umuveCTA)
                    .foregroundColor(.white)
                    .cornerRadius(8)
            }
            
            ConfettiView()
        }
    }
}

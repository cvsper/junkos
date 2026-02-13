//
//  ErrorView.swift
//  Umuve
//
//  Error handling components with animations and retry actions
//

import SwiftUI

// MARK: - Shake Animation Modifier
struct ShakeEffect: GeometryEffect {
    var amount: CGFloat = 10
    var shakesPerUnit = 3
    var animatableData: CGFloat
    
    func effectValue(size: CGSize) -> ProjectionTransform {
        ProjectionTransform(
            CGAffineTransform(
                translationX: amount * sin(animatableData * .pi * CGFloat(shakesPerUnit)),
                y: 0
            )
        )
    }
}

extension View {
    func shake(trigger: Int) -> some View {
        modifier(ShakeAnimation(trigger: trigger))
    }
}

struct ShakeAnimation: ViewModifier {
    let trigger: Int
    @State private var attempts: Int = 0
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    
    func body(content: Content) -> some View {
        content
            .modifier(ShakeEffect(animatableData: CGFloat(attempts)))
            .onChange(of: trigger) { _ in
                if !reduceMotion {
                    withAnimation(.default) {
                        attempts += 1
                    }
                }
            }
    }
}

// MARK: - Error Type
enum JunkError {
    case network
    case validation(String)
    case unknown
    case serverError
    case timeout
    
    var icon: String {
        switch self {
        case .network, .timeout:
            return "wifi.slash"
        case .validation:
            return "exclamationmark.triangle"
        case .serverError:
            return "server.rack"
        case .unknown:
            return "questionmark.circle"
        }
    }
    
    var title: String {
        switch self {
        case .network:
            return "Connection Error"
        case .validation(let message):
            return message
        case .serverError:
            return "Server Error"
        case .timeout:
            return "Request Timeout"
        case .unknown:
            return "Something Went Wrong"
        }
    }
    
    var message: String {
        switch self {
        case .network:
            return "Please check your internet connection and try again"
        case .validation:
            return "Please fix the errors above and try again"
        case .serverError:
            return "Our servers are having trouble. Please try again in a moment"
        case .timeout:
            return "The request took too long. Please try again"
        case .unknown:
            return "An unexpected error occurred. Please try again"
        }
    }
}

// MARK: - Error View Component
struct ErrorView: View {
    let error: JunkError
    let retryAction: (() -> Void)?
    
    @Environment(\.dynamicTypeSize) var dynamicTypeSize
    @Environment(\.colorSchemeContrast) var contrast
    
    init(error: JunkError, retryAction: (() -> Void)? = nil) {
        self.error = error
        self.retryAction = retryAction
    }
    
    var body: some View {
        UmuveCard {
            VStack(spacing: UmuveSpacing.large) {
                // Error icon
                ZStack {
                    Circle()
                        .fill(Color.red.opacity(0.1))
                        .frame(width: 80, height: 80)
                    
                    Image(systemName: error.icon)
                        .font(.system(size: 40))
                        .foregroundColor(.red)
                }
                
                VStack(spacing: UmuveSpacing.small) {
                    Text(error.title)
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)
                        .multilineTextAlignment(.center)
                    
                    Text(error.message)
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveTextMuted)
                        .multilineTextAlignment(.center)
                }
                
                if let retryAction = retryAction {
                    Button(action: retryAction) {
                        HStack {
                            Image(systemName: "arrow.clockwise")
                            Text("Try Again")
                        }
                    }
                    .buttonStyle(UmuvePrimaryButtonStyle())
                    .accessibilityLabel("Try again")
                    .accessibilityHint("Double tap to retry")
                }
            }
            .padding(UmuveSpacing.xlarge)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Error: \(error.title). \(error.message)")
    }
}

// MARK: - Inline Error Badge
struct InlineError: View {
    let message: String
    let isValid: Bool
    
    var body: some View {
        HStack(spacing: UmuveSpacing.small) {
            Image(systemName: isValid ? "checkmark.circle.fill" : "xmark.circle.fill")
                .foregroundColor(isValid ? .umuveCTA : .red)
            
            Text(message)
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(isValid ? .umuveCTA : .red)
        }
        .padding(.horizontal, UmuveSpacing.medium)
        .padding(.vertical, UmuveSpacing.small)
        .background(isValid ? Color.umuveCTA.opacity(0.1) : Color.red.opacity(0.1))
        .cornerRadius(8)
        .accessibilityLabel(isValid ? "Valid: \(message)" : "Error: \(message)")
    }
}

// MARK: - Validation Feedback Icon
struct ValidationIcon: View {
    let isValid: Bool
    let show: Bool
    
    var body: some View {
        if show {
            Image(systemName: isValid ? "checkmark.circle.fill" : "xmark.circle.fill")
                .foregroundColor(isValid ? .umuveCTA : .red)
                .font(.system(size: 20))
                .transition(.scale.combined(with: .opacity))
                .accessibilityLabel(isValid ? "Valid input" : "Invalid input")
        }
    }
}

// MARK: - Network Error Banner
struct NetworkErrorBanner: View {
    let retryAction: () -> Void
    
    var body: some View {
        HStack(spacing: UmuveSpacing.medium) {
            Image(systemName: "wifi.slash")
                .foregroundColor(.white)
            
            VStack(alignment: .leading, spacing: 4) {
                Text("No Internet Connection")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.white)
                
                Text("Check your connection")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.white.opacity(0.8))
            }
            
            Spacer()
            
            Button(action: retryAction) {
                Text("Retry")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(Color.white.opacity(0.2))
                    .cornerRadius(8)
            }
            .accessibilityLabel("Retry connection")
        }
        .padding(UmuveSpacing.normal)
        .background(Color.red)
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.2), radius: 4, x: 0, y: 2)
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Preview
struct ErrorView_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 20) {
            ErrorView(error: .network, retryAction: {})
            ErrorView(error: .validation("Invalid email address"))
            InlineError(message: "Email is valid", isValid: true)
            InlineError(message: "Email is invalid", isValid: false)
            NetworkErrorBanner(retryAction: {})
            
            // Shake demo
            Text("Shake me!")
                .padding()
                .background(Color.umuvePrimary)
                .foregroundColor(.white)
                .cornerRadius(8)
                .shake(trigger: 1)
        }
        .padding()
        .background(Color.umuveBackground)
    }
}

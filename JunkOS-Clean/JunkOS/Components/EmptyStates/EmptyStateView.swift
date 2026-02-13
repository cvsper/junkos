//
//  EmptyStateView.swift
//  Umuve
//
//  Reusable empty state components with SF Symbols
//

import SwiftUI

// MARK: - Generic Empty State
struct EmptyStateView: View {
    let icon: String
    let title: String
    let subtitle: String
    let actionTitle: String?
    let action: (() -> Void)?
    
    @Environment(\.dynamicTypeSize) var dynamicTypeSize
    @Environment(\.colorSchemeContrast) var contrast
    
    init(
        icon: String,
        title: String,
        subtitle: String,
        actionTitle: String? = nil,
        action: (() -> Void)? = nil
    ) {
        self.icon = icon
        self.title = title
        self.subtitle = subtitle
        self.actionTitle = actionTitle
        self.action = action
    }
    
    var body: some View {
        UmuveCard {
            VStack(spacing: UmuveSpacing.large) {
                // Icon with gradient background
                ZStack {
                    Circle()
                        .fill(
                            LinearGradient(
                                colors: [
                                    Color.umuvePrimary.opacity(0.1),
                                    Color.umuveSecondary.opacity(0.1)
                                ],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 120, height: 120)
                    
                    Image(systemName: icon)
                        .font(.system(size: 60))
                        .foregroundColor(.umuvePrimary)
                }
                .padding(.top, UmuveSpacing.normal)
                
                VStack(spacing: UmuveSpacing.small) {
                    Text(title)
                        .font(UmuveTypography.h2Font)
                        .foregroundColor(.umuveText)
                        .multilineTextAlignment(.center)
                    
                    Text(subtitle)
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)
                        .multilineTextAlignment(.center)
                }
                
                if let actionTitle = actionTitle, let action = action {
                    Button(action: action) {
                        HStack {
                            Text(actionTitle)
                            Image(systemName: "arrow.right")
                        }
                    }
                    .buttonStyle(UmuvePrimaryButtonStyle())
                    .padding(.horizontal, UmuveSpacing.large)
                    .accessibilityLabel(actionTitle)
                    .accessibilityHint("Double tap to \(actionTitle.lowercased())")
                }
            }
            .frame(maxWidth: .infinity)
            .padding(UmuveSpacing.xlarge)
        }
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Photo Upload Empty State
struct PhotoUploadEmptyState: View {
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            EmptyStateView(
                icon: "photo.on.rectangle.angled",
                title: "No Photos Yet",
                subtitle: "Tap to add photos of items you want removed. More photos = more accurate quotes!"
            )
        }
        .buttonStyle(PlainButtonStyle())
        .accessibilityLabel("Add photos")
        .accessibilityHint("Double tap to add photos from your gallery or camera")
    }
}

// MARK: - Service Selection Empty State
struct ServiceSelectionEmptyState: View {
    var body: some View {
        EmptyStateView(
            icon: "square.grid.2x2",
            title: "Select Services",
            subtitle: "Choose the services you need from the options below"
        )
        .accessibilityLabel("No services selected yet. Choose services below.")
    }
}

// MARK: - Date Time Empty State
struct DateTimeEmptyState: View {
    var body: some View {
        EmptyStateView(
            icon: "calendar.badge.clock",
            title: "Pick Your Time",
            subtitle: "Select a date and time slot that works best for you"
        )
        .accessibilityLabel("No date and time selected. Choose your preferred schedule below.")
    }
}

// MARK: - Preview
struct EmptyStateView_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 20) {
            EmptyStateView(
                icon: "photo",
                title: "No Photos",
                subtitle: "Add photos to get started",
                actionTitle: "Add Photos",
                action: {}
            )
            
            PhotoUploadEmptyState(onTap: {})
            ServiceSelectionEmptyState()
            DateTimeEmptyState()
        }
        .padding()
        .background(Color.umuveBackground)
    }
}

//
//  RatingView.swift
//  Umuve Pro
//
//  Driver rating view shown after completing a job.
//  5-star picker for rating the customer, optional comment, submit.
//

import SwiftUI

struct RatingView: View {
    @State private var viewModel: RatingViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var isVisible = false

    init(jobId: String) {
        _viewModel = State(wrappedValue: RatingViewModel(jobId: jobId))
    }

    var body: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            if viewModel.isSubmitted {
                successView
            } else {
                reviewFormView
            }
        }
        .onAppear {
            withAnimation(AnimationConstants.bouncySpring.delay(0.1)) {
                isVisible = true
            }
        }
    }

    // MARK: - Review Form

    private var reviewFormView: some View {
        ScrollView {
            VStack(spacing: DriverSpacing.xxl) {
                // Close / skip
                HStack {
                    Spacer()
                    Button(action: { dismiss() }) {
                        Text("Skip")
                            .font(DriverTypography.callout)
                            .foregroundColor(.driverTextSecondary)
                            .padding()
                    }
                }

                // Header
                VStack(spacing: DriverSpacing.sm) {
                    Image(systemName: "star.circle.fill")
                        .font(.system(size: 72))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Color.driverPrimary, Color.driverPrimaryLight],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .opacity(isVisible ? 1 : 0)
                        .scaleEffect(isVisible ? 1 : 0.5)

                    Text("Rate the Customer")
                        .font(DriverTypography.title)
                        .foregroundColor(.driverText)
                        .multilineTextAlignment(.center)

                    Text("Help us maintain quality on both sides")
                        .font(DriverTypography.body)
                        .foregroundColor(.driverTextSecondary)
                }
                .padding(.top, DriverSpacing.md)
                .opacity(isVisible ? 1 : 0)
                .offset(y: isVisible ? 0 : 20)

                // Star picker
                starPicker
                    .opacity(isVisible ? 1 : 0)
                    .offset(y: isVisible ? 0 : 20)

                // Rating label
                if viewModel.stars > 0 {
                    Text(ratingLabel)
                        .font(DriverTypography.headline)
                        .foregroundColor(.driverPrimary)
                        .transition(.scale.combined(with: .opacity))
                }

                // Comment field
                VStack(alignment: .leading, spacing: DriverSpacing.xs) {
                    Text("Add a note (optional)")
                        .font(DriverTypography.footnote)
                        .foregroundColor(.driverTextSecondary)

                    TextEditor(text: $viewModel.comment)
                        .font(DriverTypography.body)
                        .foregroundColor(.driverText)
                        .frame(minHeight: 100)
                        .padding(DriverSpacing.md)
                        .background(Color.white)
                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                        .overlay(
                            RoundedRectangle(cornerRadius: DriverRadius.md)
                                .stroke(Color.driverBorder, lineWidth: 1)
                        )
                        .scrollContentBackground(.hidden)
                }
                .padding(.horizontal, DriverSpacing.xl)
                .opacity(isVisible ? 1 : 0)
                .offset(y: isVisible ? 0 : 20)

                // Error message
                if let error = viewModel.errorMessage {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.driverError)
                        Text(error)
                            .font(DriverTypography.footnote)
                            .foregroundColor(.driverError)
                    }
                    .padding(DriverSpacing.sm)
                    .background(Color.driverError.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.sm))
                    .padding(.horizontal, DriverSpacing.xl)
                    .transition(.scale.combined(with: .opacity))
                }

                Spacer(minLength: DriverSpacing.lg)

                // Submit button
                Button(action: {
                    Task {
                        await viewModel.submitRating()
                    }
                }) {
                    if viewModel.isSubmitting {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    } else {
                        Text("Submit Rating")
                    }
                }
                .buttonStyle(DriverPrimaryButtonStyle(isEnabled: viewModel.canSubmit))
                .disabled(!viewModel.canSubmit)
                .padding(.horizontal, DriverSpacing.xl)
                .padding(.bottom, DriverSpacing.xxl)
            }
        }
    }

    // MARK: - Star Picker

    private var starPicker: some View {
        HStack(spacing: DriverSpacing.sm) {
            ForEach(1...5, id: \.self) { star in
                Button(action: {
                    withAnimation(AnimationConstants.snappySpring) {
                        viewModel.stars = star
                    }
                    HapticManager.shared.selection()
                }) {
                    Image(systemName: star <= viewModel.stars ? "star.fill" : "star")
                        .font(.system(size: 44))
                        .foregroundColor(star <= viewModel.stars ? .driverPrimary : .driverBorder)
                        .scaleEffect(star <= viewModel.stars ? 1.1 : 1.0)
                        .animation(AnimationConstants.bouncySpring, value: viewModel.stars)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.vertical, DriverSpacing.md)
    }

    // MARK: - Success View

    private var successView: some View {
        VStack(spacing: DriverSpacing.xxl) {
            Spacer()

            ZStack {
                Circle()
                    .fill(Color.driverSuccess.opacity(0.15))
                    .frame(width: 120, height: 120)

                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 56))
                    .foregroundStyle(Color.driverSuccess)
            }

            VStack(spacing: DriverSpacing.xs) {
                Text("Thanks!")
                    .font(DriverTypography.title)
                    .foregroundStyle(Color.driverText)

                Text("Your rating has been submitted")
                    .font(DriverTypography.body)
                    .foregroundStyle(Color.driverTextSecondary)

                HStack(spacing: 4) {
                    ForEach(1...5, id: \.self) { star in
                        Image(systemName: star <= viewModel.stars ? "star.fill" : "star")
                            .font(.system(size: 20))
                            .foregroundColor(star <= viewModel.stars ? .driverPrimary : .driverBorder)
                    }
                }
                .padding(.top, DriverSpacing.xs)
            }

            Spacer()

            Button(action: { dismiss() }) {
                Text("Done")
            }
            .buttonStyle(DriverPrimaryButtonStyle())
            .padding(.horizontal, DriverSpacing.xl)
            .padding(.bottom, DriverSpacing.xxl)
        }
        .transition(.opacity)
    }

    // MARK: - Helpers

    private var ratingLabel: String {
        switch viewModel.stars {
        case 1: return "Poor"
        case 2: return "Fair"
        case 3: return "Good"
        case 4: return "Great"
        case 5: return "Excellent!"
        default: return ""
        }
    }
}

#Preview {
    RatingView(jobId: "test-job-456")
}

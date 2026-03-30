//
//  RatingReviewView.swift
//  Umuve
//
//  Customer rating/review view shown after a job is completed.
//  Displays a 5-star picker, optional comment field, and submit button.
//

import SwiftUI

struct RatingReviewView: View {
    @StateObject private var viewModel: RatingReviewViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var isVisible = false

    init(jobId: String) {
        _viewModel = StateObject(wrappedValue: RatingReviewViewModel(jobId: jobId))
    }

    var body: some View {
        ZStack {
            Color.umuveBackground.ignoresSafeArea()

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
            VStack(spacing: UmuveSpacing.xxlarge) {
                // Close button
                HStack {
                    Spacer()
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark")
                            .font(.title3)
                            .foregroundColor(.umuveText)
                            .padding()
                    }
                }

                // Header
                VStack(spacing: UmuveSpacing.medium) {
                    Image(systemName: "star.circle.fill")
                        .font(.system(size: 72))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Color.umuvePrimary, Color.umuvePrimaryLight],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .opacity(isVisible ? 1 : 0)
                        .scaleEffect(isVisible ? 1 : 0.5)

                    Text("How was your experience?")
                        .font(UmuveTypography.h1Font)
                        .foregroundColor(.umuveText)
                        .multilineTextAlignment(.center)

                    Text("Your feedback helps us improve")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)
                }
                .padding(.top, UmuveSpacing.normal)
                .opacity(isVisible ? 1 : 0)
                .offset(y: isVisible ? 0 : 20)

                // Star Rating
                starPicker
                    .opacity(isVisible ? 1 : 0)
                    .offset(y: isVisible ? 0 : 20)

                // Rating label
                if viewModel.rating > 0 {
                    Text(ratingLabel)
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuvePrimary)
                        .transition(.scale.combined(with: .opacity))
                }

                // Comment field
                VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                    Text("Add a comment (optional)")
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveTextMuted)

                    TextEditor(text: $viewModel.comment)
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveText)
                        .frame(minHeight: 100)
                        .padding(UmuveSpacing.medium)
                        .background(Color.white)
                        .cornerRadius(UmuveRadius.md)
                        .overlay(
                            RoundedRectangle(cornerRadius: UmuveRadius.md)
                                .stroke(Color.umuveBorder, lineWidth: 1)
                        )
                        .scrollContentBackground(.hidden)
                }
                .padding(.horizontal, UmuveSpacing.xlarge)
                .opacity(isVisible ? 1 : 0)
                .offset(y: isVisible ? 0 : 20)

                // Error message
                if let error = viewModel.errorMessage {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.umuveError)
                        Text(error)
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.umuveError)
                    }
                    .padding(UmuveSpacing.medium)
                    .background(Color.umuveError.opacity(0.1))
                    .cornerRadius(UmuveRadius.sm)
                    .padding(.horizontal, UmuveSpacing.xlarge)
                    .transition(.scale.combined(with: .opacity))
                }

                Spacer(minLength: UmuveSpacing.large)

                // Submit button
                Button(action: {
                    Task {
                        await viewModel.submitReview()
                    }
                }) {
                    if viewModel.isSubmitting {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    } else {
                        Text("Submit Review")
                            .font(UmuveTypography.h3Font)
                            .foregroundColor(.white)
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(height: 56)
                .background(viewModel.canSubmit ? Color.umuvePrimary : Color.umuveTextMuted)
                .cornerRadius(28)
                .disabled(!viewModel.canSubmit)
                .padding(.horizontal, UmuveSpacing.xlarge)
                .padding(.bottom, UmuveSpacing.xxlarge)
            }
        }
    }

    // MARK: - Star Picker

    private var starPicker: some View {
        HStack(spacing: UmuveSpacing.medium) {
            ForEach(1...5, id: \.self) { star in
                Button(action: {
                    withAnimation(AnimationConstants.snappySpring) {
                        viewModel.rating = star
                    }
                    HapticManager.shared.selection()
                }) {
                    Image(systemName: star <= viewModel.rating ? "star.fill" : "star")
                        .font(.system(size: 44))
                        .foregroundColor(star <= viewModel.rating ? .umuvePrimary : .umuveBorder)
                        .scaleEffect(star <= viewModel.rating ? 1.1 : 1.0)
                        .animation(AnimationConstants.bouncySpring, value: viewModel.rating)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.vertical, UmuveSpacing.normal)
    }

    // MARK: - Success View

    private var successView: some View {
        VStack(spacing: UmuveSpacing.xxlarge) {
            Spacer()

            ZStack {
                Circle()
                    .fill(Color.umuveSuccess.opacity(0.15))
                    .frame(width: 120, height: 120)

                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 56))
                    .foregroundStyle(Color.umuveSuccess)
            }

            VStack(spacing: UmuveSpacing.small) {
                Text("Thank you!")
                    .font(UmuveTypography.h1Font)
                    .foregroundColor(.umuveText)

                Text("Your review has been submitted")
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)

                // Show the stars the user gave
                HStack(spacing: 4) {
                    ForEach(1...5, id: \.self) { star in
                        Image(systemName: star <= viewModel.rating ? "star.fill" : "star")
                            .font(.system(size: 20))
                            .foregroundColor(star <= viewModel.rating ? .umuvePrimary : .umuveBorder)
                    }
                }
                .padding(.top, UmuveSpacing.small)
            }

            Spacer()

            Button(action: { dismiss() }) {
                Text("Done")
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.white)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 56)
            .background(Color.umuvePrimary)
            .cornerRadius(28)
            .padding(.horizontal, UmuveSpacing.xlarge)
            .padding(.bottom, UmuveSpacing.xxlarge)
        }
        .transition(.opacity)
    }

    // MARK: - Helpers

    private var ratingLabel: String {
        switch viewModel.rating {
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
    RatingReviewView(jobId: "test-job-123")
}

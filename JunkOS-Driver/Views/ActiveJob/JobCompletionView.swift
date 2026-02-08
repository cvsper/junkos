//
//  JobCompletionView.swift
//  JunkOS Driver
//
//  Celebration screen after completing a job.
//

import SwiftUI

struct JobCompletionView: View {
    let job: DriverJob
    @Bindable var appState: AppState
    @State private var isVisible = false
    @State private var showConfetti = false

    var body: some View {
        VStack(spacing: DriverSpacing.xxl) {
            Spacer()

            // Celebration icon
            ZStack {
                Circle()
                    .fill(Color.driverSuccess.opacity(0.15))
                    .frame(width: 120, height: 120)
                    .scaleEffect(isVisible ? 1 : 0.5)

                Image(systemName: "checkmark.seal.fill")
                    .font(.system(size: 56))
                    .foregroundStyle(Color.driverSuccess)
                    .scaleEffect(isVisible ? 1 : 0)
            }

            VStack(spacing: DriverSpacing.xs) {
                Text("Job Complete!")
                    .font(DriverTypography.title)
                    .foregroundStyle(Color.driverText)

                Text("Great work! The customer has been notified.")
                    .font(DriverTypography.body)
                    .foregroundStyle(Color.driverTextSecondary)
                    .multilineTextAlignment(.center)
            }
            .opacity(isVisible ? 1 : 0)
            .offset(y: isVisible ? 0 : 20)

            // Earnings
            VStack(spacing: DriverSpacing.xs) {
                Text("You earned")
                    .font(DriverTypography.footnote)
                    .foregroundStyle(Color.driverTextSecondary)

                Text(job.formattedPrice)
                    .font(DriverTypography.stat)
                    .foregroundStyle(Color.driverPrimary)
            }
            .opacity(isVisible ? 1 : 0)
            .offset(y: isVisible ? 0 : 20)

            Spacer()

            // Done button
            Button {
                appState.activeJob = nil
            } label: {
                Text("Back to Dashboard")
            }
            .buttonStyle(DriverPrimaryButtonStyle())
            .padding(.horizontal, DriverSpacing.xl)
            .padding(.bottom, DriverSpacing.xxl)
            .opacity(isVisible ? 1 : 0)
        }
        .onAppear {
            HapticManager.shared.success()
            withAnimation(AnimationConstants.bouncySpring.delay(0.2)) {
                isVisible = true
            }
        }
    }
}

//
//  AfterPhotosView.swift
//  Umuve Pro
//
//  Camera capture for "after" photos + Rescue Engine outcome picker
//  + Mark Complete button.
//

import SwiftUI

// MARK: - Rescue Engine v1 — load outcome

/// What the hauler did with the load. Raw values match the backend contract
/// (`disposition_outcome`).
enum DispositionOutcome: String, CaseIterable, Identifiable {
    case donated
    case recycled
    case disposed
    case mixed
    case couldNot = "could_not"

    var id: String { rawValue }

    var label: String {
        switch self {
        case .donated: return "Donated / routed for reuse"
        case .recycled: return "Recycled"
        case .disposed: return "Disposed"
        case .mixed: return "Mixed load (some diverted)"
        case .couldNot: return "Couldn't donate/recycle"
        }
    }

    var icon: String {
        switch self {
        case .donated: return "gift.fill"
        case .recycled: return "arrow.3.trianglepath"
        case .disposed: return "trash.fill"
        case .mixed: return "square.split.2x1.fill"
        case .couldNot: return "xmark.circle.fill"
        }
    }

    /// Whether picking this outcome reveals the optional note field.
    var allowsNote: Bool {
        self == .couldNot || self == .mixed
    }

    /// Sensible default seeded from the customer's stated preference.
    /// "recycle" → recycled, "donate" → donated, anything else → disposed.
    static func `default`(for preference: String?) -> DispositionOutcome {
        guard let pref = preference?.lowercased() else { return .disposed }
        if pref.contains("recycl") { return .recycled }
        if pref.contains("donat") { return .donated }
        return .disposed
    }
}

struct AfterPhotosView: View {
    @Bindable var viewModel: ActiveJobViewModel
    @State private var showCamera = false
    @State private var outcome: DispositionOutcome = .disposed
    @State private var dispositionNotes: String = ""
    @State private var didSeedOutcome = false

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: DriverSpacing.lg) {
                    // Instructions
                    VStack(spacing: DriverSpacing.xs) {
                        Image(systemName: "camera.badge.clock.fill")
                            .font(.system(size: 40))
                            .foregroundStyle(Color.driverPrimary)

                        Text("After Photos")
                            .font(DriverTypography.title3)
                            .foregroundStyle(Color.driverText)

                        Text("Take photos showing the clean area after removal")
                            .font(DriverTypography.footnote)
                            .foregroundStyle(Color.driverTextSecondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.horizontal, DriverSpacing.xl)

                    // Photo grid
                    if !viewModel.afterPhotos.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: DriverSpacing.sm) {
                                ForEach(viewModel.afterPhotos.indices, id: \.self) { index in
                                    Image(uiImage: viewModel.afterPhotos[index])
                                        .resizable()
                                        .scaledToFill()
                                        .frame(width: 100, height: 100)
                                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.sm))
                                }

                                Button {
                                    showCamera = true
                                } label: {
                                    VStack {
                                        Image(systemName: "plus")
                                            .font(.system(size: 24))
                                            .foregroundStyle(Color.driverPrimary)
                                    }
                                    .frame(width: 100, height: 100)
                                    .background(
                                        RoundedRectangle(cornerRadius: DriverRadius.sm)
                                            .strokeBorder(Color.driverPrimary, style: StrokeStyle(lineWidth: 2, dash: [6]))
                                    )
                                }
                            }
                            .padding(.horizontal, DriverSpacing.xl)
                        }
                    } else {
                        Button {
                            showCamera = true
                        } label: {
                            VStack(spacing: DriverSpacing.sm) {
                                Image(systemName: "camera.badge.ellipsis")
                                    .font(.system(size: 32))
                                Text("Take Photo")
                                    .font(DriverTypography.headline)
                            }
                            .foregroundStyle(Color.driverPrimary)
                            .frame(maxWidth: .infinity)
                            .frame(height: 140)
                            .background(
                                RoundedRectangle(cornerRadius: DriverRadius.lg)
                                    .strokeBorder(Color.driverPrimary, style: StrokeStyle(lineWidth: 2, dash: [8]))
                                    .background(RoundedRectangle(cornerRadius: DriverRadius.lg).fill(Color.driverPrimary.opacity(0.05)))
                            )
                        }
                        .buttonStyle(.plain)
                        .padding(.horizontal, DriverSpacing.xl)
                    }

                    // Rescue Engine — where did the load go?
                    dispositionSection
                        .padding(.horizontal, DriverSpacing.xl)
                }
                .padding(.vertical, DriverSpacing.lg)
            }

            // Complete job — pinned so the outcome picker never pushes it off-screen
            Button {
                Task {
                    await viewModel.markCompleted(
                        dispositionOutcome: outcome.rawValue,
                        dispositionNotes: notesToSend
                    )
                }
            } label: {
                if viewModel.isUpdating {
                    ProgressView().tint(.white)
                } else {
                    Text("Complete Job")
                }
            }
            .buttonStyle(DriverPrimaryButtonStyle(isEnabled: !viewModel.afterPhotos.isEmpty))
            .disabled(viewModel.afterPhotos.isEmpty || viewModel.isUpdating)
            .padding(.horizontal, DriverSpacing.xl)
            .padding(.top, DriverSpacing.sm)
            .padding(.bottom, DriverSpacing.xxl)
        }
        .onAppear(perform: seedOutcomeIfNeeded)
        .sheet(isPresented: $showCamera) {
            CameraPickerView { image in
                viewModel.afterPhotos.append(image)
            }
        }
    }

    // MARK: - Disposition Picker

    private var dispositionSection: some View {
        VStack(alignment: .leading, spacing: DriverSpacing.sm) {
            Text("What happened to the load?")
                .font(DriverTypography.headline)
                .foregroundStyle(Color.driverText)

            VStack(spacing: DriverSpacing.xs) {
                ForEach(DispositionOutcome.allCases) { option in
                    outcomeRow(option)
                }
            }

            if outcome.allowsNote {
                TextField("Add a note (optional)", text: $dispositionNotes, axis: .vertical)
                    .lineLimit(1...3)
                    .textFieldStyle(DriverTextFieldStyle())
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
    }

    private func outcomeRow(_ option: DispositionOutcome) -> some View {
        let isSelected = outcome == option
        return Button {
            withAnimation(.easeInOut(duration: 0.15)) { outcome = option }
            HapticManager.shared.selection()
        } label: {
            HStack(spacing: DriverSpacing.sm) {
                Image(systemName: option.icon)
                    .font(.system(size: 15))
                    .foregroundStyle(isSelected ? Color.driverPrimary : Color.driverTextTertiary)
                    .frame(width: 22)

                Text(option.label)
                    .font(DriverTypography.callout)
                    .foregroundStyle(Color.driverText)
                    .multilineTextAlignment(.leading)

                Spacer(minLength: DriverSpacing.xs)

                Image(systemName: isSelected ? "largecircle.fill.circle" : "circle")
                    .font(.system(size: 18))
                    .foregroundStyle(isSelected ? Color.driverPrimary : Color.driverBorder)
            }
            .padding(.vertical, DriverSpacing.sm)
            .padding(.horizontal, DriverSpacing.md)
            .background(
                RoundedRectangle(cornerRadius: DriverRadius.md)
                    .fill(isSelected ? Color.driverPrimary.opacity(0.06) : Color.clear)
            )
            .overlay(
                RoundedRectangle(cornerRadius: DriverRadius.md)
                    .stroke(isSelected ? Color.driverPrimary.opacity(0.4) : Color.driverBorder, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: - Helpers

    /// Trimmed note, only when the selected outcome exposes the field.
    private var notesToSend: String? {
        guard outcome.allowsNote else { return nil }
        let trimmed = dispositionNotes.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    /// Pre-select the outcome from the customer's disposition preference the
    /// first time the screen appears. Never clobbers a hauler's own choice.
    private func seedOutcomeIfNeeded() {
        guard !didSeedOutcome else { return }
        didSeedOutcome = true
        outcome = DispositionOutcome.default(for: viewModel.job?.dispositionPreference)
    }
}

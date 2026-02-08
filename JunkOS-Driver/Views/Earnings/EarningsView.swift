//
//  EarningsView.swift
//  JunkOS Driver
//
//  Earnings history with period filter and summary.
//

import SwiftUI

struct EarningsView: View {
    @Bindable var appState: AppState
    @State private var viewModel = EarningsViewModel()

    var body: some View {
        NavigationStack {
            ZStack {
                Color.driverBackground.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: DriverSpacing.lg) {
                        // Period picker
                        Picker("Period", selection: $viewModel.selectedPeriod) {
                            ForEach(EarningsViewModel.EarningsPeriod.allCases, id: \.self) { period in
                                Text(period.rawValue).tag(period)
                            }
                        }
                        .pickerStyle(.segmented)
                        .padding(.horizontal, DriverSpacing.xl)

                        // Summary card
                        VStack(spacing: DriverSpacing.xs) {
                            Text("Total Earnings")
                                .font(DriverTypography.footnote)
                                .foregroundStyle(Color.driverTextSecondary)

                            Text(viewModel.displayedAmount)
                                .font(DriverTypography.stat)
                                .foregroundStyle(Color.driverPrimary)
                        }
                        .frame(maxWidth: .infinity)
                        .driverCard()
                        .padding(.horizontal, DriverSpacing.xl)

                        // Entries list
                        if viewModel.entries.isEmpty {
                            EmptyStateView(
                                icon: "dollarsign.circle",
                                title: "No Earnings Yet",
                                message: "Complete jobs to start earning. Your earnings history will appear here."
                            )
                            .frame(height: 200)
                        } else {
                            VStack(spacing: DriverSpacing.xs) {
                                ForEach(viewModel.entries) { entry in
                                    EarningsRow(entry: entry)
                                }
                            }
                            .padding(.horizontal, DriverSpacing.xl)
                        }
                    }
                    .padding(.top, DriverSpacing.md)
                    .padding(.bottom, DriverSpacing.xxxl)
                }
            }
            .navigationTitle("Earnings")
            .navigationBarTitleDisplayMode(.large)
        }
    }
}

private struct EarningsRow: View {
    let entry: EarningsEntry

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: DriverSpacing.xxxs) {
                Text(entry.address)
                    .font(DriverTypography.subheadline)
                    .foregroundStyle(Color.driverText)
                    .lineLimit(1)

                Text(entry.formattedDate)
                    .font(DriverTypography.caption2)
                    .foregroundStyle(Color.driverTextTertiary)
            }

            Spacer()

            Text(entry.formattedAmount)
                .font(DriverTypography.priceSmall)
                .foregroundStyle(Color.driverPrimary)
        }
        .padding(DriverSpacing.sm)
        .background(Color.driverSurface)
        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.sm))
    }
}

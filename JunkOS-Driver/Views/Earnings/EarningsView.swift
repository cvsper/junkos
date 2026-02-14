//
//  EarningsView.swift
//  Umuve Pro
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
                        // Error banner
                        if let errorMessage = viewModel.errorMessage {
                            HStack {
                                Text(errorMessage)
                                    .font(DriverTypography.caption1)
                                    .foregroundStyle(.white)
                                    .lineLimit(2)

                                Spacer()

                                Button("Retry") {
                                    Task { await viewModel.fetchEarnings() }
                                }
                                .font(DriverTypography.caption1)
                                .foregroundStyle(.white)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(.white.opacity(0.2))
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                            }
                            .padding()
                            .background(Color.red)
                            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                            .padding(.horizontal, DriverSpacing.xl)
                            .onTapGesture {
                                viewModel.errorMessage = nil
                            }
                        }

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

                            // Job count (if available)
                            if !viewModel.filteredEntries.isEmpty {
                                Text("\(viewModel.filteredEntries.count) jobs")
                                    .font(DriverTypography.caption2)
                                    .foregroundStyle(Color.driverTextTertiary)
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .driverCard()
                        .padding(.horizontal, DriverSpacing.xl)

                        // Loading or entries list
                        if viewModel.isLoading && viewModel.entries.isEmpty {
                            VStack(spacing: DriverSpacing.md) {
                                ProgressView()
                                    .tint(Color.driverPrimary)
                                Text("Loading earnings...")
                                    .font(DriverTypography.caption1)
                                    .foregroundStyle(Color.driverTextSecondary)
                            }
                            .frame(height: 200)
                        } else if viewModel.filteredEntries.isEmpty {
                            EmptyStateView(
                                icon: "dollarsign.circle",
                                title: "No Earnings Yet",
                                message: "Complete jobs to start earning. Your earnings history will appear here."
                            )
                            .frame(height: 200)
                        } else {
                            VStack(spacing: DriverSpacing.xs) {
                                ForEach(viewModel.filteredEntries) { entry in
                                    EarningsRow(entry: entry)
                                }
                            }
                            .padding(.horizontal, DriverSpacing.xl)
                        }
                    }
                    .padding(.top, DriverSpacing.md)
                    .padding(.bottom, DriverSpacing.xxxl)
                }
                .refreshable {
                    await viewModel.fetchEarnings()
                }
            }
            .navigationTitle("Earnings")
            .navigationBarTitleDisplayMode(.large)
            .task {
                await viewModel.fetchEarnings()
            }
        }
    }
}

private struct EarningsRow: View {
    let entry: EarningsEntry

    var body: some View {
        HStack(alignment: .top) {
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

            VStack(alignment: .trailing, spacing: DriverSpacing.xxxs) {
                Text(entry.formattedAmount)
                    .font(DriverTypography.priceSmall)
                    .foregroundStyle(Color.driverPrimary)

                // Payout status badge
                Text(entry.payoutStatus.displayName)
                    .font(DriverTypography.caption2)
                    .foregroundStyle(payoutStatusColor(entry.payoutStatus))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(payoutStatusColor(entry.payoutStatus).opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 4))
            }
        }
        .padding(DriverSpacing.sm)
        .background(Color.driverSurface)
        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.sm))
    }

    private func payoutStatusColor(_ status: PayoutStatus) -> Color {
        switch status {
        case .pending: return Color("driverWarning")
        case .processing: return Color("driverPrimary")
        case .paid: return Color("driverSuccess")
        }
    }
}

//
//  AvailabilityScheduleView.swift
//  JunkOS Driver
//
//  Weekly availability schedule editor.
//

import SwiftUI

struct AvailabilityScheduleView: View {
    @Bindable var appState: AppState
    @State private var schedule: [String: Bool] = [
        "monday": true,
        "tuesday": true,
        "wednesday": true,
        "thursday": true,
        "friday": true,
        "saturday": false,
        "sunday": false,
    ]

    private let days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    var body: some View {
        ZStack {
            Color.driverBackground.ignoresSafeArea()

            ScrollView {
                VStack(spacing: DriverSpacing.sm) {
                    Text("Set the days you're available to work")
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverTextSecondary)
                        .padding(.horizontal, DriverSpacing.xl)
                        .padding(.top, DriverSpacing.md)

                    ForEach(days, id: \.self) { day in
                        HStack {
                            Text(day.capitalized)
                                .font(DriverTypography.body)
                                .foregroundStyle(Color.driverText)

                            Spacer()

                            Toggle("", isOn: Binding(
                                get: { schedule[day] ?? false },
                                set: { schedule[day] = $0 }
                            ))
                            .tint(Color.driverPrimary)
                        }
                        .padding(.horizontal, DriverSpacing.md)
                        .padding(.vertical, DriverSpacing.sm)
                        .background(Color.driverSurface)
                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.sm))
                        .padding(.horizontal, DriverSpacing.xl)
                    }
                }
                .padding(.bottom, DriverSpacing.xxxl)
            }
        }
        .navigationTitle("Availability")
        .navigationBarTitleDisplayMode(.inline)
    }
}

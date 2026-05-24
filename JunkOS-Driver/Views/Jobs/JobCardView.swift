//
//  JobCardView.swift
//  Umuve Pro
//
//  Rich job card built for driving — in-truck, glove-friendly.
//  Hierarchy: money is loudest, then distance/time, then everything else.
//

import SwiftUI
import MapKit

struct JobCardView: View {
    let job: DriverJob

    var body: some View {
        VStack(spacing: 0) {
            // Map ribbon up top (Apple Maps — free, no API key)
            mapRibbon

            // Body
            VStack(alignment: .leading, spacing: DriverSpacing.sm) {
                priceHero
                addressBlock
                itemChips
                scheduledPill
            }
            .padding(DriverSpacing.md)
        }
        .background(
            ZStack {
                Color.driverSurface
                LinearGradient(
                    colors: [
                        Color.driverPrimary.opacity(0.05),
                        Color.clear
                    ],
                    startPoint: .bottomLeading,
                    endPoint: .topTrailing
                )
            }
        )
        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
        .overlay(
            // Left urgency rail
            HStack {
                urgencyRail
                    .frame(width: 4)
                Spacer()
            }
            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
        )
        .shadow(color: .black.opacity(0.08), radius: 12, x: 0, y: 4)
    }

    // MARK: - Map ribbon

    @ViewBuilder
    private var mapRibbon: some View {
        if let lat = job.lat, let lng = job.lng {
            let coordinate = CLLocationCoordinate2D(latitude: lat, longitude: lng)
            Map(initialPosition: .region(MKCoordinateRegion(
                center: coordinate,
                span: MKCoordinateSpan(latitudeDelta: 0.012, longitudeDelta: 0.012)
            ))) {
                Annotation("", coordinate: coordinate, anchor: .bottom) {
                    ZStack {
                        Circle()
                            .fill(Color.driverPrimary.opacity(0.25))
                            .frame(width: 32, height: 32)
                        Circle()
                            .fill(Color.driverPrimary)
                            .frame(width: 14, height: 14)
                            .overlay(
                                Circle()
                                    .stroke(Color.white, lineWidth: 2)
                            )
                    }
                }
            }
            .mapStyle(.standard(elevation: .flat, pointsOfInterest: .excludingAll, showsTraffic: false))
            .frame(height: 110)
            .allowsHitTesting(false)
            .overlay(alignment: .topTrailing) {
                distanceBadge
                    .padding(DriverSpacing.sm)
            }
        } else {
            // No coords — synthetic banner
            Rectangle()
                .fill(
                    LinearGradient(
                        colors: [Color.driverPrimary.opacity(0.7), Color.driverPrimaryLight],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .frame(height: 60)
                .overlay(
                    HStack(spacing: DriverSpacing.xs) {
                        Image(systemName: "mappin.and.ellipse")
                        Text(job.shortAddress)
                    }
                    .font(DriverTypography.headline)
                    .foregroundStyle(.white)
                )
        }
    }

    private var distanceBadge: some View {
        HStack(spacing: 4) {
            Image(systemName: "location.fill")
                .font(.system(size: 10, weight: .bold))
            Text(job.formattedDistance)
                .font(.system(size: 12, weight: .semibold, design: .rounded))
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(.black.opacity(0.65))
        .clipShape(Capsule())
    }

    // MARK: - Price Hero

    private var priceHero: some View {
        HStack(alignment: .firstTextBaseline, spacing: DriverSpacing.xs) {
            // The number itself — big and bold
            Text(job.formattedPrice)
                .font(.system(size: 36, weight: .heavy, design: .rounded))
                .foregroundStyle(Color.driverText)
                .lineLimit(1)
                .minimumScaleFactor(0.7)

            // Driver take subtitle (80%)
            Text("you keep ~\(driverTake)")
                .font(.system(size: 12, weight: .medium, design: .rounded))
                .foregroundStyle(Color.driverSuccess)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.driverSuccess.opacity(0.12))
                .clipShape(Capsule())

            Spacer(minLength: 0)

            etaPill
        }
    }

    private var driverTake: String {
        String(format: "$%.0f", job.totalPrice * 0.80)
    }

    private var etaPill: some View {
        HStack(spacing: 4) {
            Image(systemName: "car.fill")
                .font(.system(size: 11, weight: .semibold))
            Text(etaMinutes)
                .font(.system(size: 13, weight: .semibold, design: .rounded))
        }
        .foregroundStyle(Color.driverText)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(Color.driverBackground)
        .clipShape(Capsule())
    }

    /// Rough drive ETA = miles × 2.5 min/mi (city default).
    private var etaMinutes: String {
        guard let miles = job.distanceMiles else { return "—" }
        let mins = max(1, Int((miles * 2.5).rounded()))
        if mins < 60 { return "\(mins) min" }
        return String(format: "%.1f hr", Double(mins) / 60.0)
    }

    // MARK: - Address

    private var addressBlock: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(job.shortAddress)
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(Color.driverText)
                .lineLimit(1)

            Text(restOfAddress)
                .font(DriverTypography.footnote)
                .foregroundStyle(Color.driverTextSecondary)
                .lineLimit(1)
        }
    }

    private var restOfAddress: String {
        let parts = job.address.components(separatedBy: ",")
        guard parts.count > 1 else { return "—" }
        return parts.dropFirst().joined(separator: ",").trimmingCharacters(in: .whitespaces)
    }

    // MARK: - Item chips

    @ViewBuilder
    private var itemChips: some View {
        if let items = job.items, !items.isEmpty {
            HStack(spacing: 6) {
                ForEach(Array(items.prefix(3).enumerated()), id: \.offset) { _, item in
                    chip(for: item)
                }
                if items.count > 3 {
                    Text("+\(items.count - 3) more")
                        .font(.system(size: 12, weight: .semibold, design: .rounded))
                        .foregroundStyle(Color.driverTextSecondary)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.driverDivider)
                        .clipShape(Capsule())
                }
                Spacer(minLength: 0)
            }
        }
    }

    private func chip(for item: JobItem) -> some View {
        let icon = Self.iconForCategory(item.category)
        let qty = item.quantity ?? 1
        return HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.system(size: 11, weight: .semibold))
            Text(qty > 1 ? "\(item.category) ×\(qty)" : item.category)
                .font(.system(size: 12, weight: .medium))
                .lineLimit(1)
        }
        .foregroundStyle(Color.driverText)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color.driverPrimary.opacity(0.08))
        .clipShape(Capsule())
    }

    static func iconForCategory(_ raw: String) -> String {
        let s = raw.lowercased()
        if s.contains("couch") || s.contains("sofa") { return "sofa.fill" }
        if s.contains("mattress") || s.contains("bed") { return "bed.double.fill" }
        if s.contains("chair") { return "chair.fill" }
        if s.contains("tv") || s.contains("television") || s.contains("monitor") { return "tv.fill" }
        if s.contains("fridge") || s.contains("appliance") { return "refrigerator.fill" }
        if s.contains("box") || s.contains("misc") { return "shippingbox.fill" }
        if s.contains("desk") || s.contains("table") { return "table.furniture.fill" }
        if s.contains("yard") || s.contains("debris") || s.contains("brush") { return "leaf.fill" }
        if s.contains("metal") || s.contains("scrap") { return "wrench.and.screwdriver.fill" }
        return "shippingbox.fill"
    }

    // MARK: - Scheduled pill

    @ViewBuilder
    private var scheduledPill: some View {
        if let date = job.scheduledDate {
            HStack(spacing: 6) {
                Image(systemName: scheduleIcon(for: date))
                    .font(.system(size: 12, weight: .semibold))
                Text(scheduleLabel(for: date))
                    .font(.system(size: 13, weight: .semibold, design: .rounded))
            }
            .foregroundStyle(scheduleColor(for: date))
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(scheduleColor(for: date).opacity(0.12))
            .clipShape(Capsule())
        }
    }

    private func scheduleLabel(for date: Date) -> String {
        let interval = date.timeIntervalSinceNow
        if interval < 0 {
            return "Ready now"
        } else if interval < 3600 {
            let mins = Int(interval / 60)
            return "In \(mins) min"
        } else if Calendar.current.isDateInToday(date) {
            return "Today at \(timeString(date))"
        } else if Calendar.current.isDateInTomorrow(date) {
            return "Tomorrow at \(timeString(date))"
        } else {
            let formatter = DateFormatter()
            formatter.dateFormat = "EEE, MMM d 'at' h:mm a"
            return formatter.string(from: date)
        }
    }

    private func timeString(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm a"
        return formatter.string(from: date)
    }

    private func scheduleIcon(for date: Date) -> String {
        let interval = date.timeIntervalSinceNow
        if interval < 1800 { return "bolt.fill" }    // < 30 min — urgent
        if Calendar.current.isDateInToday(date) { return "clock.fill" }
        return "calendar"
    }

    private func scheduleColor(for date: Date) -> Color {
        let interval = date.timeIntervalSinceNow
        if interval < 1800 { return .driverError }       // urgent
        if Calendar.current.isDateInToday(date) { return .driverWarning }
        return .driverInfo
    }

    // MARK: - Urgency rail

    private var urgencyRail: some View {
        Rectangle()
            .fill(railColor)
    }

    private var railColor: Color {
        guard let date = job.scheduledDate else { return .driverInfo }
        let interval = date.timeIntervalSinceNow
        if interval < 1800 { return .driverError }
        if Calendar.current.isDateInToday(date) { return .driverWarning }
        return .driverInfo
    }
}

//
//  DumpSuggestionView.swift
//  Umuve Pro
//
//  "Where do I dump this?" — the backend ranks every permitted facility for
//  the hauler's position and the load on the truck (tip fee + drive), and
//  says why. This card shows the pick, the reasons, the facility details,
//  and the runner-ups.
//

import SwiftUI
import MapKit
import CoreLocation

@Observable
final class DumpSuggestionViewModel {
    var response: DumpSuggestResponse?
    var isLoading = false
    var errorMessage: String?
    private var lastKey: String?

    func load(jobId: String?, location: CLLocation?, force: Bool = false) async {
        let key = "\(jobId ?? "-")|\(location.map { "\(Int($0.coordinate.latitude * 100)),\(Int($0.coordinate.longitude * 100))" } ?? "-")"
        if !force, key == lastKey, response != nil { return }
        isLoading = true
        errorMessage = nil
        do {
            response = try await DriverAPIClient.shared.getDumpSuggestion(
                jobId: jobId,
                lat: location?.coordinate.latitude,
                lng: location?.coordinate.longitude
            )
            lastKey = key
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

struct DumpSuggestionView: View {
    let job: DriverJob
    @Bindable var appState: AppState
    @State private var viewModel = DumpSuggestionViewModel()
    @State private var showAlternatives = false
    @State private var selected: DumpOption?

    var body: some View {
        VStack(alignment: .leading, spacing: DriverSpacing.sm) {
            header

            if let r = viewModel.response, let pick = r.suggested {
                DumpPickCard(option: pick, assumptions: r.assumptions) { selected = pick }

                if !r.alternatives.isEmpty {
                    Button {
                        withAnimation(AnimationConstants.smoothSpring) { showAlternatives.toggle() }
                    } label: {
                        HStack {
                            Text(showAlternatives ? "Hide other options" : "\(r.alternatives.count) other option\(r.alternatives.count == 1 ? "" : "s")")
                            Spacer()
                            Image(systemName: showAlternatives ? "chevron.up" : "chevron.down")
                        }
                        .font(DriverTypography.subheadline)
                        .foregroundStyle(Color.driverTextSecondary)
                    }
                    .padding(.horizontal, DriverSpacing.xxs)

                    if showAlternatives {
                        VStack(spacing: DriverSpacing.xs) {
                            ForEach(r.alternatives) { alt in
                                DumpAltRow(option: alt) { selected = alt }
                            }
                        }
                    }
                }
            } else if viewModel.isLoading {
                HStack(spacing: DriverSpacing.sm) {
                    ProgressView().tint(Color.driverPrimary)
                    Text("Finding the cheapest place to tip this load…")
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverTextSecondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(DriverSpacing.md)
                .background(Color.driverSurfaceElevated)
                .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
            } else if let err = viewModel.errorMessage {
                VStack(alignment: .leading, spacing: DriverSpacing.xs) {
                    Text("Couldn't load dump options")
                        .font(DriverTypography.headline)
                        .foregroundStyle(Color.driverText)
                    Text(err)
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverTextSecondary)
                    Button("Try again") { Task { await reload(force: true) } }
                        .font(DriverTypography.subheadline)
                        .foregroundStyle(Color.driverPrimary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(DriverSpacing.md)
                .background(Color.driverSurfaceElevated)
                .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
            } else if viewModel.response != nil {
                Text("No permitted facility within range can take this load. Call dispatch.")
                    .font(DriverTypography.footnote)
                    .foregroundStyle(Color.driverWarning)
                    .padding(DriverSpacing.md)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.driverWarning.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
            }
        }
        .padding(.horizontal, DriverSpacing.xl)
        .task { await reload() }
        .sheet(item: $selected) { option in
            DumpFacilityDetailSheet(option: option)
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            Label("Where to dump", systemImage: "arrow.down.to.line.compact")
                .font(DriverTypography.headline)
                .foregroundStyle(Color.driverText)
            Spacer()
            if let a = viewModel.response?.assumptions {
                Text("\(a.categoryLabel) · ~\(a.tons, specifier: "%.1f") t")
                    .font(DriverTypography.caption)
                    .foregroundStyle(Color.driverTextTertiary)
            }
            Button {
                Task { await reload(force: true) }
            } label: {
                Image(systemName: "arrow.clockwise")
                    .font(DriverTypography.caption)
                    .foregroundStyle(Color.driverTextSecondary)
            }
            .accessibilityLabel("Refresh dump suggestion")
        }
    }

    private func reload(force: Bool = false) async {
        await viewModel.load(jobId: job.id, location: appState.locationManager.currentLocation, force: force)
    }
}

// MARK: - Pick card

private struct DumpPickCard: View {
    let option: DumpOption
    let assumptions: DumpAssumptions
    let onDetails: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: DriverSpacing.sm) {
            HStack(alignment: .top, spacing: DriverSpacing.sm) {
                VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                    Text(option.facility.name)
                        .font(DriverTypography.title3)
                        .foregroundStyle(Color.driverText)
                        .fixedSize(horizontal: false, vertical: true)
                    Text("\(option.facility.typeLabel) · \(option.facility.countyLabel)")
                        .font(DriverTypography.caption)
                        .foregroundStyle(Color.driverTextSecondary)
                }
                Spacer(minLength: DriverSpacing.xs)
                DumpCostBadge(option: option)
            }

            HStack(spacing: DriverSpacing.md) {
                Label("\(option.miles, specifier: "%.1f") mi", systemImage: "car.fill")
                Label("\(option.minutes) min", systemImage: "clock")
                if option.openNow, let c = option.closesAt {
                    Label("Closes \(c)", systemImage: "door.left.hand.open")
                        .foregroundStyle(Color.driverSuccess)
                } else if let n = option.nextOpen {
                    Label("Opens \(n)", systemImage: "door.left.hand.closed")
                        .foregroundStyle(Color.driverWarning)
                }
            }
            .font(DriverTypography.footnote)
            .foregroundStyle(Color.driverTextSecondary)

            // Why this one
            VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                ForEach(option.reasons, id: \.self) { reason in
                    HStack(alignment: .top, spacing: DriverSpacing.xs) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 13))
                            .foregroundStyle(Color.driverSuccess)
                            .padding(.top, 2)
                        Text(reason)
                            .font(DriverTypography.subheadline)
                            .foregroundStyle(Color.driverText)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                ForEach(option.caveats.prefix(2), id: \.self) { caveat in
                    HStack(alignment: .top, spacing: DriverSpacing.xs) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.system(size: 13))
                            .foregroundStyle(Color.driverWarning)
                            .padding(.top, 2)
                        Text(caveat)
                            .font(DriverTypography.footnote)
                            .foregroundStyle(Color.driverTextSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }

            HStack(spacing: DriverSpacing.sm) {
                Button {
                    DumpNavigation.openDirections(to: option.facility)
                } label: {
                    Label("Navigate", systemImage: "location.fill")
                        .font(DriverTypography.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, DriverSpacing.sm)
                        .background(Color.driverPrimary)
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                }
                Button(action: onDetails) {
                    Text("Details")
                        .font(DriverTypography.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, DriverSpacing.sm)
                        .background(Color.driverPrimary.opacity(0.1))
                        .foregroundStyle(Color.driverPrimary)
                        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                }
            }
        }
        .padding(DriverSpacing.md)
        .background(Color.driverSurface)
        .overlay(RoundedRectangle(cornerRadius: DriverRadius.lg).strokeBorder(Color.driverBorder))
        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
    }
}

private struct DumpCostBadge: View {
    let option: DumpOption

    var body: some View {
        VStack(alignment: .trailing, spacing: 0) {
            if let total = option.estTotal {
                Text("$\(total, specifier: "%.0f")")
                    .font(DriverTypography.price)
                    .foregroundStyle(Color.driverText)
                Text(option.rateEstimated == true ? "est. trip" : "trip est.")
                    .font(DriverTypography.caption2)
                    .foregroundStyle(Color.driverTextTertiary)
            } else {
                Text("quote")
                    .font(DriverTypography.priceSmall)
                    .foregroundStyle(Color.driverTextSecondary)
                Text("at the gate")
                    .font(DriverTypography.caption2)
                    .foregroundStyle(Color.driverTextTertiary)
            }
        }
    }
}

// MARK: - Alternatives

private struct DumpAltRow: View {
    let option: DumpOption
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: DriverSpacing.sm) {
                VStack(alignment: .leading, spacing: DriverSpacing.xxxs) {
                    Text(option.facility.name)
                        .font(DriverTypography.subheadline)
                        .foregroundStyle(Color.driverText)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                    HStack(spacing: DriverSpacing.xs) {
                        Text("\(option.miles, specifier: "%.1f") mi · \(option.minutes) min")
                        if let r = option.ratePerTon {
                            Text("· $\(r, specifier: "%.0f")/t\(option.rateEstimated == true ? " est." : "")")
                        }
                        if !option.openNow, let n = option.nextOpen {
                            Text("· opens \(n)").foregroundStyle(Color.driverWarning)
                        }
                    }
                    .font(DriverTypography.caption)
                    .foregroundStyle(Color.driverTextSecondary)
                }
                Spacer()
                if let t = option.estTotal {
                    Text("$\(t, specifier: "%.0f")")
                        .font(DriverTypography.priceSmall)
                        .foregroundStyle(Color.driverText)
                }
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Color.driverTextTertiary)
            }
            .padding(DriverSpacing.sm)
            .background(Color.driverSurfaceElevated)
            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Detail sheet

struct DumpFacilityDetailSheet: View {
    let option: DumpOption

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DriverSpacing.lg) {
                VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                    Text(option.facility.name)
                        .font(DriverTypography.title2)
                        .foregroundStyle(Color.driverText)
                        .fixedSize(horizontal: false, vertical: true)
                    Text("\(option.facility.typeLabel) · \(option.facility.operator ?? option.facility.countyLabel)")
                        .font(DriverTypography.subheadline)
                        .foregroundStyle(Color.driverTextSecondary)
                }

                // Cost breakdown
                if let tip = option.estTip, let drive = option.estDrive, let total = option.estTotal {
                    VStack(spacing: DriverSpacing.xs) {
                        costRow("Tip fee", tip, note: option.ratePerTon.map { "$\(String(format: "%.2f", $0))/ton\(option.rateEstimated == true ? " (estimated)" : "")\(option.rateNote.map { " · \($0)" } ?? "")" })
                        costRow("Drive there", drive, note: "\(String(format: "%.1f", option.miles)) mi, about \(option.minutes) min")
                        Divider()
                        costRow("Trip total", total, bold: true)
                    }
                    .padding(DriverSpacing.md)
                    .background(Color.driverSurfaceElevated)
                    .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                }

                section("Why") {
                    ForEach(option.reasons, id: \.self) { Text("• \($0)") }
                }
                if !option.caveats.isEmpty {
                    section("Before you go") {
                        ForEach(option.caveats, id: \.self) { Text("• \($0)") }
                    }
                }

                section("Facility") {
                    detailRow("Address", option.facility.address)
                    if let phone = option.facility.phone {
                        detailRow("Phone", DumpNavigation.prettyPhone(phone))
                    }
                    if option.openNow, let c = option.closesAt {
                        detailRow("Today", "Open now, closes \(c)")
                    } else if let n = option.nextOpen {
                        detailRow("Today", "Closed — opens \(n)")
                    }
                    detailRow("Payment", option.facility.accessLabel)
                    detailRow("Takes", option.facility.acceptsCategories.map(DumpNavigation.categoryLabel).joined(separator: ", "))
                }

                HStack(spacing: DriverSpacing.sm) {
                    Button {
                        DumpNavigation.openDirections(to: option.facility)
                    } label: {
                        Label("Navigate", systemImage: "location.fill")
                            .font(DriverTypography.headline)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, DriverSpacing.sm)
                            .background(Color.driverPrimary)
                            .foregroundStyle(.white)
                            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                    }
                    if let phone = option.facility.phone {
                        Button {
                            DumpNavigation.call(phone)
                        } label: {
                            Label("Call", systemImage: "phone.fill")
                                .font(DriverTypography.headline)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, DriverSpacing.sm)
                                .background(Color.driverPrimary.opacity(0.1))
                                .foregroundStyle(Color.driverPrimary)
                                .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
                        }
                    }
                }
            }
            .padding(DriverSpacing.xl)
        }
        .background(Color.driverBackground)
    }

    private func costRow(_ label: String, _ amount: Double, note: String? = nil, bold: Bool = false) -> some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 1) {
                Text(label)
                    .font(bold ? DriverTypography.headline : DriverTypography.subheadline)
                    .foregroundStyle(Color.driverText)
                if let note {
                    Text(note)
                        .font(DriverTypography.caption)
                        .foregroundStyle(Color.driverTextSecondary)
                }
            }
            Spacer()
            Text("$\(amount, specifier: "%.2f")")
                .font(bold ? DriverTypography.priceSmall : DriverTypography.subheadline)
                .foregroundStyle(Color.driverText)
                .monospacedDigit()
        }
    }

    private func section<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: DriverSpacing.xs) {
            Text(title.uppercased())
                .font(DriverTypography.caption)
                .foregroundStyle(Color.driverTextTertiary)
                .tracking(0.6)
            content()
                .font(DriverTypography.subheadline)
                .foregroundStyle(Color.driverText)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func detailRow(_ k: String, _ v: String) -> some View {
        HStack(alignment: .top, spacing: DriverSpacing.sm) {
            Text(k)
                .font(DriverTypography.caption)
                .foregroundStyle(Color.driverTextSecondary)
                .frame(width: 64, alignment: .leading)
            Text(v)
                .font(DriverTypography.subheadline)
                .foregroundStyle(Color.driverText)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

// MARK: - Helpers

enum DumpNavigation {
    static func openDirections(to f: DumpFacility) {
        let placemark = MKPlacemark(coordinate: CLLocationCoordinate2D(latitude: f.lat, longitude: f.lon))
        let item = MKMapItem(placemark: placemark)
        item.name = f.name
        item.openInMaps(launchOptions: [MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeDriving])
    }

    static func call(_ e164: String) {
        guard let url = URL(string: "tel:\(e164)") else { return }
        UIApplication.shared.open(url)
    }

    static func prettyPhone(_ e164: String) -> String {
        let digits = e164.filter(\.isNumber)
        guard digits.count == 11, digits.hasPrefix("1") else { return e164 }
        let d = Array(digits.dropFirst())
        return "(\(String(d[0...2]))) \(String(d[3...5]))-\(String(d[6...9]))"
    }

    static func categoryLabel(_ c: String) -> String {
        switch c {
        case "msw": return "garbage"
        case "c_and_d": return "C&D"
        case "yard": return "yard waste"
        case "bulky": return "bulk junk"
        case "metal": return "metal"
        case "appliance_w_freon": return "appliances"
        case "mattress": return "mattresses"
        case "tires": return "tires"
        case "concrete": return "concrete"
        case "drywall": return "drywall"
        case "mixed": return "mixed loads"
        default: return c
        }
    }
}

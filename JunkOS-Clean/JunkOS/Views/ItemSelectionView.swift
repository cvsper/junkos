//
//  ItemSelectionView.swift
//  Umuve
//
//  Booking wizard's Items step — seven category buttons (multi-select),
//  collapsible per-category item rows with quantity steppers, a sticky
//  footer showing truck-fill + estimated price + cu ft / lbs totals,
//  plus an optional 500-char notes field. Mirrors the web booking
//  flow's Step 3 layout.
//

import SwiftUI

struct ItemSelectionView: View {
    @EnvironmentObject var bookingData: BookingData
    @EnvironmentObject var wizardVM: BookingWizardViewModel

    @State private var expandedCategories: Set<ItemCategory> = []

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: UmuveSpacing.xlarge) {
                headerSection
                categoryGrid
                itemSectionsList
                notesSection
                pricingInfoNote
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.top, UmuveSpacing.normal)
            .padding(.bottom, UmuveSpacing.xxlarge + 120) // leave room for sticky footer
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .safeAreaInset(edge: .bottom) {
            stickyFooter
        }
        .onAppear {
            bookingData.serviceType = .junkRemoval

            // AI pre-fill: if photos were analyzed and the user hasn't
            // added items yet, seed the cart with what the model
            // detected. They can still edit/remove anything.
            if bookingData.items.isEmpty,
               let analysis = bookingData.aiAnalysis,
               !analysis.items.isEmpty {
                applyAIAnalysis(analysis)
            }

            // Auto-expand any category that has items (whether from AI
            // pre-fill or a prior trip through this step).
            for item in bookingData.items {
                expandedCategories.insert(item.category)
            }
        }
    }

    /// Map each AI-detected item to a BookingItem using the closest preset
    /// from the matched category. Falls back to the first preset when the
    /// description doesn't match any known preset name.
    private func applyAIAnalysis(_ analysis: AIPhotoAnalysis) {
        var seeded: [BookingItem] = []
        for detected in analysis.items {
            let category = detected.itemCategory()
            let presets = category.presets
            guard let preset = matchPreset(for: detected, in: presets) else { continue }
            seeded.append(BookingItem(category: category, preset: preset, quantity: max(detected.quantity, 1)))
        }
        bookingData.items = seeded
    }

    private func matchPreset(for detected: AIDetectedItem, in presets: [ItemPreset]) -> ItemPreset? {
        guard let description = detected.description?.lowercased(), !description.isEmpty else {
            return presets.first
        }
        // Best-effort: pick the preset whose name shares the most words
        // with the AI description. Falls back to the first preset.
        let descWords = Set(description.split(separator: " ").map(String.init))
        let best = presets.max { a, b in
            let aHits = a.name.lowercased().split(separator: " ").reduce(0) { $0 + (descWords.contains(String($1)) ? 1 : 0) }
            let bHits = b.name.lowercased().split(separator: " ").reduce(0) { $0 + (descWords.contains(String($1)) ? 1 : 0) }
            return aHits < bHits
        }
        return best ?? presets.first
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.small) {
            Text("What are we removing?")
                .font(UmuveTypography.h1Font)
                .foregroundColor(.umuveText)

            Text("Select categories and tell us what items you need hauled away.")
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveTextMuted)
        }
    }

    // MARK: - Category Grid (multi-select buttons)

    private var categoryGrid: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.small) {
            Text("Categories (select all that apply)")
                .font(UmuveTypography.captionFont)
                .foregroundColor(.umuveTextMuted)
                .textCase(.uppercase)
                .tracking(0.8)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: UmuveSpacing.small) {
                ForEach(ItemCategory.allCases) { category in
                    categoryButton(category)
                }
            }
        }
    }

    private func categoryButton(_ category: ItemCategory) -> some View {
        let isSelected = expandedCategories.contains(category)
        let count = bookingData.items.filter { $0.category == category }.reduce(0) { $0 + $1.quantity }

        return Button {
            HapticManager.shared.lightTap()
            toggleCategory(category)
        } label: {
            HStack(spacing: UmuveSpacing.small) {
                Image(systemName: category.systemIcon)
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(isSelected ? .white : .umuvePrimary)
                    .frame(width: 24)

                Text(category.displayName)
                    .font(UmuveTypography.bodySmallFont.weight(.semibold))
                    .foregroundColor(isSelected ? .white : .umuveText)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)

                Spacer(minLength: 0)

                if count > 0 {
                    Text("\(count)")
                        .font(UmuveTypography.smallFont.weight(.bold))
                        .foregroundColor(isSelected ? .umuvePrimary : .white)
                        .frame(width: 22, height: 22)
                        .background(Circle().fill(isSelected ? Color.white : Color.umuvePrimary))
                }
            }
            .padding(UmuveSpacing.normal)
            .frame(maxWidth: .infinity, minHeight: 64)
            .background(
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .fill(isSelected ? Color.umuvePrimary : Color.umuveWhite)
            )
            .overlay(
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .strokeBorder(isSelected ? Color.umuvePrimary : Color.umuveBorder, lineWidth: 1)
            )
            .shadow(color: .black.opacity(isSelected ? 0 : 0.04), radius: 6, x: 0, y: 2)
        }
        .buttonStyle(.plain)
    }

    private func toggleCategory(_ category: ItemCategory) {
        if expandedCategories.contains(category) {
            // Collapse — but keep already-added items so the user can come
            // back and tweak. Removing on collapse would be too punishing.
            expandedCategories.remove(category)
        } else {
            expandedCategories.insert(category)
            let alreadyHasItems = bookingData.items.contains { $0.category == category }
            if !alreadyHasItems, let firstPreset = category.presets.first {
                bookingData.items.append(BookingItem(category: category, preset: firstPreset))
            }
        }
    }

    // MARK: - Item Sections (one per expanded category)

    private var itemSectionsList: some View {
        VStack(spacing: UmuveSpacing.medium) {
            ForEach(ItemCategory.allCases.filter { expandedCategories.contains($0) }) { category in
                categorySection(category)
            }
        }
    }

    private func categorySection(_ category: ItemCategory) -> some View {
        let categoryItems = bookingData.items.filter { $0.category == category }

        return VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            HStack {
                Image(systemName: category.systemIcon)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(.umuvePrimary)
                Text(category.displayName)
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.umuveText)
                Spacer()
            }

            ForEach(categoryItems) { item in
                itemRow(category: category, item: item)
            }

            Button {
                addNewItem(in: category)
            } label: {
                HStack {
                    Image(systemName: "plus.circle.fill")
                    Text("Add another \(category.displayName.lowercased())")
                }
                .font(UmuveTypography.bodySmallFont.weight(.semibold))
                .foregroundColor(.umuvePrimary)
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuveBorder, lineWidth: 1)
        )
    }

    private func itemRow(category: ItemCategory, item: BookingItem) -> some View {
        VStack(spacing: UmuveSpacing.small) {
            HStack(spacing: UmuveSpacing.small) {
                Menu {
                    ForEach(category.presets) { preset in
                        Button(preset.name) {
                            updateItem(item, to: preset)
                        }
                    }
                } label: {
                    HStack(spacing: 4) {
                        Text(item.name)
                            .font(UmuveTypography.bodyFont.weight(.medium))
                            .foregroundColor(.umuveText)
                            .lineLimit(1)
                        Image(systemName: "chevron.up.chevron.down")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundColor(.umuveTextMuted)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, UmuveSpacing.medium)
                    .padding(.vertical, 10)
                    .background(Color.umuveSurfaceElevated)
                    .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
                }

                quantityStepper(for: item)

                Button {
                    removeItem(item)
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 22))
                        .foregroundColor(.umuveTextTertiary)
                }
            }

            HStack {
                Text("~\(Int(item.totalCuFt)) cu ft")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextMuted)
                Text("·")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextTertiary)
                Text("~\(Int(item.totalLbs)) lbs")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextMuted)
                Spacer()
            }
        }
    }

    private func quantityStepper(for item: BookingItem) -> some View {
        HStack(spacing: 0) {
            Button {
                changeQuantity(item, delta: -1)
            } label: {
                Image(systemName: "minus")
                    .font(.system(size: 14, weight: .bold))
                    .frame(width: 32, height: 32)
                    .foregroundColor(item.quantity > 1 ? .umuveText : .umuveTextTertiary)
            }
            .disabled(item.quantity <= 1)

            Text("\(item.quantity)")
                .font(UmuveTypography.bodyFont.weight(.bold))
                .foregroundColor(.umuveText)
                .frame(minWidth: 24)

            Button {
                changeQuantity(item, delta: 1)
            } label: {
                Image(systemName: "plus")
                    .font(.system(size: 14, weight: .bold))
                    .frame(width: 32, height: 32)
                    .foregroundColor(item.quantity < 20 ? .umuveText : .umuveTextTertiary)
            }
            .disabled(item.quantity >= 20)
        }
        .background(Color.umuveSurfaceElevated)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
    }

    // MARK: - Mutation helpers

    private func addNewItem(in category: ItemCategory) {
        HapticManager.shared.lightTap()
        guard let firstPreset = category.presets.first else { return }
        bookingData.items.append(BookingItem(category: category, preset: firstPreset))
    }

    private func updateItem(_ item: BookingItem, to preset: ItemPreset) {
        guard let idx = bookingData.items.firstIndex(where: { $0.id == item.id }) else { return }
        bookingData.items[idx].name = preset.name
        bookingData.items[idx].cuFtPerUnit = preset.cuFt
        bookingData.items[idx].lbsPerUnit = preset.lbs
    }

    private func changeQuantity(_ item: BookingItem, delta: Int) {
        guard let idx = bookingData.items.firstIndex(where: { $0.id == item.id }) else { return }
        let newQty = bookingData.items[idx].quantity + delta
        guard newQty >= 1, newQty <= 20 else { return }
        HapticManager.shared.lightTap()
        bookingData.items[idx].quantity = newQty
    }

    private func removeItem(_ item: BookingItem) {
        HapticManager.shared.lightTap()
        bookingData.items.removeAll { $0.id == item.id }
    }

    // MARK: - Notes

    private var notesSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.small) {
            HStack {
                Text("Additional Notes (optional)")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.umuveTextMuted)
                    .textCase(.uppercase)
                    .tracking(0.8)
                Spacer()
                Text("\(bookingData.notes.count)/500")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextTertiary)
            }

            TextField(
                "Anything else we should know? (e.g., items are on 2nd floor, narrow hallway, heavy items need 2 people…)",
                text: $bookingData.notes,
                axis: .vertical
            )
            .font(UmuveTypography.bodyFont)
            .lineLimit(3...6)
            .padding(UmuveSpacing.medium)
            .background(Color.umuveWhite)
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .strokeBorder(Color.umuveBorder, lineWidth: 1)
            )
            .onChange(of: bookingData.notes) { newValue in
                if newValue.count > 500 {
                    bookingData.notes = String(newValue.prefix(500))
                }
            }
        }
    }

    private var pricingInfoNote: some View {
        HStack(alignment: .top, spacing: UmuveSpacing.small) {
            Image(systemName: "info.circle.fill")
                .foregroundColor(.umuvePrimary)
                .padding(.top, 2)
            Text("Price based on truck space used — not by item count. Final price confirmed before we start, never higher than the high estimate.")
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(.umuveTextMuted)
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuvePrimary.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
    }

    // MARK: - Sticky Footer (truck fill + price + continue)

    private var stickyFooter: some View {
        VStack(spacing: UmuveSpacing.medium) {
            if bookingData.hasItems {
                truckFillBar
                priceTickerRow
            }

            Button {
                wizardVM.completeCurrentStep()
            } label: {
                Text(bookingData.hasItems ? "Continue" : "Add at least one item")
            }
            .buttonStyle(UmuvePrimaryButtonStyle(isEnabled: bookingData.hasItems))
            .disabled(!bookingData.hasItems)
        }
        .padding(.horizontal, UmuveSpacing.large)
        .padding(.vertical, UmuveSpacing.normal)
        .background(Color.umuveBackground.opacity(0.98))
        .overlay(
            Rectangle().fill(Color.umuveBorder).frame(height: 1),
            alignment: .top
        )
        .ignoresSafeArea(.keyboard, edges: .bottom)
    }

    private var truckFillBar: some View {
        let fillRatio = min(bookingData.totalCuFt / TruckLoadTier.maxCapacityCuFt, 1.0)
        let fillColor: Color = {
            switch fillRatio {
            case 0..<0.25: return .umuveSuccess
            case 0.25..<0.5: return .categoryYellow
            case 0.5..<0.75: return .categoryOrange
            default: return .umuveError
            }
        }()

        return VStack(spacing: 4) {
            HStack {
                Text("Estimated Truck Space")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextMuted)
                Spacer()
                Text(bookingData.currentTruckTier.label)
                    .font(UmuveTypography.smallFont.weight(.bold))
                    .foregroundColor(.umuveText)
            }

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color.umuveBorder)
                    Capsule()
                        .fill(fillColor)
                        .frame(width: geo.size.width * fillRatio)
                        .animation(.smooth, value: fillRatio)
                }
            }
            .frame(height: 8)
        }
    }

    private var priceTickerRow: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("Estimated Price")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextMuted)
                Text("$\(Int(bookingData.currentTruckTier.basePrice))")
                    .font(UmuveTypography.priceFont)
                    .foregroundColor(.umuveCTA)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text("~\(Int(bookingData.totalCuFt)) cu ft")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextMuted)
                Text("~\(Int(bookingData.totalLbs)) lbs")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextMuted)
            }
        }
    }
}

// MARK: - Preview

#Preview {
    let data = BookingData()
    data.serviceType = .junkRemoval
    return NavigationStack {
        ItemSelectionView()
            .environmentObject(data)
            .environmentObject(BookingWizardViewModel())
    }
}

//
//  ConfirmationView.swift
//  JunkOS
//
//  Booking confirmation and submission screen
//  Enhanced with success haptic and celebration animation
//  SF Symbols Reference: https://developer.apple.com/sf-symbols/
//

import SwiftUI

struct ConfirmationView: View {
    @EnvironmentObject var bookingData: BookingData
    @EnvironmentObject var authManager: AuthenticationManager
    @StateObject private var viewModel = ConfirmationViewModel()
    @State private var showConfetti = false
    @State private var showSuccessCheckmark = false

    // Customer info bound to bookingData for flow-through
    @State private var customerName = ""
    @State private var customerEmail = ""
    @State private var customerPhone = ""
    @State private var showPaymentError = false

    var body: some View {
        ZStack {
            ScrollView {
            VStack(spacing: JunkSpacing.xxlarge) {
                // Header
                ScreenHeader(
                    title: "Review Booking",
                    subtitle: "Everything look good?",
                    progress: 1.0
                )
                .staggeredEntrance(index: 0, isVisible: viewModel.elementsVisible)

                // Customer info
                customerInfoSection
                    .staggeredEntrance(index: 1, isVisible: viewModel.elementsVisible)

                // Booking summary
                bookingSummary
                    .staggeredEntrance(index: 2, isVisible: viewModel.elementsVisible)

                // LoadUp Feature #2: Don't Need to Be Home
                dontNeedToBeHomeSection
                    .staggeredEntrance(index: 3, isVisible: viewModel.elementsVisible)

                // LoadUp Feature #4: Commercial Details
                if bookingData.isCommercialBooking {
                    commercialDetailsSection
                        .staggeredEntrance(index: 4, isVisible: viewModel.elementsVisible)
                }

                // LoadUp Feature #3: Eco-Friendly Messaging
                ecoFriendlySection
                    .staggeredEntrance(index: 5, isVisible: viewModel.elementsVisible)

                // Price breakdown
                priceSection
                    .staggeredEntrance(index: 6, isVisible: viewModel.elementsVisible)

                // What's next
                whatsNextSection
                    .staggeredEntrance(index: 7, isVisible: viewModel.elementsVisible)

                Spacer()
            }
            .padding(JunkSpacing.large)
        }
            .background(Color.junkBackground.ignoresSafeArea())
            .navigationBarTitleDisplayMode(.inline)
            .safeAreaInset(edge: .bottom) {
                confirmButton
            }
            .onAppear {
                viewModel.startAnimations()
                viewModel.updatePriceBreakdown(
                    serviceTier: bookingData.serviceTier,
                    isCommercial: bookingData.isCommercialBooking
                )
                // Pre-fill from auth if available
                if let user = authManager.currentUser, user.id != "guest" {
                    customerName = user.name ?? ""
                    customerEmail = user.email ?? ""
                    customerPhone = user.phoneNumber ?? ""
                }
            }
            .alert("Booking Confirmed!", isPresented: $viewModel.showSuccess) {
                Button("OK") {
                    bookingData.bookingCompleted = true
                }
            } message: {
                Text("You'll receive a confirmation email shortly. Our team will arrive during your selected time window.")
            }
            .alert("Booking Failed", isPresented: .init(
                get: { viewModel.errorMessage != nil },
                set: { if !$0 { viewModel.errorMessage = nil } }
            )) {
                Button("OK") { viewModel.errorMessage = nil }
            } message: {
                Text(viewModel.errorMessage ?? "Please try again.")
            }

            // Confetti overlay
            if showConfetti {
                ConfettiView()
            }

            // Success checkmark overlay
            if showSuccessCheckmark {
                ZStack {
                    Color.black.opacity(0.3)
                        .ignoresSafeArea()

                    SuccessCheckmark()
                }
                .transition(.opacity)
                .onAppear {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                        withAnimation {
                            showSuccessCheckmark = false
                        }
                    }
                }
            }
        }
    }
    
    // MARK: - Customer Info Section
    private var customerInfoSection: some View {
        JunkCard {
            VStack(alignment: .leading, spacing: JunkSpacing.normal) {
                SectionTitle(icon: "person.fill", text: "Your Information")

                VStack(spacing: JunkSpacing.medium) {
                    VStack(alignment: .leading, spacing: JunkSpacing.tiny) {
                        Text("Name")
                            .font(JunkTypography.captionFont)
                            .foregroundColor(.junkTextMuted)
                        TextField("Full name", text: $customerName)
                            .font(JunkTypography.bodyFont)
                            .textContentType(.name)
                            .padding(JunkSpacing.medium)
                            .background(Color.junkBackground)
                            .clipShape(RoundedRectangle(cornerRadius: JunkRadius.sm))
                    }

                    VStack(alignment: .leading, spacing: JunkSpacing.tiny) {
                        Text("Email")
                            .font(JunkTypography.captionFont)
                            .foregroundColor(.junkTextMuted)
                        TextField("Email address", text: $customerEmail)
                            .font(JunkTypography.bodyFont)
                            .keyboardType(.emailAddress)
                            .textContentType(.emailAddress)
                            .autocapitalization(.none)
                            .padding(JunkSpacing.medium)
                            .background(Color.junkBackground)
                            .clipShape(RoundedRectangle(cornerRadius: JunkRadius.sm))
                    }

                    VStack(alignment: .leading, spacing: JunkSpacing.tiny) {
                        Text("Phone")
                            .font(JunkTypography.captionFont)
                            .foregroundColor(.junkTextMuted)
                        TextField("Phone number", text: $customerPhone)
                            .font(JunkTypography.bodyFont)
                            .keyboardType(.phonePad)
                            .textContentType(.telephoneNumber)
                            .padding(JunkSpacing.medium)
                            .background(Color.junkBackground)
                            .clipShape(RoundedRectangle(cornerRadius: JunkRadius.sm))
                    }
                }
            }
            .padding(JunkSpacing.large)
        }
    }

    // MARK: - Booking Summary
    private var bookingSummary: some View {
        JunkCard {
            VStack(alignment: .leading, spacing: JunkSpacing.normal) {
                // SF Symbol: mappin.circle.fill for location
                SectionTitle(icon: "mappin.circle.fill", text: "Location")
                Text(bookingData.address.fullAddress)
                    .font(JunkTypography.bodyFont)
                    .foregroundColor(.junkTextMuted)
                
                Divider()
                    .padding(.vertical, JunkSpacing.small)
                
                // SF Symbol: camera.fill for photos
                SectionTitle(icon: "camera.fill", text: "Photos")
                Text("\(bookingData.photos.count) photo\(bookingData.photos.count == 1 ? "" : "s") uploaded")
                    .font(JunkTypography.bodyFont)
                    .foregroundColor(.junkTextMuted)
                
                Divider()
                    .padding(.vertical, JunkSpacing.small)
                
                // SF Symbol: arrow.3.trianglepath for recycling/services
                SectionTitle(icon: "arrow.3.trianglepath", text: "Services")
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(Array(bookingData.selectedServices), id: \.self) { serviceId in
                        if let service = Service.all.first(where: { $0.id == serviceId }) {
                            Text("• \(service.name)")
                                .font(JunkTypography.bodyFont)
                                .foregroundColor(.junkTextMuted)
                        }
                    }
                }
                
                if !bookingData.serviceDetails.isEmpty {
                    Text(bookingData.serviceDetails)
                        .font(JunkTypography.bodySmallFont)
                        .foregroundColor(.junkTextMuted)
                        .italic()
                        .padding(.top, JunkSpacing.small)
                }
                
                Divider()
                    .padding(.vertical, JunkSpacing.small)
                
                // SF Symbol: calendar for date/scheduling
                SectionTitle(icon: "calendar", text: "Scheduled")
                if let date = bookingData.selectedDate,
                   let timeSlot = TimeSlot.slots.first(where: { $0.id == bookingData.selectedTimeSlot }) {
                    Text("\(date, style: .date) at \(timeSlot.time)")
                        .font(JunkTypography.bodyFont)
                        .foregroundColor(.junkTextMuted)
                }
            }
            .padding(JunkSpacing.large)
        }
    }
    
    // MARK: - LoadUp Feature #2: Don't Need to Be Home
    private var dontNeedToBeHomeSection: some View {
        JunkCard {
            VStack(alignment: .leading, spacing: JunkSpacing.normal) {
                Toggle(isOn: $bookingData.dontNeedToBeHome) {
                    HStack {
                        Image(systemName: "house.fill")
                            .foregroundColor(.junkPrimary)
                        Text("Don't Need to Be Home")
                            .font(JunkTypography.h3Font)
                            .foregroundColor(.junkText)
                    }
                }
                
                if bookingData.dontNeedToBeHome {
                    VStack(alignment: .leading, spacing: JunkSpacing.small) {
                        Text("Outdoor Placement Instructions")
                            .font(JunkTypography.bodyFont.weight(.semibold))
                            .foregroundColor(.junkText)
                        
                        TextEditor(text: $bookingData.outdoorPlacementInstructions)
                            .font(JunkTypography.bodyFont)
                            .frame(height: 80)
                            .padding(JunkSpacing.small)
                            .background(Color.junkBackground)
                            .cornerRadius(8)
                        
                        Text("Special Notes for Loaders")
                            .font(JunkTypography.bodyFont.weight(.semibold))
                            .foregroundColor(.junkText)
                            .padding(.top, JunkSpacing.small)
                        
                        TextEditor(text: $bookingData.loaderNotes)
                            .font(JunkTypography.bodyFont)
                            .frame(height: 80)
                            .padding(JunkSpacing.small)
                            .background(Color.junkBackground)
                            .cornerRadius(8)
                    }
                    .transition(.opacity)
                }
            }
            .padding(JunkSpacing.large)
        }
    }
    
    // MARK: - LoadUp Feature #4: Commercial Details
    private var commercialDetailsSection: some View {
        JunkCard {
            VStack(alignment: .leading, spacing: JunkSpacing.normal) {
                HStack {
                    Image(systemName: "building.2.fill")
                        .foregroundColor(.junkPrimary)
                    Text("Commercial Booking")
                        .font(JunkTypography.h3Font)
                        .foregroundColor(.junkText)
                }
                
                VStack(alignment: .leading, spacing: JunkSpacing.small) {
                    Text("Business Name")
                        .font(JunkTypography.bodyFont.weight(.semibold))
                        .foregroundColor(.junkText)
                    
                    TextField("Enter business name", text: $bookingData.businessName)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                }
                
                Toggle(isOn: $bookingData.isRecurringPickup) {
                    Text("Recurring Pickup")
                        .font(JunkTypography.bodyFont)
                        .foregroundColor(.junkText)
                }
                
                if bookingData.isRecurringPickup {
                    VStack(alignment: .leading, spacing: JunkSpacing.small) {
                        Text("Frequency")
                            .font(JunkTypography.bodyFont.weight(.semibold))
                            .foregroundColor(.junkText)
                        
                        Picker("Frequency", selection: $bookingData.recurringFrequency) {
                            ForEach(RecurringFrequency.allCases, id: \.self) { frequency in
                                Text(frequency.rawValue).tag(frequency)
                            }
                        }
                        .pickerStyle(SegmentedPickerStyle())
                    }
                    .transition(.opacity)
                }
                
                HStack {
                    Image(systemName: "tag.fill")
                        .foregroundColor(.junkSuccess)
                    Text("15% bulk discount applied")
                        .font(JunkTypography.bodyFont)
                        .foregroundColor(.junkSuccess)
                }
                .padding(.top, JunkSpacing.small)
            }
            .padding(JunkSpacing.large)
        }
    }
    
    // MARK: - LoadUp Feature #3: Eco-Friendly Section
    private var ecoFriendlySection: some View {
        JunkCard {
            VStack(alignment: .leading, spacing: JunkSpacing.normal) {
                HStack {
                    Image(systemName: "leaf.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.junkSuccess)
                    Text("Responsible Disposal")
                        .font(JunkTypography.h2Font)
                        .foregroundColor(.junkText)
                }
                
                VStack(alignment: .leading, spacing: JunkSpacing.small) {
                    ResponsibleDisposalItem(
                        icon: "arrow.3.trianglepath",
                        title: "Recycle",
                        description: "Items sent to local recycling facilities"
                    )
                    
                    ResponsibleDisposalItem(
                        icon: "heart.fill",
                        title: "Donate",
                        description: "Usable items donated to local charities"
                    )
                    
                    ResponsibleDisposalItem(
                        icon: "building.2.fill",
                        title: "Dispose",
                        description: "Remaining items properly disposed at certified facilities"
                    )
                }
                
                Text("We aim to divert 60% of items from landfills through our eco-friendly practices.")
                    .font(JunkTypography.bodySmallFont)
                    .foregroundColor(.junkTextMuted)
                    .italic()
                    .padding(.top, JunkSpacing.small)
            }
            .padding(JunkSpacing.large)
        }
        .background(Color.junkSuccess.opacity(0.05))
    }
    
    // MARK: - Price Section
    private var priceSection: some View {
        JunkCard {
            VStack(spacing: JunkSpacing.normal) {
                HStack {
                    Text("Base Service")
                        .font(JunkTypography.bodyFont)
                        .foregroundColor(.junkText)
                    Spacer()
                    Text("$\(viewModel.formatPrice(viewModel.priceBreakdown.basePrice))")
                        .font(JunkTypography.bodyFont)
                        .foregroundColor(.junkText)
                }
                
                HStack {
                    Text("Items Charge")
                        .font(JunkTypography.bodyFont)
                        .foregroundColor(.junkText)
                    Spacer()
                    Text("$\(viewModel.formatPrice(viewModel.priceBreakdown.itemsCharge))")
                        .font(JunkTypography.bodyFont)
                        .foregroundColor(.junkText)
                }
                
                HStack {
                    Text("Disposal Fee")
                        .font(JunkTypography.bodyFont)
                        .foregroundColor(.junkText)
                    Spacer()
                    Text("$\(viewModel.formatPrice(viewModel.priceBreakdown.disposalFee))")
                        .font(JunkTypography.bodyFont)
                        .foregroundColor(.junkText)
                }
                
                // LoadUp Feature #1: Service Tier Discount
                if viewModel.priceBreakdown.tierDiscount > 0 {
                    HStack {
                        Text("\(bookingData.serviceTier.rawValue) Discount")
                            .font(JunkTypography.bodyFont)
                            .foregroundColor(.junkSuccess)
                        Spacer()
                        Text("-$\(viewModel.formatPrice(viewModel.priceBreakdown.tierDiscount))")
                            .font(JunkTypography.bodyFont)
                            .foregroundColor(.junkSuccess)
                    }
                }
                
                // LoadUp Feature #4: Commercial Discount
                if viewModel.priceBreakdown.commercialDiscount > 0 {
                    HStack {
                        Text("Commercial Discount")
                            .font(JunkTypography.bodyFont)
                            .foregroundColor(.junkSuccess)
                        Spacer()
                        Text("-$\(viewModel.formatPrice(viewModel.priceBreakdown.commercialDiscount))")
                            .font(JunkTypography.bodyFont)
                            .foregroundColor(.junkSuccess)
                    }
                }
                
                Divider()
                    .padding(.vertical, JunkSpacing.small)
                
                HStack {
                    Text("Estimated Total")
                        .font(JunkTypography.h3Font)
                        .foregroundColor(.junkText)
                    Spacer()
                    Text("$\(viewModel.formatPrice(viewModel.priceBreakdown.total))")
                        .font(JunkTypography.h2Font)
                        .foregroundColor(.junkCTA)
                }
                
                Text("*Final price determined after on-site inspection")
                    .font(JunkTypography.bodySmallFont)
                    .foregroundColor(.junkTextMuted)
                    .multilineTextAlignment(.center)
                    .padding(.top, JunkSpacing.small)
            }
            .padding(JunkSpacing.large)
        }
    }
    
    // MARK: - What's Next Section
    private var whatsNextSection: some View {
        JunkCard {
            VStack(alignment: .leading, spacing: JunkSpacing.normal) {
                Text("What's Next?")
                    .font(JunkTypography.h2Font)
                    .foregroundColor(.junkText)
                
                NextStep(number: 1, text: "You'll receive a confirmation email")
                NextStep(number: 2, text: "Our team will text you 30 min before arrival")
                NextStep(number: 3, text: "We load, haul, and dispose responsibly")
            }
            .padding(JunkSpacing.large)
        }
    }
    
    // MARK: - Confirm Button
    private var isFormValid: Bool {
        !customerName.trimmingCharacters(in: .whitespaces).isEmpty &&
        !customerEmail.trimmingCharacters(in: .whitespaces).isEmpty &&
        !customerPhone.trimmingCharacters(in: .whitespaces).isEmpty
    }

    private var confirmButton: some View {
        NavigationLink {
            PaymentView(
                priceBreakdown: viewModel.priceBreakdown,
                onPaymentSuccess: {
                    submitBookingAfterPayment()
                }
            )
            .environmentObject(bookingData)
        } label: {
            Text("Continue to Payment")
        }
        .buttonStyle(JunkPrimaryButtonStyle(isEnabled: isFormValid))
        .padding(JunkSpacing.large)
        .background(Color.junkBackground)
        .disabled(!isFormValid)
        .simultaneousGesture(TapGesture().onEnded {
            // Sync customer info to bookingData before navigating
            bookingData.customerName = customerName.trimmingCharacters(in: .whitespaces)
            bookingData.customerEmail = customerEmail.trimmingCharacters(in: .whitespaces)
            bookingData.customerPhone = customerPhone.trimmingCharacters(in: .whitespaces)
        })
    }

    // MARK: - Submit Booking after payment
    private func submitBookingAfterPayment() {
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        let dateString = bookingData.selectedDate.map { dateFormatter.string(from: $0) } ?? ""
        let timeSlot = bookingData.selectedTimeSlot ?? ""
        let scheduledDateTime = "\(dateString) \(timeSlot)"

        var notes: String? = nil
        if !bookingData.serviceDetails.isEmpty || !bookingData.loaderNotes.isEmpty {
            notes = [bookingData.serviceDetails, bookingData.loaderNotes]
                .filter { !$0.isEmpty }
                .joined(separator: "\n")
        }

        Task {
            await viewModel.submitBooking(
                address: bookingData.address,
                serviceIds: Array(bookingData.selectedServices),
                photos: bookingData.photos,
                scheduledDateTime: scheduledDateTime,
                customerName: bookingData.customerName,
                customerEmail: bookingData.customerEmail,
                customerPhone: bookingData.customerPhone,
                notes: notes
            ) { success in
                if success {
                    bookingData.bookingCompleted = true
                }
            }
        }
    }
}

// MARK: - Supporting Views

struct SectionTitle: View {
    let icon: String // SF Symbol name
    let text: String
    
    var body: some View {
        HStack(spacing: JunkSpacing.small) {
            // Using SF Symbol instead of emoji
            // https://developer.apple.com/design/human-interface-guidelines/sf-symbols
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(.junkPrimary)
            Text(text)
                .font(JunkTypography.h3Font)
                .foregroundColor(.junkText)
        }
    }
}

struct NextStep: View {
    let number: Int
    let text: String
    
    var body: some View {
        HStack(spacing: JunkSpacing.medium) {
            ZStack {
                Circle()
                    .fill(Color.junkPrimary.opacity(0.1))
                    .frame(width: 32, height: 32)
                
                Text("\(number)")
                    .font(JunkTypography.bodyFont.weight(.bold))
                    .foregroundColor(.junkPrimary)
            }
            
            Text(text)
                .font(JunkTypography.bodyFont)
                .foregroundColor(.junkText)
            
            Spacer()
        }
    }
}

struct ResponsibleDisposalItem: View {
    let icon: String
    let title: String
    let description: String

    var body: some View {
        HStack(spacing: JunkSpacing.normal) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(.junkSuccess)
                .frame(width: 30)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(JunkTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.junkText)
                
                Text(description)
                    .font(JunkTypography.bodySmallFont)
                    .foregroundColor(.junkTextMuted)
            }
            
            Spacer()
        }
    }
}

// MARK: - Preview
struct ConfirmationView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            ConfirmationView()
                .environmentObject({
                    let data = BookingData()
                    data.address.street = "123 Main St"
                    data.address.city = "Tampa"
                    data.address.zipCode = "33602"
                    data.selectedServices = ["furniture", "appliances"]
                    data.selectedDate = Date()
                    data.selectedTimeSlot = "morning"
                    return data
                }())
                .environmentObject(AuthenticationManager())
        }
    }
}

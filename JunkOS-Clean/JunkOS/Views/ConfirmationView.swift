//
//  ConfirmationView.swift
//  Umuve
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
            VStack(spacing: UmuveSpacing.xxlarge) {
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
            .padding(UmuveSpacing.large)
        }
            .background(Color.umuveBackground.ignoresSafeArea())
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
        UmuveCard {
            VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
                SectionTitle(icon: "person.fill", text: "Your Information")

                VStack(spacing: UmuveSpacing.medium) {
                    VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                        Text("Name")
                            .font(UmuveTypography.captionFont)
                            .foregroundColor(.umuveTextMuted)
                        TextField("Full name", text: $customerName)
                            .font(UmuveTypography.bodyFont)
                            .textContentType(.name)
                            .padding(UmuveSpacing.medium)
                            .background(Color.umuveBackground)
                            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
                    }

                    VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                        Text("Email")
                            .font(UmuveTypography.captionFont)
                            .foregroundColor(.umuveTextMuted)
                        TextField("Email address", text: $customerEmail)
                            .font(UmuveTypography.bodyFont)
                            .keyboardType(.emailAddress)
                            .textContentType(.emailAddress)
                            .autocapitalization(.none)
                            .padding(UmuveSpacing.medium)
                            .background(Color.umuveBackground)
                            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
                    }

                    VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                        Text("Phone")
                            .font(UmuveTypography.captionFont)
                            .foregroundColor(.umuveTextMuted)
                        TextField("Phone number", text: $customerPhone)
                            .font(UmuveTypography.bodyFont)
                            .keyboardType(.phonePad)
                            .textContentType(.telephoneNumber)
                            .padding(UmuveSpacing.medium)
                            .background(Color.umuveBackground)
                            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
                    }
                }
            }
            .padding(UmuveSpacing.large)
        }
    }

    // MARK: - Booking Summary
    private var bookingSummary: some View {
        UmuveCard {
            VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
                // SF Symbol: mappin.circle.fill for location
                SectionTitle(icon: "mappin.circle.fill", text: "Location")
                Text(bookingData.address.fullAddress)
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
                
                Divider()
                    .padding(.vertical, UmuveSpacing.small)
                
                // SF Symbol: camera.fill for photos
                SectionTitle(icon: "camera.fill", text: "Photos")
                Text("\(bookingData.photos.count) photo\(bookingData.photos.count == 1 ? "" : "s") uploaded")
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
                
                Divider()
                    .padding(.vertical, UmuveSpacing.small)
                
                // SF Symbol: arrow.3.trianglepath for recycling/services
                SectionTitle(icon: "arrow.3.trianglepath", text: "Services")
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(Array(bookingData.selectedServices), id: \.self) { serviceId in
                        if let service = Service.all.first(where: { $0.id == serviceId }) {
                            Text("• \(service.name)")
                                .font(UmuveTypography.bodyFont)
                                .foregroundColor(.umuveTextMuted)
                        }
                    }
                }
                
                if !bookingData.serviceDetails.isEmpty {
                    Text(bookingData.serviceDetails)
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveTextMuted)
                        .italic()
                        .padding(.top, UmuveSpacing.small)
                }
                
                Divider()
                    .padding(.vertical, UmuveSpacing.small)
                
                // SF Symbol: calendar for date/scheduling
                SectionTitle(icon: "calendar", text: "Scheduled")
                if let date = bookingData.selectedDate,
                   let timeSlot = TimeSlot.slots.first(where: { $0.id == bookingData.selectedTimeSlot }) {
                    Text("\(date, style: .date) at \(timeSlot.time)")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)
                }
            }
            .padding(UmuveSpacing.large)
        }
    }
    
    // MARK: - LoadUp Feature #2: Don't Need to Be Home
    private var dontNeedToBeHomeSection: some View {
        UmuveCard {
            VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
                Toggle(isOn: $bookingData.dontNeedToBeHome) {
                    HStack {
                        Image(systemName: "house.fill")
                            .foregroundColor(.umuvePrimary)
                        Text("Don't Need to Be Home")
                            .font(UmuveTypography.h3Font)
                            .foregroundColor(.umuveText)
                    }
                }
                
                if bookingData.dontNeedToBeHome {
                    VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                        Text("Outdoor Placement Instructions")
                            .font(UmuveTypography.bodyFont.weight(.semibold))
                            .foregroundColor(.umuveText)
                        
                        TextEditor(text: $bookingData.outdoorPlacementInstructions)
                            .font(UmuveTypography.bodyFont)
                            .frame(height: 80)
                            .padding(UmuveSpacing.small)
                            .background(Color.umuveBackground)
                            .cornerRadius(8)
                        
                        Text("Special Notes for Loaders")
                            .font(UmuveTypography.bodyFont.weight(.semibold))
                            .foregroundColor(.umuveText)
                            .padding(.top, UmuveSpacing.small)
                        
                        TextEditor(text: $bookingData.loaderNotes)
                            .font(UmuveTypography.bodyFont)
                            .frame(height: 80)
                            .padding(UmuveSpacing.small)
                            .background(Color.umuveBackground)
                            .cornerRadius(8)
                    }
                    .transition(.opacity)
                }
            }
            .padding(UmuveSpacing.large)
        }
    }
    
    // MARK: - LoadUp Feature #4: Commercial Details
    private var commercialDetailsSection: some View {
        UmuveCard {
            VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
                HStack {
                    Image(systemName: "building.2.fill")
                        .foregroundColor(.umuvePrimary)
                    Text("Commercial Booking")
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)
                }
                
                VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                    Text("Business Name")
                        .font(UmuveTypography.bodyFont.weight(.semibold))
                        .foregroundColor(.umuveText)
                    
                    TextField("Enter business name", text: $bookingData.businessName)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                }
                
                Toggle(isOn: $bookingData.isRecurringPickup) {
                    Text("Recurring Pickup")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveText)
                }
                
                if bookingData.isRecurringPickup {
                    VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                        Text("Frequency")
                            .font(UmuveTypography.bodyFont.weight(.semibold))
                            .foregroundColor(.umuveText)
                        
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
                        .foregroundColor(.umuveSuccess)
                    Text("15% bulk discount applied")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveSuccess)
                }
                .padding(.top, UmuveSpacing.small)
            }
            .padding(UmuveSpacing.large)
        }
    }
    
    // MARK: - LoadUp Feature #3: Eco-Friendly Section
    private var ecoFriendlySection: some View {
        UmuveCard {
            VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
                HStack {
                    Image(systemName: "leaf.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.umuveSuccess)
                    Text("Responsible Disposal")
                        .font(UmuveTypography.h2Font)
                        .foregroundColor(.umuveText)
                }
                
                VStack(alignment: .leading, spacing: UmuveSpacing.small) {
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
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
                    .italic()
                    .padding(.top, UmuveSpacing.small)
            }
            .padding(UmuveSpacing.large)
        }
        .background(Color.umuveSuccess.opacity(0.05))
    }
    
    // MARK: - Price Section
    private var priceSection: some View {
        UmuveCard {
            VStack(spacing: UmuveSpacing.normal) {
                HStack {
                    Text("Base Service")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveText)
                    Spacer()
                    Text("$\(viewModel.formatPrice(viewModel.priceBreakdown.basePrice))")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveText)
                }
                
                HStack {
                    Text("Items Charge")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveText)
                    Spacer()
                    Text("$\(viewModel.formatPrice(viewModel.priceBreakdown.itemsCharge))")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveText)
                }
                
                HStack {
                    Text("Disposal Fee")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveText)
                    Spacer()
                    Text("$\(viewModel.formatPrice(viewModel.priceBreakdown.disposalFee))")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveText)
                }
                
                // LoadUp Feature #1: Service Tier Discount
                if viewModel.priceBreakdown.tierDiscount > 0 {
                    HStack {
                        Text("\(bookingData.serviceTier.rawValue) Discount")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveSuccess)
                        Spacer()
                        Text("-$\(viewModel.formatPrice(viewModel.priceBreakdown.tierDiscount))")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveSuccess)
                    }
                }
                
                // LoadUp Feature #4: Commercial Discount
                if viewModel.priceBreakdown.commercialDiscount > 0 {
                    HStack {
                        Text("Commercial Discount")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveSuccess)
                        Spacer()
                        Text("-$\(viewModel.formatPrice(viewModel.priceBreakdown.commercialDiscount))")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveSuccess)
                    }
                }
                
                Divider()
                    .padding(.vertical, UmuveSpacing.small)
                
                HStack {
                    Text("Estimated Total")
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)
                    Spacer()
                    Text("$\(viewModel.formatPrice(viewModel.priceBreakdown.total))")
                        .font(UmuveTypography.h2Font)
                        .foregroundColor(.umuveCTA)
                }
                
                Text("*Final price determined after on-site inspection")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
                    .multilineTextAlignment(.center)
                    .padding(.top, UmuveSpacing.small)
            }
            .padding(UmuveSpacing.large)
        }
    }
    
    // MARK: - What's Next Section
    private var whatsNextSection: some View {
        UmuveCard {
            VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
                Text("What's Next?")
                    .font(UmuveTypography.h2Font)
                    .foregroundColor(.umuveText)
                
                NextStep(number: 1, text: "You'll receive a confirmation email")
                NextStep(number: 2, text: "Our team will text you 30 min before arrival")
                NextStep(number: 3, text: "We load, haul, and dispose responsibly")
            }
            .padding(UmuveSpacing.large)
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
        .buttonStyle(UmuvePrimaryButtonStyle(isEnabled: isFormValid))
        .padding(UmuveSpacing.large)
        .background(Color.umuveBackground)
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

        // Load stored referral code if bookingData doesn't already have one
        let referral = bookingData.referralCode.isEmpty
            ? UserDefaults.standard.string(forKey: "appliedReferralCode")
            : bookingData.referralCode

        Task {
            await viewModel.submitBooking(
                address: bookingData.address,
                serviceIds: Array(bookingData.selectedServices),
                photos: bookingData.photos,
                scheduledDateTime: scheduledDateTime,
                customerName: bookingData.customerName,
                customerEmail: bookingData.customerEmail,
                customerPhone: bookingData.customerPhone,
                notes: notes,
                referralCode: referral
            ) { success in
                // BookingSuccessView handles completion when user taps "Done"
            }
        }
    }
}

// MARK: - Supporting Views

struct SectionTitle: View {
    let icon: String // SF Symbol name
    let text: String
    
    var body: some View {
        HStack(spacing: UmuveSpacing.small) {
            // Using SF Symbol instead of emoji
            // https://developer.apple.com/design/human-interface-guidelines/sf-symbols
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(.umuvePrimary)
            Text(text)
                .font(UmuveTypography.h3Font)
                .foregroundColor(.umuveText)
        }
    }
}

struct NextStep: View {
    let number: Int
    let text: String
    
    var body: some View {
        HStack(spacing: UmuveSpacing.medium) {
            ZStack {
                Circle()
                    .fill(Color.umuvePrimary.opacity(0.1))
                    .frame(width: 32, height: 32)
                
                Text("\(number)")
                    .font(UmuveTypography.bodyFont.weight(.bold))
                    .foregroundColor(.umuvePrimary)
            }
            
            Text(text)
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveText)
            
            Spacer()
        }
    }
}

struct ResponsibleDisposalItem: View {
    let icon: String
    let title: String
    let description: String

    var body: some View {
        HStack(spacing: UmuveSpacing.normal) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(.umuveSuccess)
                .frame(width: 30)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)
                
                Text(description)
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
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

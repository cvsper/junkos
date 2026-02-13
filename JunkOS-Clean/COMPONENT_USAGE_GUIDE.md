# Component Usage Guide

Quick reference for using the new UI/UX components in Umuve.

---

## 🎨 Empty States

### Generic Empty State
```swift
EmptyStateView(
    icon: "photo.on.rectangle.angled",
    title: "No Items",
    subtitle: "Add items to get started",
    actionTitle: "Add Item",
    action: {
        // Handle action
    }
)
```

### Pre-built Empty States
```swift
// Photo upload
PhotoUploadEmptyState {
    // Handle tap
}

// Service selection
ServiceSelectionEmptyState()

// Date/time picker
DateTimeEmptyState()
```

---

## ⏳ Loading States

### Skeleton Loaders
```swift
// Card placeholder
SkeletonCard(height: 120, cornerRadius: 16)

// Text placeholder
SkeletonText(width: 150, height: 16)

// Service card placeholder
SkeletonServiceCard()
```

### Loading Spinner
```swift
// Branded spinner
JunkLoadingSpinner()

// Full screen loading
LoadingView(message: "Loading services...")
```

### Shimmer Effect
```swift
// Add shimmer to any view
MyView()
    .shimmer()
```

---

## ❌ Error Handling

### Error View
```swift
ErrorView(
    error: .network,
    retryAction: {
        // Retry logic
    }
)

// Error types:
// .network
// .validation("Custom message")
// .serverError
// .timeout
// .unknown
```

### Shake Animation
```swift
@State private var shakeTrigger = 0

TextField("Email", text: $email)
    .shake(trigger: shakeTrigger)
    .onChange(of: email) { newValue in
        if !isValid {
            shakeTrigger += 1
        }
    }
```

### Inline Validation
```swift
InlineError(message: "Email is valid", isValid: true)
InlineError(message: "Invalid email", isValid: false)

// Validation icon
ValidationIcon(isValid: true, show: true)
```

### Network Error Banner
```swift
NetworkErrorBanner {
    // Retry action
}
```

---

## ✨ Animations

### Confetti
```swift
@State private var showConfetti = false

ZStack {
    // Your content
    
    if showConfetti {
        ConfettiView()
    }
}
```

### Success Checkmark
```swift
@State private var showSuccess = false

if showSuccess {
    SuccessCheckmark()
}
```

### Pulse Animation
```swift
Text("Pulsing")
    .pulse()
```

### Bounce Animation
```swift
@State private var bounceTrigger = 0

MyView()
    .bounce(trigger: bounceTrigger)
```

---

## 💰 Progressive Disclosure

### Live Price Estimate
```swift
LivePriceEstimate(
    services: selectedServices,
    photoCount: photos.count
)
```

### Booking Summary
```swift
BookingSummaryPreview(
    address: bookingData.address.fullAddress,
    services: bookingData.selectedServices,
    date: bookingData.selectedDate,
    timeSlot: bookingData.selectedTimeSlot,
    photoCount: bookingData.photos.count
)
```

---

## 🌟 Trust & Social Proof

### Reviews Section
```swift
// Shows 3 reviews by default
ReviewsSection()

// Custom reviews
ReviewsSection(reviews: myReviews)
```

### Individual Review Card
```swift
ReviewCard(review: CustomerReview(
    name: "John D.",
    rating: 5,
    comment: "Great service!",
    date: "1 week ago",
    location: "Miami, FL"
))
```

### Trust Badges
```swift
// Scrollable bar with all badges
TrustBadgesBar()

// Individual badge
TrustBadge(
    icon: "shield.checkered",
    text: "Licensed & Insured",
    color: .junkCTA
)
```

### Live Bookings Counter
```swift
LiveBookingsCounter()
```

---

## 🎓 Onboarding

### Show Onboarding
```swift
@StateObject private var onboardingManager = OnboardingManager()
@State private var showOnboarding = false

.onAppear {
    if !onboardingManager.hasCompletedOnboarding {
        showOnboarding = true
    }
}
.sheet(isPresented: $showOnboarding) {
    OnboardingView()
}
```

### Permission Pre-Prompt
```swift
PermissionPrePromptView(
    icon: "location.fill",
    title: "Location Access",
    subtitle: "We need your location for service",
    reason: "Helps us match you with the nearest team",
    allowAction: {
        // Request permission
    },
    denyAction: {
        // Handle denial
    }
)
```

---

## ♿️ Accessibility

### Haptic Feedback
```swift
Button("Tap me") {
    // Action
}
.hapticFeedback(.medium)

// Styles: .light, .medium, .heavy, .selection, .success, .warning, .error
```

### Staggered Entrance
```swift
@State private var isVisible = false

VStack {
    Text("First")
        .staggeredEntrance(index: 0, isVisible: isVisible)
    Text("Second")
        .staggeredEntrance(index: 1, isVisible: isVisible)
    Text("Third")
        .staggeredEntrance(index: 2, isVisible: isVisible)
}
.onAppear {
    isVisible = true
}
```

### Accessible Button
```swift
AccessibleButton(
    action: { /* action */ },
    accessibilityLabel: "Submit form",
    accessibilityHint: "Double tap to submit"
) {
    Text("Submit")
}
```

### Environment Support
```swift
@Environment(\.accessibilityReduceMotion) var reduceMotion
@Environment(\.colorSchemeContrast) var contrast
@Environment(\.dynamicTypeSize) var dynamicTypeSize

// Use in view logic
if !reduceMotion {
    // Show animation
}
```

---

## 🎯 Common Patterns

### Loading Flow
```swift
@State private var isLoading = false

if isLoading {
    VStack {
        SkeletonCard()
        SkeletonCard()
        SkeletonCard()
    }
} else {
    // Real content
}
```

### Error + Retry Flow
```swift
@State private var error: JunkError?

if let error = error {
    ErrorView(error: error) {
        self.error = nil
        retry()
    }
} else {
    // Content
}
```

### Empty → Loading → Content Flow
```swift
@State private var items: [Item] = []
@State private var isLoading = false

Group {
    if items.isEmpty && !isLoading {
        EmptyStateView(
            icon: "tray",
            title: "No items",
            subtitle: "Add some items to get started"
        )
    } else if isLoading {
        LoadingView(message: "Loading items...")
    } else {
        ItemList(items: items)
    }
}
```

### Success Celebration Flow
```swift
@State private var showConfetti = false
@State private var showSuccess = false

func onComplete() {
    withAnimation {
        showSuccess = true
        showConfetti = true
    }
    
    HapticManager.shared.success()
    
    DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
        withAnimation {
            showSuccess = false
        }
    }
}
```

---

## 🔧 Best Practices

### 1. Always Support Reduce Motion
```swift
@Environment(\.accessibilityReduceMotion) var reduceMotion

if reduceMotion {
    // Instant state change
    isVisible = true
} else {
    // Animated state change
    withAnimation {
        isVisible = true
    }
}
```

### 2. Add Accessibility Labels
```swift
Button(action: {}) {
    Image(systemName: "trash")
}
.accessibilityLabel("Delete item")
.accessibilityHint("Double tap to remove this item")
```

### 3. Use Haptics for Feedback
```swift
Button("Delete") {
    HapticManager.shared.heavyTap()
    delete()
}
```

### 4. Show Progress for Long Operations
```swift
@State private var isSubmitting = false

Button(action: submit) {
    HStack {
        if isSubmitting {
            ProgressView()
        }
        Text(isSubmitting ? "Submitting..." : "Submit")
    }
}
.disabled(isSubmitting)
```

### 5. Provide Empty States
Every list/collection should have an empty state:
```swift
if items.isEmpty {
    EmptyStateView(...)
} else {
    List(items) { ... }
}
```

---

## 📱 Testing Components

### Test Empty States
1. Launch with no data
2. Verify empty state appears
3. Add data
4. Verify content replaces empty state

### Test Loading States
1. Add artificial delay
2. Verify skeletons appear
3. Verify smooth transition to content

### Test Error States
1. Simulate network error
2. Verify error view appears
3. Tap retry
4. Verify retry works

### Test Animations
1. Enable Reduce Motion in Settings
2. Verify animations are disabled
3. Verify functionality still works

### Test Accessibility
1. Enable VoiceOver
2. Navigate through all screens
3. Verify labels are descriptive
4. Verify hints are helpful

---

## 🎨 Customization

### Custom Colors
All components use `Color.junkPrimary`, `Color.junkCTA`, etc. from `DesignSystem.swift`.

### Custom Spacing
All components use `JunkSpacing` constants.

### Custom Typography
All components use `JunkTypography` fonts.

### Custom Haptics
Use `HapticManager.shared` methods throughout.

---

**Quick Tip**: Command+Click on any component in Xcode to see its definition and available parameters!

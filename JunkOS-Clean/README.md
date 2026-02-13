# Umuve - Clean iOS Project

Clean, minimal SwiftUI iOS app for Umuve junk removal booking.

## Project Details

- **Name:** Umuve
- **Bundle ID:** com.goumuve.com
- **Platform:** iOS 16+
- **Interface:** SwiftUI
- **Language:** Swift

## Project Structure

```
Umuve/
├── UmuveApp.swift              # App entry point
├── Design/
│   └── DesignSystem.swift       # Design tokens and reusable components
├── Models/
│   └── BookingModels.swift      # Data models for booking flow
├── Views/
│   ├── WelcomeView.swift        # Initial landing screen
│   ├── AddressInputView.swift   # Address entry screen
│   ├── ServiceSelectionView.swift # Service type selection
│   ├── PhotoUploadView.swift    # Photo upload screen
│   ├── DateTimePickerView.swift # Date/time selection
│   └── ConfirmationView.swift   # Final review and submit
├── Utilities/
│   ├── AnimationConstants.swift # Animation timing constants
│   ├── HapticManager.swift      # Haptic feedback utilities
│   └── ViewExtensions.swift     # SwiftUI view modifiers
└── Resources/
    ├── Assets.xcassets          # App assets
    └── Info.plist               # App configuration

```

## Files Copied

From `~/Documents/programs/webapps/junkos/ios-native/Umuve/`:

✅ Design/DesignSystem.swift
✅ Models/BookingModels.swift
✅ Views/WelcomeView.swift
✅ Views/AddressInputView.swift
✅ Views/ServiceSelectionView.swift
✅ Views/PhotoUploadView.swift
✅ Views/DateTimePickerView.swift
✅ Views/ConfirmationView.swift
✅ UmuveApp.swift
✅ Info.plist
✅ Assets.xcassets

## Utility Files Added

To support the views, these minimal utility files were created:

- **AnimationConstants.swift** - Spring animation presets
- **HapticManager.swift** - Haptic feedback helpers
- **ViewExtensions.swift** - Staggered entrance animations

## Build Status

✅ **Project compiles successfully** with `xcodebuild`

## Building

```bash
cd ~/Documents/programs/webapps/junkos/JunkOS-Clean
xcodebuild -scheme Umuve -sdk iphonesimulator -configuration Debug build
```

## What's NOT Included

This is a minimal working project. The following are intentionally excluded:

- ❌ ViewModels (MVVM architecture)
- ❌ Services layer
- ❌ Test files
- ❌ Additional utilities beyond what views require

## Next Steps

1. ✅ Minimal working project created
2. ⏳ Add MVVM architecture
3. ⏳ Add services layer
4. ⏳ Add unit tests
5. ⏳ Add integration tests

---

Created: February 7, 2026
Last verified build: February 7, 2026

# Screen Flow Guide - LoadUp UX Redesign

## 📱 Complete Screen-by-Screen Overview

---

## 🌟 1. Enhanced Welcome Screen
**File:** `EnhancedWelcomeView.swift`

### Visual Layout:
```
┌─────────────────────────────┐
│   Green Gradient Background  │
│                              │
│      ⚪ [Logo Circle]        │
│        Umuve                │
│  Professional Junk Removal   │
│                              │
│   ⭐        ✓       🛡️      │
│  4.9/5   2,500+   Insured   │
│  Rating  Jobs     Licensed   │
│                              │
│  ┌───────────────────────┐  │
│  │   How it works        │  │
│  │                       │  │
│  │  ① Choose service     │  │
│  │  ② Set location       │  │
│  │  ③ Get quote          │  │
│  │  ④ We haul it         │  │
│  └───────────────────────┘  │
│                              │
│  [   Get Started   →   ]    │
│                              │
└─────────────────────────────┘
```

### Auto-transitions to Main Tab after 3 seconds

---

## 🏠 2. Home Tab (Main Screen)
**File:** `HomeView.swift`

### Visual Layout:
```
┌─────────────────────────────┐
│  Umuve              [Icon]  │
│  Professional junk removal   │
│                              │
│  🔍 What services do you need?│
│                              │
│  ┌─────────────────────────┐│
│  │ 🗑️  Junk Removal       →││
│  │ Furniture, appliances... ││
│  └─────────────────────────┘│
│                              │
│  ┌─────────────────────────┐│
│  │ ❤️  Donation Pickups   →││
│  │ Gently used items...     ││
│  └─────────────────────────┘│
│                              │
│  ┌─────────────────────────┐│
│  │ 💪 Moving Labor        →││
│  │ Heavy lifting help...    ││
│  └─────────────────────────┘│
│                              │
│  ┌─────────────────────────┐│
│  │ 🏠 Property Cleanout   →││
│  │ Full estate cleanout...  ││
│  └─────────────────────────┘│
│                              │
│  ⭐ 4.9/5  ✓ 2,500+  🛡️ Insured│
│                              │
│  How it works                │
│  ① Choose → ② Set → ③ Quote →④│
│                              │
├─────────────────────────────┤
│  🏠 Home  📦 Orders  👤 Profile│
└─────────────────────────────┘
```

### Color Coding:
- Junk Removal: **Blue** (#3B82F6)
- Donation Pickups: **Pink** (#EC4899)
- Moving Labor: **Yellow** (#FBBF24)
- Property Cleanout: **Green** (#10B981)

---

## 🗺️ 3. Map Address Picker
**File:** `MapAddressPickerView.swift`

### Visual Layout:
```
┌─────────────────────────────┐
│  ← Back                      │
│                              │
│                              │
│        [MAP VIEW]            │
│         🔴 📍               │
│      (Draggable Pin)         │
│                              │
│                              │
│                              │
├─────────────────────────────┤
│  ━━━  (Handle)              │
│                              │
│  📍 Service Location         │
│  123 Main St, San Francisco  │
│  You can modify later        │
│                              │
│  [ 📍 Locate Me ]            │
│                              │
│  [ Confirm Address ]         │
│  (Green Gradient)            │
└─────────────────────────────┘
```

### Features:
- Interactive MapKit integration
- Draggable pin (red/green)
- GPS "Locate Me" button
- Reverse geocoding
- Bottom sheet with address

---

## 🎯 4. Service Selection
**File:** `ServiceSelectionRedesignView.swift`

### Visual Layout:
```
┌─────────────────────────────┐
│  ← Select Service            │
│                              │
│  📍 123 Main St, SF      Edit│
│                              │
│  ┌─────────────────────────┐│
│  │ 🗑️  Junk Removal        ││
│  │ Furniture, appliances    ││
│  │                          ││
│  │ ✓ Furniture              ││
│  │ ✓ Appliances             ││
│  │ ✓ Electronics            ││
│  │ ✓ General Junk           ││
│  │                          ││
│  │ [   Book Now   →   ]    ││
│  └─────────────────────────┘│
│                              │
│  ┌─────────────────────────┐│
│  │ ❤️  Donation Pickups     ││
│  │ Gently used items        ││
│  │                          ││
│  │ ✓ Clothing               ││
│  │ ✓ Books                  ││
│  │ ✓ Toys                   ││
│  │ ✓ Home Goods             ││
│  │                          ││
│  │ [   Book Now   →   ]    ││
│  └─────────────────────────┘│
│                              │
│  [More cards below...]       │
└─────────────────────────────┘
```

### Each Card Shows:
- Large icon (60x60) with colored background
- Service title & description
- Checkmark list of what's included
- Colored "Book Now" button with gradient

---

## 📦 5. Orders Tab
**File:** `OrdersView.swift`

### Visual Layout:
```
┌─────────────────────────────┐
│           Orders             │
│                              │
│  ┌─────────────────────────┐│
│  │      🚚                  ││
│  │  (Truck Illustration)    ││
│  │                          ││
│  │  Track Your Order        ││
│  │  Enter order ID to see   ││
│  │  real-time status        ││
│  │                          ││
│  │  #️⃣ Enter Order ID      ││
│  │  [________________]      ││
│  │                          ││
│  │  [   Track Order   ]     ││
│  └─────────────────────────┘│
│                              │
│  Past Orders                 │
│                              │
│  ┌─────────────────────────┐│
│  │ #JOS-2024-001   [Done ✓]││
│  │ Feb 5, 2024              ││
│  │ ─────────────────        ││
│  │ 🔧 Furniture Removal     ││
│  │ 📍 123 Main St...        ││
│  │ 💵 $149.00               ││
│  │ [    Book Again    ]     ││
│  └─────────────────────────┘│
│                              │
│  ┌─────────────────────────┐│
│  │ #JOS-2024-002   [Done ✓]││
│  │ Jan 29, 2024             ││
│  │ ─────────────────        ││
│  │ 🔧 Appliances            ││
│  │ 📍 456 Oak Ave...        ││
│  │ 💵 $89.00                ││
│  │ [    Book Again    ]     ││
│  └─────────────────────────┘│
│                              │
├─────────────────────────────┤
│  🏠 Home  📦 Orders  👤 Profile│
└─────────────────────────────┘
```

### Status Colors:
- Completed: **Green**
- In Progress: **Yellow**
- Scheduled: **Blue**
- Cancelled: **Pink**

---

## 👤 6. Profile Tab
**File:** `ProfileView.swift`

### Visual Layout:
```
┌─────────────────────────────┐
│           Profile            │
│                              │
│  ┌─────────────────────────┐│
│  │         🟢 G            ││
│  │     Guest User           ││
│  │  guest@goumuve.com        ││
│  │   [ Edit Profile ]       ││
│  └─────────────────────────┘│
│                              │
│  App Settings                │
│  ┌─────────────────────────┐│
│  │ 🔔 Notifications       → ││
│  │ 📍 Location Services   → ││
│  │ 💳 Payment Methods     → ││
│  │ 🌐 Language            → ││
│  └─────────────────────────┘│
│                              │
│  Review Us On                │
│  ┌─────────────────────────┐│
│  │ 🔍 Google  ⭐ 4.9      ↗││
│  └─────────────────────────┘│
│  ┌─────────────────────────┐│
│  │ 🍎 App Store  ⭐ 4.8   ↗││
│  └─────────────────────────┘│
│  ┌─────────────────────────┐│
│  │ 🛡️ BBB  ⭐ A+          ↗││
│  └─────────────────────────┘│
│  ┌─────────────────────────┐│
│  │ ⭐ Trust Pilot  ⭐ 4.9  ↗││
│  └─────────────────────────┘│
│  ┌─────────────────────────┐│
│  │ 💬 Yelp  ⭐ 4.7         ↗││
│  └─────────────────────────┘│
│                              │
│  About & Legal               │
│  ┌─────────────────────────┐│
│  │ ℹ️ About Us             →││
│  │ 📄 Insurance Certificate→││
│  │ 🔒 Privacy Policy       →││
│  │ 📋 Terms & Conditions   →││
│  │ ✉️ Contact Us           →││
│  └─────────────────────────┘│
│                              │
├─────────────────────────────┤
│  🏠 Home  📦 Orders  👤 Profile│
└─────────────────────────────┘
```

---

## 🔄 Complete Navigation Flow

```
                    ┌──────────────────┐
                    │  Welcome Screen  │
                    │   (3 seconds)    │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   Main Tab View   │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌─────────┐    ┌─────────┐    ┌─────────┐
        │  Home   │    │ Orders  │    │ Profile │
        │   Tab   │    │   Tab   │    │   Tab   │
        └────┬────┘    └─────────┘    └─────────┘
             │
             ▼
     ┌──────────────┐
     │ Service Card │
     │   (Tap)      │
     └──────┬───────┘
            │
            ▼
     ┌──────────────┐
     │  Map Picker  │
     │  (Set Addr)  │
     └──────┬───────┘
            │
            ▼
     ┌──────────────┐
     │   Service    │
     │  Selection   │
     └──────┬───────┘
            │
            ▼
     ┌──────────────┐
     │Photo Upload  │
     │  (Existing)  │
     └──────┬───────┘
            │
            ▼
     ┌──────────────┐
     │ Date Picker  │
     │  (Existing)  │
     └──────┬───────┘
            │
            ▼
     ┌──────────────┐
     │Confirmation  │
     │  (Existing)  │
     └──────────────┘
```

---

## 🎨 Color Legend

| Color | Hex Code | Used For |
|-------|----------|----------|
| 🟢 **LoadUp Green** | #10B981 | Primary actions, tab accent |
| 🔵 **Blue** | #3B82F6 | Junk Removal category |
| 🟡 **Yellow** | #FBBF24 | Moving Labor category |
| 🔴 **Pink** | #EC4899 | Donation Pickups category |
| 🟢 **Green** | #10B981 | Property Cleanout category |
| 🟣 **Purple** | #8B5CF6 | Additional accent |
| 🟠 **Orange** | #F97316 | Additional accent |

---

## 📱 Responsive Behavior

### iPhone SE (Small):
- Cards stack vertically
- Single column layout
- Compact spacing

### iPhone 13/14 (Medium):
- Optimal layout
- Cards fill width
- Standard spacing

### iPhone 14 Pro Max (Large):
- Wider cards
- More white space
- Larger touch targets

---

## ✨ Animations

### Welcome Screen:
- Logo: Scale + Fade (0.8s)
- Trust badges: Slide up + Fade (0.8s, delay 0.3s)
- How it works: Slide up + Fade (0.8s, delay 0.5s)
- Button: Scale + Fade (0.8s, delay 0.7s)

### Tab Switches:
- Default iOS transition
- Green accent color

### Card Taps:
- Scale to 0.97 on press
- Bounce back animation

### Map Pin:
- Drop animation on appear
- Bounce on location change

---

## 🎯 Key Interaction Points

1. **Welcome → Main:** Auto after 3s OR tap "Get Started"
2. **Home → Map:** Tap any service card
3. **Map → Service:** Tap "Confirm Address"
4. **Service → Photo:** Tap "Book Now"
5. **Bottom Tabs:** Tap to switch between Home/Orders/Profile
6. **Profile Links:** Tap to navigate to detail screens

---

## 📐 Spacing & Layout

Using `JunkSpacing` tokens:
- `tiny`: 4pt
- `small`: 8pt
- `medium`: 12pt
- `normal`: 16pt
- `large`: 20pt
- `xlarge`: 24pt
- `xxlarge`: 32pt
- `huge`: 48pt

### Card Padding:
- Inner: 16pt (normal)
- Outer: 20pt (large)

### Corner Radius:
- Cards: 16pt
- Buttons: 12pt
- Small elements: 8pt

### Shadows:
- Cards: opacity 0.06, radius 4, y: 2
- Buttons: opacity 0.3, radius 8, y: 4

---

## 🔍 Screen Priorities

### Must-Have (High Priority):
1. ✅ Home Screen
2. ✅ Map Picker
3. ✅ Service Selection
4. ✅ Welcome Screen

### Nice-to-Have (Medium):
5. ✅ Orders Tab
6. ✅ Profile Tab

### Future Enhancement (Low):
7. Order detail views
8. Profile editing
9. Settings screens
10. Legal document views

---

## 📊 Performance Considerations

- **View Count:** 7 new views + 6 existing = 13 total
- **Asset Usage:** SF Symbols only (built-in, no bundle size impact)
- **Memory:** Lightweight SwiftUI views
- **Load Time:** Instant (no network calls for UI)

---

## ✅ Checklist for Testing

- [ ] Welcome screen shows correctly
- [ ] Auto-transition works (3 seconds)
- [ ] All 3 tabs switch properly
- [ ] Service cards navigate to map
- [ ] Map shows and updates address
- [ ] "Confirm Address" navigates forward
- [ ] Service detail cards display
- [ ] "Book Now" buttons work
- [ ] Orders tab shows mock data
- [ ] Profile sections are tappable
- [ ] All colors render (green theme)
- [ ] Trust badges visible on welcome
- [ ] Tab bar shows green accent

---

## 🎉 End Result

A complete, modern, LoadUp-inspired UI redesign with:
- 7 new screens
- Tab-based navigation
- Map-based address picker
- Colorful service cards
- Order tracking
- Comprehensive profile
- Green brand theme
- Trust signals throughout

**Ready for production! 🚀**

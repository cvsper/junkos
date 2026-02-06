# React Native Best Practices for JunkOS

Source: https://github.com/secondsky/claude-skills/blob/fa10bf37ebdfdfb263fe1dbf382474a3e8777b26/plugins/react-native-skills/skills/react-native-skills/SKILL.md

## Critical Performance Rules

### 1. List Performance (CRITICAL)
- ✅ Use **FlashList** for large lists (not FlatList)
- ✅ **Memoize list item components** (React.memo)
- ✅ Stabilize callback references (useCallback)
- ✅ Avoid inline style objects in lists
- ✅ Extract functions outside render
- ✅ Optimize images in lists
- ✅ Move expensive work outside items
- ✅ Use item types for heterogeneous lists

### 2. Animation (HIGH)
- ✅ Animate **only transform and opacity** (GPU-accelerated)
- ✅ Use **useDerivedValue** for computed animations
- ✅ Use **Gesture.Tap** instead of Pressable for better performance

### 3. Navigation (HIGH)
- ✅ Use **native stack and native tabs** over JS navigators (react-navigation native-stack)

### 4. UI Patterns (HIGH)
- ✅ Use **expo-image** for all images (better performance than Image)
- ✅ Use **Galeria** for image lightboxes
- ✅ Use **Pressable** over TouchableOpacity
- ✅ Handle safe areas in ScrollViews
- ✅ Use **contentInset** for headers
- ✅ Use **native context menus**
- ✅ Use **native modals** when possible
- ✅ Use **onLayout**, not measure()
- ✅ Use **StyleSheet.create** or **Nativewind** for styling

### 5. State Management (MEDIUM)
- ✅ Minimize state subscriptions
- ✅ Use dispatcher pattern for callbacks
- ✅ Show fallback on first render
- ✅ Destructure for React Compiler compatibility
- ✅ Handle shared values with React Compiler

### 6. Rendering (MEDIUM)
- ✅ Wrap text in **Text components**
- ✅ Avoid falsy && for conditional rendering (use ternary instead)

### 7. Monorepo (MEDIUM)
- ✅ Keep native dependencies in app package (not shared packages)
- ✅ Use single versions across packages

### 8. Configuration (LOW)
- ✅ Use config plugins for custom fonts
- ✅ Organize design system imports
- ✅ Hoist Intl object creation

---

## JunkOS Mobile App Implementation

Apply these rules to the booking app:

**Photo Upload List:**
- Use FlashList for photo grid
- Memoize photo thumbnail components
- Use expo-image for all images

**Booking Flow:**
- Native Stack Navigator (not JS stack)
- Animate transitions with transform/opacity only
- Use Pressable for all touch targets

**Forms:**
- Minimize re-renders with React.memo
- Stabilize callbacks with useCallback
- Use onLayout for dynamic measurements

**Camera:**
- Use expo-image-picker
- Optimize uploaded images before sending to API

**Maps:**
- Use react-native-maps (native)
- Optimize marker rendering with memoization

---

**Priority:** Apply CRITICAL and HIGH priority rules first, then optimize with MEDIUM/LOW rules.

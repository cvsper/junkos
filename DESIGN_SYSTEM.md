# Umuve Design System

Generated: 2026-02-06

## Design Pattern
- **Name:** Minimal & Direct + Demo
- **CTA Placement:** Above fold
- **Sections:** Hero > Features > CTA

## Visual Style
- **Name:** Vibrant & Block-based
- **Keywords:** Bold, energetic, professional, block layout, geometric shapes, high color contrast, modern
- **Best For:** SaaS platforms, business operations software, professional tools
- **Performance:** ⚡ Good | **Accessibility:** Ensure WCAG 2.1 AA compliance

## Color Palette

| Role | Hex | Usage |
|------|-----|-------|
| Primary | #6366F1 (Indigo) | Main brand color, primary buttons, links |
| Secondary | #818CF8 (Light Indigo) | Secondary actions, hover states |
| CTA | #DC2626 (Red) | Call-to-action buttons, success states |
| Background | #F5F3FF (Light Purple) | Page background, card backgrounds |
| Text | #1E1B4B (Dark Indigo) | Primary text, headings |

### Extended Palette (Light Mode)
- **Success:** #DC2626 (Red)
- **Warning:** #F59E0B (Amber)
- **Error:** #EF4444 (Red)
- **Info:** #3B82F6 (Blue)
- **Muted Text:** #64748B (Slate-600)
- **Borders:** #E2E8F0 (Slate-200)

### Dark Mode Palette
- **Primary:** #818CF8 (Lighter Indigo)
- **Background:** #1E1B4B (Dark Indigo)
- **Surface:** #312E81 (Indigo-900)
- **Text:** #F5F3FF (Light Purple)
- **Borders:** #4C1D95 (Purple-900)

## Typography

### Font Families
- **Heading:** Poppins (Google Fonts)
  - Weights: 400, 500, 600, 700
- **Body:** Open Sans (Google Fonts)
  - Weights: 300, 400, 500, 600, 700

**Mood:** Modern, professional, clean, friendly, approachable
**Best For:** SaaS, business apps, professional services, operations platforms

### Import Code
```css
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;500;600;700&family=Poppins:wght@400;500;600;700&display=swap');
```

### Tailwind Config
```js
fontFamily: {
  sans: ['Open Sans', 'system-ui', 'sans-serif'],
  heading: ['Poppins', 'sans-serif'],
}
```

### Type Scale
- **Display (h1):** 48px (3rem) / Poppins Bold
- **Heading 2:** 36px (2.25rem) / Poppins SemiBold
- **Heading 3:** 28px (1.75rem) / Poppins Medium
- **Heading 4:** 20px (1.25rem) / Poppins Medium
- **Body Large:** 18px (1.125rem) / Open Sans Regular
- **Body:** 16px (1rem) / Open Sans Regular
- **Body Small:** 14px (0.875rem) / Open Sans Regular
- **Caption:** 12px (0.75rem) / Open Sans Regular

### Line Heights
- **Headings:** 1.2
- **Body:** 1.6
- **Tight (UI labels):** 1.4

## Key UI Effects & Animations

### Spacing
- Large sections with 48px+ gaps between major blocks
- Card padding: 24px (desktop), 16px (mobile)
- Button padding: 12px 24px (desktop), 10px 20px (mobile)

### Animations
- **Duration:** 200-300ms for all transitions
- **Easing:** ease-in-out for most interactions
- **Hover Effects:** Color shift (primary → secondary), subtle scale (1.02x)
- **Loading States:** Skeleton screens with shimmer effect
- **Page Transitions:** Fade-in (opacity 0 → 1, 300ms)

### Interactive Elements
- **Buttons:** 
  - Primary: #DC2626 background, white text, 8px border-radius
  - Hover: Darken 10%, add shadow
  - Active: Scale 0.98
- **Cards:** 
  - Background: White (light mode) / #312E81 (dark mode)
  - Border: 1px solid #E2E8F0
  - Shadow: 0 1px 3px rgba(0,0,0,0.1)
  - Hover: Lift shadow (0 4px 6px rgba(0,0,0,0.1))

### Scroll Behavior
- Smooth scroll enabled
- Scroll-snap on sections (optional for hero/features)

## Layout Patterns

### Grid System
- **Max Width:** 1280px (container-xl)
- **Gutters:** 24px (desktop), 16px (mobile)
- **Columns:** 12-column grid

### Breakpoints (Mobile-First)
- **Mobile:** 375px - 639px
- **Tablet:** 640px - 1023px
- **Desktop:** 1024px - 1439px
- **Large Desktop:** 1440px+

### Common Patterns
1. **Hero Section:** Full-width, centered content, CTA above fold
2. **Feature Grid:** 3 columns (desktop), 1 column (mobile)
3. **Dashboard Layout:** Sidebar (240px) + main content area
4. **Job Cards:** Grid layout, 2-3 columns depending on screen size

## Component Guidelines

### Buttons
- **Minimum Size:** 44x44px (touch-friendly)
- **States:** Default, Hover, Active, Disabled, Loading
- **Types:** Primary (CTA), Secondary, Outline, Ghost
- **Icon Buttons:** Always include aria-label

### Forms
- **Input Height:** 44px minimum
- **Label Position:** Top-aligned (not floating)
- **Error Messages:** Below input, red text (#EF4444)
- **Validation:** Real-time on blur, final on submit

### Cards
- **Border Radius:** 8px
- **Shadow:** Subtle elevation
- **Padding:** 24px (desktop), 16px (mobile)
- **Hover:** Lift effect with increased shadow

### Tables
- **Row Height:** 56px (desktop), 48px (mobile)
- **Zebra Striping:** Optional for large datasets
- **Sticky Headers:** Enabled for scrollable tables
- **Mobile:** Convert to cards on < 640px

## Accessibility Checklist

- [x] **Color Contrast:** All text meets WCAG AA (4.5:1 minimum)
- [x] **Focus States:** Visible outline on all interactive elements
- [x] **Touch Targets:** Minimum 44x44px
- [x] **Alt Text:** All images have descriptive alt attributes
- [x] **ARIA Labels:** Icon-only buttons have aria-label
- [x] **Keyboard Navigation:** Tab order matches visual order
- [x] **Form Labels:** All inputs have associated labels
- [x] **Reduced Motion:** Respects prefers-reduced-motion

## Anti-Patterns to Avoid

❌ **Complex onboarding flow** — Keep booking to 3-5 steps max
❌ **Cluttered layout** — Use whitespace generously
❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide)
❌ **Layout shift on hover** — Use transform/opacity, not width/height
❌ **Invisible borders in light mode** — Ensure borders have sufficient contrast
❌ **Generic stock photos** — Use real product screenshots, avoid cheesy stock imagery

## Pre-Delivery Checklist

Before shipping any UI code:

### Visual Quality
- [ ] No emojis used as icons (use Heroicons/Lucide SVG)
- [ ] All icons from consistent icon set
- [ ] Brand logos are correct (if applicable)
- [ ] Hover states don't cause layout shift
- [ ] Theme colors used directly (no unnecessary var() wrappers)

### Interaction
- [ ] All clickable elements have `cursor-pointer`
- [ ] Hover states provide clear visual feedback
- [ ] Transitions are smooth (200-300ms)
- [ ] Focus states visible for keyboard navigation
- [ ] Loading states on async actions

### Light/Dark Mode
- [ ] Light mode text has sufficient contrast (4.5:1 minimum)
- [ ] Glass/transparent elements visible in light mode
- [ ] Borders visible in both modes
- [ ] Test both modes before delivery

### Layout & Responsive
- [ ] Floating elements have proper spacing from edges
- [ ] No content hidden behind fixed navbars
- [ ] Responsive at 375px, 768px, 1024px, 1440px
- [ ] No horizontal scroll on mobile
- [ ] Touch targets are 44x44px minimum

### Accessibility
- [ ] All images have alt text
- [ ] Form inputs have labels
- [ ] Color is not the only indicator
- [ ] `prefers-reduced-motion` respected
- [ ] Keyboard navigation works completely

## Implementation Notes

### Tailwind Utility Classes (Quick Reference)

**Colors:**
```css
bg-indigo-600      /* Primary */
bg-red-600     /* CTA */
text-indigo-950    /* Primary text */
border-slate-200   /* Borders */
```

**Typography:**
```css
font-heading       /* Poppins */
font-sans          /* Open Sans */
text-4xl font-bold /* Display headings */
leading-relaxed    /* Body text (1.6) */
```

**Spacing:**
```css
p-6 md:p-8        /* Card padding */
gap-12            /* Section gaps */
space-y-4         /* Vertical rhythm */
```

**Effects:**
```css
hover:bg-indigo-700 transition-colors duration-200
shadow-md hover:shadow-lg
rounded-lg
```

---

**Last Updated:** 2026-02-06  
**Version:** 1.0  
**Status:** Active

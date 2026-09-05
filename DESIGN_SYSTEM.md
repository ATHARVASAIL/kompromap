# Kompromap — Premium UI/UX Design System
## Next-Generation AppSec Attack-Chain Graph Interface

---

## Design Philosophy

**"Where darkness meets precision. Where intelligence becomes visible.**
**The future of security operations."**

A deep sci-fi/hacker aesthetic that transforms complex vulnerability data into an intuitive, high-performance command center. Every pixel serves intelligence. Every animation serves understanding.

---

## Color System

### Primary Palette
```css
--komp-bg-void:        #03070f    /* Deepest background - virtual black */
--komp-bg-primary:     #0a0f1c    /* Primary background - deep space blue */
--komp-bg-secondary:   #111827    /* Secondary surfaces - zinc-900 */
--komp-bg-elevated:    #1a2332    /* Elevated cards - slate-900 */
--komp-border-primary: rgba(0, 240, 255, 0.08)  /* Electric cyan at 8% */
--komp-border-secondary: rgba(148, 163, 184, 0.1) /* Slate-400 at 10% */
```

### Accent Colors (Strictly NO Red/Crimson)
```css
/* Active States & Interactive Elements */
--komp-accent-primary:     #00f0ff  /* Electric cyan - active states */
--komp-accent-glow:        rgba(0, 240, 255, 0.4)  /* Cyan glow effect */
--komp-accent-subtle:      rgba(0, 240, 255, 0.08) /* Very subtle cyan */

/* Severity & Alerts */
--komp-severity-critical:  #ffb700  /* Amber/gold - critical findings */
--komp-severity-high:      #ff8c00  /* Dark orange - high severity */
--komp-severity-medium:    #fbbf24  /* Lighter amber - medium */
--komp-severity-low:       #22c55e  /* Green - low severity */
--komp-severity-info:      #3b82f6  /* Blue - informational */

/* Status Colors */
--komp-status-verified:    #10b981  /* Emerald green - verified items */
--komp-status-false-positive: #6b7280  /* Gray - dismissed */
--komp-status-insufficient: #f59e0b  /* Amber - needs review */
```

### Text Hierarchy
```css
--komp-text-primary:    #f1f5f9  /* Slate-100 */
--komp-text-secondary:  #94a3b8  /* Slate-400 */
--komp-text-tertiary:   #64748b  /* Slate-500 */
--komp-text-disabled:   #475569  /* Slate-600 */
--komp-text-accent:     #00f0ff  /* Electric cyan */
```

---

## Component Specifications

### 1. LEFT SIDEBAR — Command Deck

**Visual Style:**
- Width: 240px (collapsed: 64px)
- Background: Glassmorphism with backdrop-blur-xl
- Border: 1px solid rgba(0, 240, 255, 0.1)
- Subtle gradient overlay

**Structure:**
- Logo with cyan glow
- Engagement selector dropdown
- Navigation items with sliding active indicator
- Live stats (nodes/edges count)
- Shortcuts button

**Sliding Active Indicator:**
- Absolute positioned pill that slides between nav items
- Cyan glow effect with backdrop blur
- Smooth 300ms cubic-bezier transition

### 2. CENTRAL WORKSPACE — Neural Graph Canvas

**Visual Style:**
- Full viewport canvas
- Deep space background with subtle grid overlay
- Node glow effects based on severity/type
- Pulsing animated edges for attack paths

**Node Styling:**
- Asset: Cyan border, slate background
- Finding: Amber border (critical), darker amber background
- Credential: Purple border, deep indigo background
- Other types: Distinct but cohesive color coding

**Attack Path Edges:**
- Normal edges: Subtle gray, thin lines
- YIELDS edges: Cyan glow with pulsing animation
- Selected path: Bright cyan, thicker line, enhanced glow

### 3. RIGHT DRAWER — AI Triage Copilot

**Visual Style:**
- Width: 420px
- Glassmorphism with cyan tint
- Slide-in from right with spring physics
- Sections with staggered fade-in animations

**Structure:**
- Assessment card (status, confidence, severity)
- Risk metrics visualization
- AI analysis text with expand/collapse
- Finding details
- Merge/Keep Separate/Duplicate actions
- Accept/Dismiss buttons

---

## Animation Specifications

### Micro-interactions
- Hover: Scale 1.1x with cyan tint (200ms)
- Active: Pill slides with glow pulse (300ms)
- Click: Subtle ripple effect
- Collapse: Width animation with icon centering

### Complex Animations (Framer Motion)
- Sidebar: Width transition 300ms
- Drawer: Spring physics (damping: 25, stiffness: 200)
- Sections: Staggered fade-in (50ms delay each)
- Command palette: Scale + fade from center (150ms)

### Edge Pulse Animation
- 2s loop, GPU-accelerated
- Opacity: 0.6 ↔ 1.0
- Width: 2.5px ↔ 3.5px
- Glow: drop-shadow with cyan color

---

## Typography

```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;

Scale: 12px (xs) → 14px (sm) → 16px (base) → 18px (lg) → 20px (xl) → 24px (2xl)
```

---

## Performance Targets

- Graph render: 60fps with 500+ nodes
- Sidebar transitions: 300ms
- Drawer animation: 300ms
- Tooltip delay: 200ms
- Command palette: 150ms
- Edge pulse: 2s loop, GPU-accelerated

---

## Accessibility

- Focus indicators: 2px cyan outline
- Keyboard navigation: Full app navigable
- Screen reader labels: All interactive elements
- Color contrast: Minimum 4.5:1 for text
- Motion preference: Respects prefers-reduced-motion

---

*"Precision in every pixel. Intelligence in every interaction.*
*This is Kompromap — where security meets sophistication."*

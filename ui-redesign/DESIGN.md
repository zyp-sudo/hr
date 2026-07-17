---
name: Nexus Talent Intelligence
colors:
  surface: '#131318'
  surface-dim: '#131318'
  surface-bright: '#39383e'
  surface-container-lowest: '#0e0e13'
  surface-container-low: '#1b1b20'
  surface-container: '#1f1f24'
  surface-container-high: '#2a292f'
  surface-container-highest: '#35343a'
  on-surface: '#e4e1e8'
  on-surface-variant: '#c9c4d8'
  inverse-surface: '#e4e1e8'
  inverse-on-surface: '#303035'
  outline: '#938ea1'
  outline-variant: '#484555'
  surface-tint: '#cabeff'
  primary: '#cabeff'
  on-primary: '#31009a'
  primary-container: '#947dff'
  on-primary-container: '#2a0088'
  inverse-primary: '#603ce2'
  secondary: '#9cd0d2'
  on-secondary: '#003739'
  secondary-container: '#184e50'
  on-secondary-container: '#8bbec0'
  tertiary: '#7fd5cd'
  on-tertiary: '#003733'
  tertiary-container: '#469e97'
  on-tertiary-container: '#00302c'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e6deff'
  primary-fixed-dim: '#cabeff'
  on-primary-fixed: '#1c0062'
  on-primary-fixed-variant: '#4816cb'
  secondary-fixed: '#b8ecee'
  secondary-fixed-dim: '#9cd0d2'
  on-secondary-fixed: '#002021'
  on-secondary-fixed-variant: '#184e50'
  tertiary-fixed: '#9bf2e9'
  tertiary-fixed-dim: '#7fd5cd'
  on-tertiary-fixed: '#00201e'
  on-tertiary-fixed-variant: '#00504b'
  background: '#131318'
  on-background: '#e4e1e8'
  surface-variant: '#35343a'
typography:
  headline-xl:
    fontFamily: Space Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  body-lg:
    fontFamily: Space Grotesk
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Space Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Space Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.05em
  data-numeral:
    fontFamily: JetBrains Mono
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 24px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  container-max: 1440px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
  stack-sm: 4px
  stack-md: 12px
  stack-lg: 24px
---

## Brand & Style

This design system is engineered for a high-performance, enterprise-grade Job-Person Matching System. The brand personality is **Technical, Visionary, and Analytical**. It bridges the gap between raw recruitment data and human potential through a sophisticated, data-rich dashboard aesthetic.

The visual style is a hybrid of **Modern Corporate and Technical Minimalism**. It utilizes a "Dark Mode First" approach to reduce eye strain for power users (recruiters and HR analysts) who interact with complex data for extended periods. The design emphasizes high-quality typography and vibrant, neon-inflected accents that suggest AI-driven precision and "matching" connectivity. Visual density is managed through generous spacing and clear structural hierarchies, ensuring that even the most complex datasets remain readable and actionable.

## Colors

The palette is anchored by a deep obsidian neutral (`#06060A`), providing a high-contrast foundation for the functional brand colors. 

- **Primary (`#7C5CFF`):** A vibrant violet used for primary actions, selection states, and core branding elements. It represents the "intelligence" layer of the system.
- **Secondary (`#B9EDEF`):** A refined, pale cyan used for high-impact data visualization, highlighting key metrics, and indicating elite-level matches. This updated tone provides a softer, more sophisticated glow.
- **Tertiary (`#8FE6DD`):** A soft mint used for auxiliary data points, filters, and secondary highlights.
- **Neutral:** We utilize a layered grayscale for depth. Pure black is reserved for the deepest background, while lighter variations define surfaces and borders.

The default color mode is **dark**, prioritizing the neon-on-dark aesthetic that characterizes modern AI and technical interfaces.

## Typography

This design system uses a dual-font strategy to balance character and utility. 

**Space Grotesk** is the primary typeface for all headlines and body copy. Its geometric quirks and modern construction provide a distinct "tech-forward" feel that differentiates the system from standard SaaS products.

**JetBrains Mono** is utilized for labels, technical metadata, and numeric data points within tables. This monospaced font ensures that alignment remains consistent across data columns and emphasizes the analytical, "under-the-hood" nature of the matching engine. 

Text should generally be set in high-contrast off-white for legibility against the dark backgrounds, with secondary text utilizing lower opacity (60-70%) of the same color.

## Layout & Spacing

The design system employs a **12-column fluid grid** for dashboard views, allowing content to breathe while maintaining rigorous alignment.

- **Desktop:** 12 columns with 24px gutters and 40px outer margins. Sidebar navigation is fixed at 280px.
- **Tablet:** 8 columns with 16px gutters and 24px margins. Sidebar collapses to an icon-only rail.
- **Mobile:** 4 columns with 16px gutters and 16px margins. Navigation moves to a bottom bar or hamburger menu.

Spacing follows an 8px rhythmic scale. Components like cards and data tables should use 24px internal padding (`stack-lg`) to maintain a premium, spacious feel despite the high density of information.

## Elevation & Depth

Hierarchy is established through **Tonal Layering** and **Subtle Blurs**, avoiding traditional heavy shadows which can feel muddy on dark interfaces.

- **Level 0 (Base):** The primary background color (`#06060A`).
- **Level 1 (Cards/Surfaces):** Raised surfaces use a slightly lighter neutral with a subtle border to create a crisp, "etched" look.
- **Level 2 (Modals/Popovers):** Higher surfaces add a subtle primary-tinted ambient glow (e.g., 10% opacity `#7C5CFF` with a 40px blur) to suggest light emanating from the interface.
- **Active States:** Interactive elements may use a backdrop-filter (blur: 8px) when overlaid on data visualizations to maintain legibility without losing context.

## Shapes

The shape language is **Rounded and Modern**. We have moved from sharp precision to a more approachable, modern SaaS aesthetic while maintaining structural integrity.

Standard components (Buttons, Inputs, Cards) use an 8px (0.5rem) radius. This increased roundedness softens the technical edge of the interface, making the complex data environment feel more user-friendly and contemporary.

Tags and "Status Pills" may use a fully rounded (Pill-shaped) geometry to distinguish them clearly from structural components like buttons or input fields.

## Components

### Buttons
- **Primary:** Solid `#7C5CFF` with high-contrast text. High-contrast, no shadow.
- **Secondary:** Ghost style with a `#B9EDEF` 1px border and matching text.
- **Actionable Icons:** 40x40px containers with 8px corner radius and subtle hover transitions.

### Input Fields
- Dark backgrounds with a 1px border and an 8px corner radius.
- On focus, the border transitions to Primary Purple (`#7C5CFF`) with a subtle outer glow.
- Labels use **JetBrains Mono** in all-caps, 12px, for a technical data-entry feel.

### Data Tables
- Header rows use a subtle background tint and **JetBrains Mono** labels.
- Rows are separated by 1px horizontal lines. 
- On hover, rows highlight with a 5% opacity Primary Purple overlay.

### Card Structures
- Cards for Job or Candidate profiles use Level 1 Elevation and an 8px corner radius.
- Headers within cards should use **Space Grotesk** Medium.
- Footer actions in cards are right-aligned and use ghost-style buttons.

### Match Score Visualizer
- A custom component utilizing a circular progress gauge or a thick horizontal bar. 
- Colors transition from Secondary (`#B9EDEF`) for high matches to Neutral Grays for low matches, creating a high-contrast visual indicator of success.
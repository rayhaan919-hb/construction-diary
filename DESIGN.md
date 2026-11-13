# Modern Minimalistic UI & Design Tokens (`DESIGN.md`)

## Core Aesthetic Rules (Strict)
1. **No AI Clutter:** Avoid rainbow gradients, heavy drop shadows, or unnecessary glassmorphism. Use flat tonal surfaces with crisp `1px` borders (`#E2E8F0` light / `#27272A` dark).
2. **Typography:** `Inter` (UI) + `JetBrains Mono` (IDs, timestamps, currency, API keys). Use `tabular-nums` on all numbers.
3. **Spacing Scale:** Strictly use `4px`, `8px`, `12px`, `16px`, `24px`, `32px`. Max container width: `1200px`.
4. **States:** Every data-fetching view MUST implement:
   - Skeleton loader (matching exact layout dimensions)
   - Actionable empty state (icon + 1-line explanation + primary CTA button)
   - Inline error banner with a "Retry" button

## Brand & Color Tokens (Outdoor High-Contrast & Bento Portal)
- `--bg-canvas`: `#F8FAFC`
- `--bg-surface`: `#FFFFFF`
- `--accent-primary`: `#D97706` (Construction Amber — high visibility outdoors)
- `--status-ok`: `#059669`
- `--status-warn`: `#EA580C`
- `--status-expired`: `#DC2626`
- **Mobile UI:** Minimum `48dp` touch targets for site supervisors wearing gloves; high-contrast black-on-white cards for sunlight legibility.

# Focus Logo Design (Soft Target) Design Doc

**Goal**: Add a calm, focus‑oriented logo that matches the current warm, soothing theme and scales cleanly from favicon to app icon.

## Summary
We will implement a rounded‑square “container” with a soft focus target inside (two rings + center dot). The outer container echoes “tymebox,” the inner target communicates “focus.” The mark is simple, monochrome‑capable, and legible at small sizes. Deliverables: SVG source and PNG exports for light/dark and apple icons to match the existing icon references in `app/layout.tsx`.

## Visual Specs
- **Shape**: Rounded square container, inner target with two rings + center dot.
- **Corner radius**: Match theme radius (`--radius` ≈ 0.75rem); for SVG use 20–24% of size.
- **Padding**: 12–15% inset from container to outer ring.
- **Ring thickness**: 8–12% of SVG size for clarity at 32px.
- **Colors (light)**:
  - Container fill: `--background`.
  - Container stroke: `--border`.
  - Outer ring: `--primary`.
  - Inner ring: `--accent` (subtle contrast).
  - Center dot: `--safe`.
- **Colors (dark)**:
  - Container fill: `--background`.
  - Container stroke: `--border`.
  - Rings/dot: same variables; rely on theme to maintain contrast.

## Deliverables
- `public/icon.svg` (scalable source)
- `public/icon-light-32x32.png`
- `public/icon-dark-32x32.png`
- `public/apple-icon.png` (180×180)

## Architecture / Implementation
- Store assets in `public/` so Next.js can serve them at root paths.
- SVG uses basic shapes: `<rect>` + `<circle>`; no filters or gradients.
- PNG exports generated from SVG (or by simple script) to ensure consistency.

## Data Flow
- No runtime data. Static assets only.
- `app/layout.tsx` already references icon paths; we will provide matching files.

## Error Handling
- If any icon file is missing, the browser falls back to default favicon or shows nothing.
- Ensure all filenames exactly match `app/layout.tsx`.

## Testing / Validation
- Manual: Run `npm run dev` and confirm favicon updates in light/dark mode.
- Manual: Inspect `icon.svg` in browser; verify clarity at 16/32/180px sizes.

## Non‑Goals
- No animated logo.
- No brand typography changes.


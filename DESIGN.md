# DESIGN.md

## Product Design Direction

Equipment Accounting is an operational system for accounting, review, writeoff, valuation, and sale of unused IT equipment.

The UI must feel like a calm workbench, not a marketing site and not a raw CRUD admin panel.

## Principles

- Prioritize scan, compare, decide, act.
- Keep navigation minimal. Do not show links that are not useful in the current role.
- Show primary workflows first. Hide secondary filters and maintenance tables behind disclosure controls.
- Tables are acceptable, but each table must have clear hierarchy, stable columns, and readable row labels.
- Use one primary action per surface where possible.
- Avoid placeholder buttons for non-MVP features.
- Avoid decorative hero sections, gradients, oversized cards, and visual noise.

## Surfaces

- Page background: light neutral.
- Work surfaces: white panels with subtle borders.
- Secondary zones: quiet off-white bands.
- Use cards only for summaries, repeated compact items, and framed tools.
- Do not nest visual cards inside cards.

## Color

- Primary action: restrained blue.
- Text: dark neutral.
- Muted text: gray.
- Status colors: quiet and semantic.
- Do not use multiple bright accent colors in the same workflow.

## Typography

- Use compact operational typography.
- Page headings are clear but not oversized.
- Form labels are short and bold.
- Table body text should remain scannable at dense data volume.

## Layout

- Header: brand left, at most one role-safe navigation link.
- Region workspace: simple summary, primary add action, recent records.
- Center registry: queue/status views first, then basic filters, then advanced filters, then table.
- Admin: summary first, create forms second, edit tables inside collapsible sections.
- Detail card: summary first, route actions second, data/photos/history below.

## Forms

- Keep common filters visible: search, location, region, type.
- Put process filters and dynamic fields into advanced filters.
- Form rows must not overlap at desktop, tablet, or mobile widths.
- Inputs must use `box-sizing: border-box`, `max-width: 100%`, and stable grid tracks.

## Tables

- Keep the primary object visually prominent.
- Prefer one strong link per row.
- Use muted secondary lines for defect/sale notes.
- Avoid showing every possible field in the first table layer.
- Use horizontal scroll for genuinely wide maintenance tables.

## Admin

- Admin screens are maintenance surfaces.
- Keep create operations visible.
- Put edit lists behind disclosure sections.
- Avoid showing all nested fields expanded by default.

## Do Not

- Do not add non-working buttons.
- Do not show center-only links to region users.
- Do not show duplicate navigation for the current page.
- Do not expose future functionality in MVP UI.
- Do not let filters or labels overlap.

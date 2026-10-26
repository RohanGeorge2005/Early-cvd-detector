# XAI-CVD interface style guide

The interface is a clinical research workspace for students, researchers, and clinicians reviewing model outputs. It prioritizes legibility, provenance, and clear limitations over promotional visuals. Model outputs are always labeled as research estimates, not diagnoses.

## Color

Tokens live in `frontend/app/tokens.css`. The default light palette uses a ten-step neutral scale (`--gray-0` through `--gray-950`) and one muted teal brand accent (`--brand-600`). Semantic colors are reserved for success, warning, danger, and information. The separate low, moderate, and high risk tokens map to risk labels, which always include text so color is never the only cue. Dark mode overrides the palette with its own surfaces and contrast values; it is not a simple inversion.

| Use | Light | Dark |
| --- | --- | --- |
| App background | `#f8fafb` | `#10191e` |
| Surface | `#ffffff` | `#17232a` |
| Main text | `#172a32` | `#edf2f2` |
| Muted text | `#586a72` | `#b1bec2` |
| Brand accent | `#176b66` | `#79c8bd` |

## Type and spacing

Use the existing system/Inter-compatible font stack; no font download is required. The type scale is 12, 14, 16, 20, 24, and 32px. Body copy uses normal letter spacing and a 1.55 line height. Use tabular numerals for probabilities, metrics, and measurements. Spacing follows a 4px base with 8px increments for routine layout. The main content is constrained to 1440px and adapts from a 12-column desktop grid to single-column mobile layouts.

## Shape, elevation, and motion

Use 6, 10, and 16px radii for controls, cards, and larger panels. Borders and subtle surface contrast establish grouping; reserve shadows for overlays and raised surfaces. State transitions are short and respect `prefers-reduced-motion`. Avoid ambient motion and decorative gradients.

## Components and interaction

- Keep one clear primary action per screen and secondary actions visually quieter.
- Use sentence case for headings, labels, and navigation. Reserve compact labels for genuinely useful metadata.
- Pair risk color with a written category. Pair chart color with direct labels, units, and readable values.
- Preserve visible keyboard focus, semantic headings, table captions, field labels, and accessible names for icon-only actions.
- On narrow layouts, present data tables as labeled rows rather than requiring horizontal scrolling.
- Keep one concise educational-use notice per screen. About and generated PDFs carry the fuller disclaimer.
- Never invent scores, sample sizes, model versions, or assessment history. If an API does not provide a value, show that it is unavailable.

## Do and avoid

**Do:** place current-session work first; show evaluation metrics with test-set context; explain whether an output is a probability, category, or binary label; tell users when session data clears.

**Avoid:** clinical claims, causal language for SHAP, unlabeled red/green encodings, decorative feature grids, repeated disclaimers, or silently filling missing inputs.

## Current API limitations

The prediction and evaluation API does not expose model-version metadata or calibration bins/Brier score. The interface labels version information as unavailable and does not draw a fabricated calibration chart. Assessment and generated-PDF lists are memory-only for the current app session; they clear on refresh.

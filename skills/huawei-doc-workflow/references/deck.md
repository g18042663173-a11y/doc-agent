# DeckIR 2.2 authoring guide

Read this file only for PPTX generation. The validator and `deck_ir.schema.json` remain authoritative.

## Root shape and narrative

Produce one bare JSON object:

```json
{
  "ir_type": "deck",
  "ir_version": "2.2",
  "meta": {
    "title": "...",
    "classification": "HUAWEI CONFIDENTIAL",
    "theme": "hw_v1"
  },
  "slides": []
}
```

Allowed themes are `hw_v1`, `hw-report`, `hw-proposal`, and `hw-academic`. Use the theme in `generation_packet.json`. Keep 1-30 slides; honor an explicit page target. A normal business deck should form a claim-evidence-action sequence rather than a list of disconnected pages.

All numeric claims, categories, units, sources, methods, dates, and statuses must be traceable to the brief or parsed source. Never manufacture a KPI to make a chart attractive. If evidence is missing, state that limitation or use a text layout.

## The 17 layouts

- `cover`: `title`; optional `subtitle`, `presenter`, `date`.
- `agenda`: `items` with 2-8 concise entries.
- `section`: `index`, `title`; optional `subtitle`.
- `title_bullets`: `title`, 1-7 `bullets` of `{text, level: 1|2}`; each item at most 60 Chinese characters.
- `two_column`: `title`, `left`, `right`. Each column has optional `heading` and either `text` or `bullets`.
- `table`: `title`, `table.header`, and nonempty rectangular `table.rows`; data area at most 12x8. Optional grouping, spans, widths, highlights, and conclusion column must remain in bounds.
- `cards`: `title`, 2-4 `cards` with `title`, `desc`, optional `tag`; optional `variant` is `default` or `kpi`.
- `chart`: `title` and `chart`. See chart rules below.
- `architecture_diagram`: `title`, unique `nodes`, valid `edges`, optional `groups` and manual geometry hints.
- `composite`: `title`, exactly left/right `regions`; each region contains 1-3 components from table, architecture, title_bullets, or cards.
- `process_flow`: `title`, 2-7 ordered `steps`; optional orientation `horizontal` or `vertical`.
- `timeline`: `title`, 2-8 `milestones`; status is `completed`, `current`, or `planned`.
- `image`: `title` and either a valid `image_ref` or an explicit `placeholder`; optional fit, focal point, alt, caption, and credit.
- `image_text`: `title`, an `image` object with `image_ref`, plus `text` or `bullets`; optional image position and heading.
- `image_grid`: `title`, 2-4 nonduplicate image entries with valid `image_ref` values.
- `infographic`: `title` and an infographic of kind `funnel`, `quadrant`, `cycle`, or `matrix` within the Schema capacities.
- `conclusion`: `title`, up to 5 `bullets`; optional one-line `cta`.

## Visual selection

- Use `line` for real time series, `bar` for category comparison, and `pie` only for 2-6 nonnegative parts of a meaningful whole.
- Use `scatter` only when paired x/y observations exist.
- Use `combo` only when the comparison genuinely needs different primary and secondary units. Different magnitudes alone are not a reason for a secondary axis.
- Use `architecture_diagram` for entity relationships, `process_flow` for linear steps, and `timeline` for dated or staged milestones.
- Use funnel/quadrant/cycle/matrix only when the underlying relationship matches the visual semantics.
- Use image layouts only with a prepared AssetManifest and an explicit text mapping from the brief or source to the exact asset. Technical image validation alone is not semantic grounding. Otherwise prefer text or an explicit, user-requested placeholder.
- Do not force every slide to contain a visual.

## Chart contract

`chart.kind` is `bar`, `line`, `pie`, `scatter`, or `combo`. Ordinary category charts use `categories` and `series[{name, values}]`. Scatter series additionally use `x_values`. Combo series require explicit `chart_type` (`bar` or `line`), `axis` (`primary` or `secondary`), and their real unit.

Optional fields include orientation, overall or per-series unit, category/value/secondary axis titles, number formats, source, methodology, note, thresholds, legend position, data labels, and side content. Preserve category order and raw values; never sort, merge, delete, rescale, or rewrite business data merely for appearance.

## Architecture and composite safety

Node IDs are unique. Every edge endpoint and group member must reference an existing node. Use node types `primary`, `secondary`, `emphasis`, `data`, `job`, or `module`. Keep edge direction and grouping faithful to the evidence.

When Graphviz is unavailable, the renderer records a deterministic-fallback runtime warning. Treat that as a visual-risk flag: inspect every architecture slide for undersized nodes, awkward wrapping, clipped text, edge-label collisions, and excessive unused space. A zero-error lint report does not clear this flag. Prefer concise node text with a short role line and one detail line; split an overloaded architecture slide rather than relying on fit-to-shape shrinking.

For KPI cards, keep the value and unit as one short visual token (for example, `16.4 ms`). The renderer preserves ordinary spaces in that token as nonbreaking spaces, but values should still stay concise and use consistent units across sibling cards.

Composite pages are for two related views that must be read together. Do not use them to squeeze unrelated content onto one page. If a region would overflow, split the material into separate slides.

## Examples

Use these for structure, not facts or historical version values:

- `scripts/engine/examples/deck_few_shot_table_v19.json`
- `scripts/engine/examples/deck_few_shot_architecture_v19.json`
- `scripts/engine/examples/deck_few_shot_composite_v19.json`
- `scripts/engine/examples/deck_valid_full.json`

Historical examples are migrated by the validator. New drafts must declare DeckIR `2.2`.

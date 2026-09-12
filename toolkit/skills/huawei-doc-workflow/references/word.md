# WordIR 1.3 authoring guide

Read this file only for DOCX generation. The validator and `word_ir.schema.json` remain authoritative.

## Root shape

Produce one bare JSON object:

```json
{
  "ir_type": "word",
  "ir_version": "1.3",
  "meta": {"title": "...", "classification": "内部公开"},
  "blocks": []
}
```

`meta.title` is required and nonblank. Optional metadata includes `subtitle`, `author`, `header_text`, and `footer_text`. Use only an allowed classification; default to `内部公开` when the user did not supply one.

For formal controlled documents, `meta.document_control` requires `product_name`, `document_name`, and `version`. Optional `prepared`, `reviewed`, and `approved` values have `{ "name": "...", "date": "..." }`. Do not invent approvers or dates.

## Blocks

Use only these ordered block types:

- `heading`: `level` 1-4 and nonblank `text`. Do not jump levels.
- `paragraph`: nonblank `text`; optional `style` is `normal`, `quote`, or `note`.
- `code_block`: `code` preserving whitespace; optional `language`.
- `bullet_list` or `numbered_list`: nonempty `items`, each `{ "text": "...", "level": 1|2 }`.
- `table`: nonempty `header`, nonempty rectangular `rows`, optional `caption` and positive `col_widths` matching the column count.
- `image_placeholder`: optional `ref` and `caption`. WordIR does not embed a real input image.
- `page_break`: no content fields.

Limits: heading levels 1-4, one paragraph or cell at most 2000 characters, table at most 100 rows by 12 columns, and no empty list. Split content instead of truncating measured facts.

## Source-grounded writing

- Preserve source names, numbers, units, conditions, dates, status, and uncertainty.
- Do not turn a warning, empty cell, unsupported object, or missing result into a positive claim.
- For xlsx input, distinguish formula text or parser statistics from evaluated business results.
- For pptx input, speaker notes are context, not automatically main-body claims.
- If the brief conflicts with measured source facts, keep the facts and describe the conflict.

Organize the document around the user's purpose. Prefer meaningful headings, short paragraphs, lists for parallel items, and tables only for genuinely tabular comparisons. Do not add decorative filler.

## Examples

Use these as structural examples, not as facts or version values:

- `scripts/engine/examples/word_valid_01_plain.json`
- `scripts/engine/examples/word_valid_03_table.json`
- `scripts/engine/examples/word_valid_05_document_control.json`

Some examples exercise historical migration. New drafts must declare WordIR `1.3`.

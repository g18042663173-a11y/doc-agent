# Validation, rendering, and lint failures

Read this file after any nonzero workflow exit.

## Repair discipline

Read `validation_report.json` and correct only the reported locations. The first draft plus two repairs is the hard limit. Do not delete evidence, relax a limit, add unknown fields, or change `ir_version` merely to silence an error. If the third validation fails, stop and report the final codes and locations.

## Contract error families

- Word `E001-E006`: malformed JSON, missing title, unknown block, invalid table/control metadata, invalid heading level, or empty content/list.
- Deck `D001-D006`: malformed JSON, missing title, unknown layout, missing/invalid layout fields, invalid table geometry, or bullet capacity.
- `W101-W104` and `I201`: recoverable hierarchy, empty/long/unknown-field, or default-classification notices. Read the normalized IR before finalizing.
- Asset `A001-A006`: unsupported/damaged/oversized image, duplicate ID, missing reference, or unsafe source/path.
- Template `E003`, `W201`, `W202`: unsafe package, deterministic redraw, or real font replacement.

JSON shell failures often come from a truncated object, trailing comma, multiple objects, prose outside the JSON, or an invalid escape. Save one complete UTF-8 JSON object. The shell may extract a historical fenced object, but new drafts should be bare JSON.

## Lint handling

Any Error blocks delivery. `finalize` does not publish the artifact when a lint Error remains.

- `HW-E01`: missing classification footer.
- `HW-E02`: disallowed font.
- `HW-E03`: animation or transition content.
- `HW-W01-W16`: typography, colors, density, table, slide count, grid, spacing, contrast, chart, image, infographic, or combo-chart risks.
- `HW-I01`: agenda and section-count mismatch.

Warnings do not automatically block the artifact, but the handoff must summarize them. Revise only when the change preserves source meaning. Never claim that automated lint proves visual quality, source truth, licensing, or final business approval.

## Environment failures

`SKILL-E001` means the installed engine snapshot is incomplete. `SKILL-E002` is an invalid or missing workflow input. `SKILL-E003` protects existing outputs. `SKILL-E020` is the repair stopping condition. `SKILL-E999` is the stable unexpected-failure boundary. Run `doctor --json`, retain the code, and avoid exposing credentials, raw sensitive prompts, or stack traces in the handoff.

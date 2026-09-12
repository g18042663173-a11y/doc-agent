# Template and image workflow

Read this file only when the deck uses a user-supplied PPTX template or local images.

## Prepare first

Pass every local PNG, JPEG, or WebP with a separate `--asset`. `prepare` decodes and normalizes the files, strips metadata, computes hashes, applies capacity limits, and writes `assets/asset_manifest.json`. Only the resulting `asset_id` values may appear in DeckIR.

Pass a `.pptx` template with `--template`. Preparation performs the Office package security preflight and writes `template_preflight.json` and `template_profile.json`. If preflight fails, stop; never bypass macro, ActiveX, OLE, external-relationship, path, size, shape-count, or damaged-XML checks.

If the only reported unsafe relationships are external hyperlinks, `sanitize-template` may create a separate safe copy. It removes only external hyperlink relationships and their `hlinkClick`/`hlinkHover` references, preserves OOXML namespace prefixes needed by Microsoft Office, runs the authoritative preflight again, and never modifies the original. Other external relationship types and active or embedded content remain hard failures. Use the safe copy in a new `prepare` run; do not reuse partial outputs from the rejected run.

## Authoring with assets

- Read the manifest rather than guessing an asset ID.
- Use `image_ref` only for an ID present in that manifest.
- This workflow does not inspect image pixels. A normalized file, filename, format, size, hash, or `asset_id` proves technical identity only, not subject matter or relevance.
- Use an asset only when the brief or parsed source explicitly maps its exact source filename or `asset_id` to a described purpose. If that text grounding is absent, keep the asset unused and report that human mapping is required.
- Supply honest `alt`, `caption`, and `credit` when known; do not invent ownership or licensing.
- Use `contain` when the whole image matters and `cover` only when cropping is acceptable. Set a focal point only when evidence supports it.
- Never use external URLs, absolute paths, base64 blobs, or a filename in place of `image_ref`.
- Use a placeholder only when the user explicitly wants a placeholder. A missing image reference is an A005 blocker, not permission to draw an empty box.

## Finalize consistently

Pass the same template and generated asset manifest to `finalize`. The renderer emits usage, crop, DPI, template replacement, structure, plan, and package audits when applicable. Review W201/W202 and HW-W13/HW-W14 rather than hiding them.

Template reuse may redraw a slide when a source layout is unsafe or too small. The output still must use validated DeckIR, current classification, and editable native objects. Template rendering must not copy animations, transitions, notes, comments, external hyperlinks, OLE, ActiveX, or unsafe embedded relationships.

Template profiling reads OOXML structure, text slots, geometry, colors, and fonts. It is not screenshot understanding or pixel-level imitation. A structurally valid template result still requires human comparison with the intended visual style.

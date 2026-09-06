# Fill all pages from material

Read skeleton.json, material.json and schema/fill_content.schema.json. Produce FillContent 2.0 in exactly the skeleton page order, with every slot exactly once. A role hint or keyword count is not evidence and never removes a page.

Every value must include evidence_refs containing actual material.evidence IDs. Preserve units, denominators and evaluation settings. A paraphrase may summarize supported facts; it must not introduce new results. Include derivation for computed chart data. Mark unsupported content status: missing with a reason. Missing content is blocked from final acceptance.

Use concise language that fits the original object, preserving its function. Do not copy facts from the source template. Keep image pixels, and document embedded text as a preserved visual exception. Native chart slots take categories and series, with equal series lengths. Do not replace missing data with zero.

Never invent a date, completion percentage, owner, benchmark or result to fill a template. Use a truthful stage label when a date is absent and explicitly label template progress bars as illustrative when their lengths are not data.

Final output requires native object readback and full visual/semantic review. Valid references prove traceability, not factual entailment by themselves.

# Progress

## 2026-07-11 Analyze-then-generate depth task

- Started with an extensive pre-existing dirty worktree; no unrelated changes will be reverted.
- Restored prior context from repository planning files because the planning skill's session-catchup helper is missing.
- Added phases 23-28 for source inspection, analyze CLI, optional generation depth, long-output handling, real-report acceptance, and completion audit.
- Current phase: inspect authoritative parser/generator/prompt/schema/taskbook behavior and capture default/schema baselines before implementation.
- Parser/generator inspection confirms measured counts and outline data already exist in DocumentIR; no parser changes are needed. The Codex transport and downstream shell can be reused, but analyze requires a non-IR response path that does not weaken or widen any schema.
- Prompt/repair inspection confirms legacy Deck generation is capped at 10 pages and already contains the core Huawei rules. The implementation will preserve the existing prompt byte-for-byte for no-option calls and use a separate opt-in depth/segmentation path for 14-18 page output.
- Taskbook and full DeckIR review confirm all depth requirements fit DeckIR v1.4. No parser, schema, renderer, checker, or linter edit is needed; the established demo is the current generation command surface.
- Captured the no-option baseline hashes for the canonical MD sample and all three schema files. Fresh full regression is green: `311 passed in 79.96s`.
- Added test-first coverage for measured analysis, metric-tamper rejection, analyze-only output, optional depth prompt rules, standard/detailed page counts, explicit page override, and the Codex analysis target. Initial run is correctly red: `8 failed`, all from missing new surfaces; no old assertion failed.
- Analyze phase complete. Targeted suite is green (`29 passed`); the CLI prints measured scale and three tiers, writes only `analysis.json`, and rejects AI-altered metrics through the shared repair/validation path.
- Optional depth prompt and stub generation tests are green (`8 passed`): standard defaults to 11 pages, detailed to 16, explicit pages override the range, and the pre-change legacy prompt hash remains exact.
- Added independent default-equivalence and dirty segmented-generation regressions; the focused depth suite is now `9 passed`. Ruff is green for all changed Python modules/tests.
- Long-output phase complete. Documentation and combined analyze/depth/Codex/repair/docs regression pass (`50 passed`). Next gate is full pytest/verify, then the real technical-report analyze + standard/detailed Codex runs and readable PDF exports.
- Full regression and verify are green (`322 passed`; overall coverage 87.34%). Default prompt/raw and all schema hashes are unchanged. The real report and conversion tools are present; starting real Codex analyze/standard/detailed acceptance.
- Real analyze and standard Deck succeeded. First detailed Deck is structurally valid but fails the semantic-depth gate because nested-section evidence was omitted by focused-context selection; adding a red regression before correcting subtree selection and regenerating.

## 2026-07-10 P0 gap closure

- Started from the verified baseline recorded immediately before this task: `220 passed`; `scripts/verify.py` passed with parsers 92.56%, IR 92.68%, lint 91.99%, overall 89.27%.
- The worktree already contains extensive prior user/task changes. They must be preserved; only targeted P0 edits will be added.
- `TASKBOOK_GAP_PLAN.md` has 34 P0 atomic rows, but several are aggregate acceptance rows. Implementation is organized around five root workstreams: contract gates, CLI failures, prompt/stub flow, parser robustness, and lint scope.
- Captured immutable canonical schema baselines before editing: Word 1.0 `88cf3a...e9a9`, Document 1.0 `915a98...9604`, Deck 1.4 `d8683d...277`.
- Contract batch decision: separate schema verification from explicit export, add version/hash history, and evolve DocumentIR 1.0 to 1.1 for format/content and preview-bound enforcement.
- Contract batch complete: DocumentIR 1.1, positive/negative samples, schema history/version gate, and read-only verify behavior are implemented. Targeted result: `97 passed`; three schema snapshots independently verified.
- CLI failure batch complete. Shared coded JSON boundary covers arguments and I/O; corrupt/missing Office checks write structured reports. Targeted result: `34 passed`; no traceback in negative subprocess cases.
- Prompt/stub content batch complete. Independent parse runs now produce byte-identical prompts; sample-backed few-shot and `est_chars` are present; four-format stub outputs carry a source fact. Targeted result: `17 passed`.
- Parser robustness batch complete. Targeted parser result: `44 passed`; actual >10MB/30,000-row worksheet is parsed under the 5-second test limit with bounded previews/scans.
- PPTX lint scope batch complete. Expanded lint result: `45 passed`; renderer/sample result: `16 passed`; representative rendered layouts have no new warnings.
- P0 closure complete: `TASKBOOK_GAP_PLAN.md` has 34/34 P0 rows marked ✅ with implementation/test evidence; `TASKBOOK_COMPLIANCE.md` was independently recounted as 106 satisfied, 22 partial, 13 unmet, with 25 remaining [A] items all belonging to P1/P2.
- Final independent test: `271 passed in 188.84s`. Final verify: parsers 92.90%, IR 93.30%, lint 92.80%, overall 89.50%; four-format semantic E2E and C0 pass.
- Schema verification is green for WordIR 1.0, DocumentIR 1.1, and DeckIR 1.4; ruff is green. No P0 was moved to [B].

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| `progress.md` did not exist when restoring planning-with-files context | 1 | Created it for the current P0 task; retained the existing uppercase `PROGRESS.md` as the project-facing historical log. |
| Contract-targeted suite rejected a 30-row DocumentIR table used as a nominal prompt fixture | 1 | The new 20-row Schema limit worked as intended; changed the valid fixture to the 20-row boundary while retaining long-paragraph truncation coverage. |
| Ruff found two unused `sys` imports after CLI error output moved to the shared helper | 1 | Removed the imports; no behavior change. |
| Prompt truncation test parsed through the newly inserted `est_chars` line | 1 | Updated the test to delimit DocumentIR JSON at the explicit `[字符估算]` section; generator extraction already uses `JSONDecoder.raw_decode`. |
| Picture-background contrast test was treated as white because a transparent text box reports `BACKGROUND` fill | 1 | Made `BACKGROUND` defer to picture-overlap detection; transparent text over a picture now yields explicit HW-W09 manual-review warning. |
| Targeted renderer command referenced nonexistent `backend/tests/test_visual_samples.py` | 1 | Located current test files with `rg --files`; reran against `test_pptx_renderer.py` and `test_ir_sample_matrix.py` only. |
| Ruff found missing `pytest` import in the new direct stub edge-case test | 1 | Added the explicit test dependency import before rerunning. |
| First parse double-failure refactor referenced `args.output` inside a helper that only receives `output` | 1 | Caught by immediate source inspection before tests; replaced with the helper parameter. |

## 2026-07-10 P0 independent-review remediation

- Started from `P0_REVIEW.md`: 23/34 satisfied, 11/34 partial, with seven root defects and four dependent aggregate rows.
- Baseline from the independent review: `271 passed`; verify parsers 92.90%, IR 93.30%, lint 92.80%, overall 89.50%.
- Worktree remains heavily dirty from earlier requested work; all remediation will be narrowly scoped and preserve unrelated changes.
- Phase 12 started: reproduce each review finding with a regression test before changing implementation.
- Persistence audit complete: DocumentIR has no database history, but multiple supported workflows intentionally write `document_ir.json`; compatibility migration is required.
- Verify design decision: delete the externally spoofable recursion flag by removing recursive full-verify invocation from pytest and replacing it with direct positive/negative gate tests.
- Parser design decision: use a killable worker only for large XLSX packages, plus OOXML drawing inspection for per-image geometry.
- Added test-first regressions for coordinated W06 metadata drift, renderer W07 edge placement, full DocumentIR+Prompt reproducibility, marker-only semantic loss, DocumentIR 1.0 migration, verify environment/coverage bypasses, XLSX image geometry, and a killable XLSX hard deadline. Implementation has not yet been changed; the next run is expected red.
- Test-first targeted run produced the expected red state: `13 failed, 84 passed`. Every failure maps to one planned root defect; no unrelated regression appeared.
- Compatibility/time/verify batch is green (`6 passed`): v1.0 reads migrate to v1.1 with a warning, repeated DocumentIR and Prompt bytes match, and an externally preset recursion flag no longer bypasses test failure.
- First multi-fact E2E run caught a real XLSX loss that the old marker missed: the second sheet's `指标/值` header was absent from DeckIR. Stub sheet fact extraction is being expanded before rerunning.
- Multi-fact E2E remediation is green (`5 passed`): marker-only output fails; md/docx/xlsx/pptx each pass through both Word and Deck, and every extracted fact is present in generated IR and the final editable artifact. XLSX with 24 facts stays within the 12-slide cap by omitting the nonessential cards page.
- Actual PPTX geometry remediation is green (`62 passed` across lint, renderer, and IR sample tests). The coordinated metadata spoof and renderer edge-placement regressions now fail correctly; full rendered samples remain free of W06/W07.
- XLSX image geometry and hard-deadline remediation is green. The parser records sheet/anchor/width/height/part/bytes, isolates >=10MB packages, terminates timed-out workers, and preserves structured worker errors.
- A new EOF worker-cleanup issue was found while raising branch coverage and fixed before closure; EOF now yields E001 and unconditional process cleanup.
- DocumentIR 1.0 compatibility is implemented because supported workflows persist `document_ir.json`; migration is in-memory, warning-bearing, and still enforces all 1.1 constraints. Usage documentation and tests describe the no-auto-overwrite boundary.
- `VERIFY_RUNNING` bypass is removed. Direct positive main testing plus external-env failure and low-coverage negatives replace the recursive verify test.
- `P0_REVIEW.md` and `TASKBOOK_GAP_PLAN.md` now record 34/34 P0 rows as independently satisfied with current file/test evidence.
- Final full pytest: `288 passed in 31.30s`. Final verify: parsers 93.30%, IR 93.37%, lint 92.88%, overall 89.58%; four-format multi-fact E2E and C0 pass. Schema snapshots/history and ruff are green; no skip/xfail.

## 2026-07-11 analyze first, then depth-controlled generation

- Added an independent, non-IR analysis recommendation structure and `scripts/analyze.py`. The real CAST report result at `output/codex_depth_analysis/analysis.json` reports 62 titles, depth 4, 19 tables, and about 74,123 characters, recommending detailed 14-18 pages.
- Added opt-in `--pages` / `--depth` generation. No options retain the legacy branch byte-for-byte; standard defaults to 11 pages and detailed to 16 only after the new options are explicitly supplied.
- Detailed generation uses an outline plus four-page chunks, shared shell/schema validation, and the existing repair path. The real 16-page run completed in four chunks without truncation; regressions force truncated outline D001 and wrong chunk count D006 through repair.
- Real outputs are `output/codex_depth_standard/` (11 pages) and `output/codex_depth_detailed_v2/` (16 pages). Detailed pages include concrete CNN sample/accuracy evidence, CNN-LSTM architecture and 1000 km/NMSE evidence, WFRFT conditions, and sample-rate/throughput figures.
- Readable Chinese WPS/Noto PDF previews are `output/codex_depth_standard/deck_preview.pdf` and `output/codex_depth_detailed_v2/deck_preview.pdf`.
- Final independent checks: `323 passed in 19.61s`; `scripts/verify.py` passed with parsers 93.75%, IR 93.44%, lint 94.01%, overall 87.46%; focused completion checks `6 passed`; ruff and `git diff --check` green.
- Word/Document/Deck schema SHA-256 hashes are unchanged from the pre-feature baseline. This feature made no task-specific change to IR fields or parse/render/check/lint core behavior.

## 2026-07-11 macOS Chinese-font preview

- Installed user-level Noto Sans CJK SC Regular/Bold solely for local preview. A font-substituted PPTX copy was generated under `output/codex_cli_real_deck_10slides/font_preview_noto/`; no source code, IR, or theme token changed.
- macOS LibreOffice continued to rasterize Chinese as missing glyphs even after the explicit font substitution, so it is not suitable as this host's visual-preview tool.
- WPS Office opened the existing 10-slide deck with correct Chinese fallback and exported a verified 10-page PDF. The copied preview is `output/codex_cli_real_deck_10slides/font_preview_noto/wps/deck_wps_preview.pdf`; sampled pages 1, 5, 6, 8, and 10 contain readable Chinese with no black-background or box-glyph issue.

## 2026-07-10 Temporary CodexGenerator upper-bound validation

- Added the isolated `backend/app/generators/codex.py` adapter. It calls OpenAI-compatible Responses API only through `OPENAI_API_KEY`, defaults to `gpt-5.6-terra` unless `OPENAI_MODEL` overrides it, supports custom `OPENAI_BASE_URL`, and never writes credentials or API response diagnostics containing secrets.
- The existing `shell.py` extraction, target-schema validation, error-code mapping, and `repair_ir_text()` two-retry loop remain the only validation path. `scripts/demo_e2e.py --generator codex` now uses that same path; parse/render/check/lint and both target schemas were not changed.
- Added eight non-network tests for request construction, deck prompting rules, key/API failure redaction, repair-loop reuse, explicit `codex` selection, environment selection, default stub behavior, and structured no-key CLI failure.
- Current verification: `308 passed in 15.88s`; schema snapshots are unchanged and `git diff --check` is green. `python scripts/verify.py` passed: parsers 93.75%, IR 93.37%, lint 94.01%, overall 89.52%.
- The user authorized a temporary OpenAI-compatible upper-bound run through a custom Responses endpoint. The key remains process-only and must be rotated afterward because it was supplied in chat.
- Initial runtime network audit: the Python installation had no default CA file, so HTTPS first failed before reaching the API. A process-only `SSL_CERT_FILE` pointing at the already-installed certifi bundle reached the official endpoint but returned HTTP 401 before model dispatch; the later custom-provider run below is the authoritative live validation.
- Live custom-provider validation: the configured OpenAI-compatible `/models` endpoint returned HTTP 200 when reached with a process-only certificate bundle. A minimal WordIR request returned valid JSON and passed the existing schema shell without repair.
- Public DOCX Word run: the source parsed to 859 blocks (62 headings, 778 paragraphs, 19 tables) with 102 parser warnings. The real model's initial WordIR directly passed validation (no repair), produced 24 blocks (13 headings, 9 paragraphs, 1 bullet list, 1 table), rendered to `output/codex_real_word/word.docx`, and its DOCX lint report was `pass=true` with no items.
- Honest visual boundary: the macOS LibreOffice preview has missing Chinese glyphs and a black second-page rendering anomaly, so the generated DOCX is structurally verified but not visually accepted on this host. Windows with the required font stack remains the required visual gate.
- Public DOCX Deck run: no real-model PPTX was produced. Under the requested `gpt-5.6-terra + xhigh + responses` configuration, the full DeckIR request exceeded the 300-second timeout, while reduced and minimal DeckIR requests each returned upstream HTTP 502. This was mapped to `D001`; no stub fallback was presented as a real-model result. Provider recovery or an approved model/API-mode change is required before retrying.
- DeckIR retry: a separate rerun against the same public DOCX and requested configuration again failed immediately with upstream HTTP 502 (`output/codex_real_deck_retry/run.log`). The local parser completed and the prompt was produced; no incomplete IR or PPTX artifact was kept.
- `gpt-5.5` retry: changing only `OPENAI_MODEL` to `gpt-5.5` also returned upstream HTTP 502 for the public DOCX DeckIR request. A minimal WordIR probe failed with the same result, so this is currently a provider routing/model-availability failure rather than a DeckIR-specific issue.
- CCSwitch validation: the imported 百事可乐 provider was initially not active; it was activated in CCSwitch, which wrote `model=gpt-5.5`, `model_provider=custom`, and the configured Responses endpoint to the Codex config. CCSwitch correctly required a new client session.
- A new `codex exec` session through that CCSwitch configuration returned a minimal expected response, then generated both target IRs from the public DOCX. DeckIR was 1,555 characters, directly schema-valid, and rendered to a 6-slide PPTX (cover, agenda, title_bullets, architecture_diagram, cards, conclusion); its lint report had 0 Error, HW-W09 Warning, and HW-I01 Info. WordIR was 2,241 characters, directly schema-valid, and rendered to a 27-block DOCX (12 headings, 11 paragraphs, 1 list, 1 table, 2 image placeholders); its lint report had no items.
- This is a real successful model-to-IR-to-render validation through CCSwitch, but it uses the Codex CLI's authenticated custom-provider route rather than the project's API-key-based `CodexGenerator` HTTP adapter. No source implementation or IR contract was changed for this fallback test. macOS LibreOffice previews still lack the required Chinese font and show black/box-glyph rendering, so they are not visual acceptance evidence.
- Final generator integration: `CodexGenerator` now has an explicit `CODEX_GENERATOR_TRANSPORT=cli` option for already-authenticated CCSwitch/Codex CLI routes. It keeps `http` as the default, runs `codex exec --ephemeral --ignore-rules -s read-only`, uses UTF-8 subprocess I/O, writes the final message only inside a temporary directory, avoids logs/credentials in errors, and preserves the active CCSwitch model unless `OPENAI_MODEL` is explicit. Tests cover invocation, explicit-model handling, failure redaction, and the existing repair loop.
- Final real E2E through `scripts/demo_e2e.py --generator codex`: Word output at `output/codex_cli_real_word/word.docx` came from a directly valid 33-block WordIR (14 headings, 15 paragraphs, 1 list, 2 tables, 1 image placeholder) and its DOCX lint report is clean. Deck output at `output/codex_cli_real_deck_10slides/deck.pptx` came from a directly valid 10-slide DeckIR (cover, agenda, section, 2 title-bullets pages, table, architecture diagram, cards, two-column, conclusion); its lint report has 0 Error, HW-W09 Warning, and HW-I01 Info. Both have PDF previews.
- Final regression: `311 passed in 16.56s`; `python scripts/verify.py` passed (parsers 93.75%, IR 93.37%, lint 94.01%, overall 89.40%). All three schema snapshots match their exported schemas (Word SHA-256 `fa45ae66...`, Document `7bb8fe73...`, Deck `469643c3...`); ruff and `git diff --check` are green.

## 2026-07-10 P1 delivery asset closure

- Started after confirming all 18 P1 rows remain open and `samples/expected/` has no files.
- No pytest/verify/demo/Office conversion process survived the interrupted turn.
- Scope is asset-only: fixed fixtures, manifests, expected JSON, review records, docs, demo evidence, and tests. Core app behavior and IR contracts will not be changed.
- Planned batches: fixed samples/expected/invalid assets; Windows dependency hashes and review records; docs/demo screenshots; full verification and 18-row evidence update.
- Added deterministic asset builders for Appendix B Office files, parser category matrix, structural expected JSON, sample outputs, Deck D001-D006 fixtures, lint violation injection, Windows wheel hashes, and cross-platform demo evidence.
- Generated 24 core delivery assets plus three official DOCX outputs, full Deck output, lint violation PPTX/report, 20 parser-category fixtures, and 8-page Appendix B PPTX expected.
- Downloaded 26 real CPython 3.12/win_amd64 wheels (17 MB local ignored wheelhouse), wrote `requirements-win312.lock` and SHA-256 manifest, and verified the complete lock with pip `--dry-run --require-hashes`.
- Generated real command logs and 1600x900 success/failure screenshots; visual inspection confirmed readable Chinese and visible return codes/D003.
- Added delivery/review/task-card docs and synchronized README, usage, intranet, acceptance, style, and Appendix A.2.
- Asset/docs targeted verification: `16 passed`.
- P1 independent verification complete: `300 passed in 95.29s`; `python scripts/verify.py` passed with four-format semantic E2E and C0. Coverage: parsers 93.75%, IR 93.37%, lint 92.88%, overall 89.66%. Schema snapshot verification, ruff, and `git diff --check` are green.

## 2026-07-11 analyze/depth generation completion

- Real analyze result is persisted at `output/codex_depth_analysis/analysis.json`: 62 titles, 4-level structure, 19 tables, about 74,123 characters; detailed 14-18 pages is recommended.
- Real standard output is 11 pages in `output/codex_depth_standard/`; real detailed output is 16 pages in `output/codex_depth_detailed_v2/` and was assembled from four validated chunks with no real truncation or repair event.
- The corrected detailed Deck contains concrete method/data evidence rather than additional headings: 40 to 72+ samples and 90.84% to 95.59%; 4-layer CNN plus two 256-unit LSTM layers, 20,000 data groups, 1000 km and NMSE -10 dB; WFRFT order/step/SIR conditions; 245.76/61.44 MHz processing parameters and 1.047 Gbps throughput.
- WPS/Noto Chinese PDF previews are final at `output/codex_depth_standard/deck_preview.pdf` (11 pages) and `output/codex_depth_detailed_v2/deck_preview.pdf` (16 pages). Visual samples contain readable Chinese and no converter black background.
- Final verification: `323 passed in 19.61s`; `scripts/verify.py` passed with parsers 93.75%, IR 93.44%, lint 94.01%, overall 87.46%; focused default/schema/truncation checks `6 passed`; ruff and `git diff --check` green.
- Three schema hashes exactly match the feature baseline. No task-specific edit touched an IR field or parse/render/check/lint core behavior; the legacy no-option prompt/raw/DeckIR remain byte-identical.
- XLSX image geometry and hard-deadline remediation is green. The parser records sheet/anchor/width/height/part/bytes, isolates >=10MB packages, terminates timed-out workers, and preserves structured worker errors.
- A new EOF worker-cleanup issue was found while raising branch coverage and fixed before closure; EOF now yields E001 and unconditional process cleanup.
- DocumentIR 1.0 compatibility is implemented because supported workflows persist `document_ir.json`; migration is in-memory, warning-bearing, and still enforces all 1.1 constraints. Usage documentation and tests describe the no-auto-overwrite boundary.
- `VERIFY_RUNNING` bypass is removed. Direct positive main testing plus external-env failure and low-coverage negatives replace the recursive verify test.
- `P0_REVIEW.md` and `TASKBOOK_GAP_PLAN.md` now record 34/34 P0 rows as independently satisfied with current file/test evidence.
- Final full pytest: `288 passed in 31.30s`. Final verify: parsers 93.30%, IR 93.37%, lint 92.88%, overall 89.58%; four-format multi-fact E2E and C0 pass. Schema snapshots/history and ruff are green; no skip/xfail.

## 2026-07-20 Composite 组合页版式

- 从提交 `fb0cd24` 的干净基线开始；设计报告为 `COMPOSITE_LAYOUT_DESIGN.md`。
- 用户确认首版仅嵌入 table / architecture_diagram / title_bullets / cards；process_flow 暂缓但保留后续扩展。
- 先补回归测试，初始红灯为 `8 failed, 2 passed`，失败均来自尚未实现的 DeckIR 1.7 / composite。
- DeckIR 已升到 1.7，1.4 / 1.5 / 1.6 可在内存迁移；CompositeRegion 复用四种既有 slide model，非法 table / architecture / bullets / cards 会递归返回原 D003-D006。
- 左右区域由主题 12 栏网格定义为 5 栏 + 1 栏间距 + 6 栏；表格、Graphviz 架构、要点、卡片复用原绘制函数，旧整页调用默认参数不变。
- 嵌入架构图超过 12 条边的真实 PPTX 仍由现有 lint 报 `HW-W03`，未新增 composite lint 豁免。
- 过程错误：planning-with-files 要求的 `progress.md` 在 macOS 大小写不敏感文件系统上指向了本文件，曾短暂覆盖历史内容；已从 HEAD 完整恢复后追加本节。
- 最终全量测试 `411 passed in 30.14s`；`verify.py` 通过，覆盖率 parsers 93.75%、IR 93.83%、lint 94.44%、overall 88.72%；ruff 与 schema 快照均通过。
- 试点产物为 `output/composite_layout_review/deck_composite_table_architecture.pptx`，中文 WPS PDF 为 `output/deck_composite_table_architecture_wps_preview.pdf`；视觉检查无重叠、裁切或标签压节点。

## 2026-07-20 Composite v1.8 栏内堆叠

- DeckIR 从 1.7 升至 1.8：`CompositeRegion.component` 演进为 `components[1..3]`；1.4/1.5/1.6/1.7 在内存深拷贝迁移到 1.8，1.7 的单 component 自动包为单元素列表，原输入对象不会被修改。
- 单元素 components 继续走 v1.7 整栏渲染路径；回读测试比较 v1.7 与等价 v1.8 的原生 PPTX shape 名称、文本和几何，结果一致。
- 多块区域按主题 token 从上到下堆叠：表格使用主题行高、要点使用最大正文候选字号测量、卡片使用原有卡片高度、架构图以 Graphviz 实际包围盒测量；累计超出栏高时，lint 从透明块边界的真实几何输出 `HW-W03`，不缩到不可读、不截断、不自动拆页。
- 递归 lint 已覆盖：堆叠内 13 条边 architecture_diagram 仍报既有密度 `HW-W03`；三块累计超高时新增 `组合页该栏内容过多` `HW-W03`。table、要点和 KPI 的原有产物规则继续通过原 lint 路径执行。
- 视觉样例为 `samples/ir/deck_valid_11_composite_stacked.json`，产物 `output/composite_stacked_venus_review/deck_composite_stacked_venus.pptx`，中文 PDF `output/composite_stacked_venus_review/deck_composite_stacked_venus.pdf`。左栏表格、架构图、要点顺序清楚且无重叠/裁切；该混合密度页仍有 1 条真实 `HW-W01`（全页 7 种字号超过主题上限 3 种），未做豁免。
- 相关回归 `268 passed`，全量 pytest 在新增 v1.8 兼容几何测试前为 `417 passed`；最终门禁待本轮结束时再次运行。

## 2026-07-20 Architecture diagram v1.9 语义配色

- DeckIR 升至 1.9：ArchitectureNode.type 改为非空、可扩展字符串；主题注册 primary/secondary/emphasis/data/job/module，未知 type 不猜测业务含义，回退到 theme default 色。
- 既有色值保持不变：primary 青、secondary 黄、emphasis 红、data 绿；新增 job 黄、module 绿。renderer 与 lint 都从 `layouts.architecture_diagram.node_type_colors` 读取同一映射，不保留硬编码配色表。
- 试点样例 `samples/ir/deck_valid_12_architecture_semantic_colors.json` 已生成原生可编辑 PPTX 和中文 PDF：`output/architecture_semantic_colors_review/deck_architecture_semantic_colors.pdf`。视觉检查确认 Job/未知 type 为黄，module/data 为绿，Graphviz 关系和标签清楚；CLI lint 为 0 Error / 0 Warning。
- 回归覆盖注册 type 与未知 default 填色、主题色 lint、已有架构与 composite/堆叠样例。最终全量 pytest、verify、ruff、Schema 快照待本轮结束时再次运行。

# Progress

## 2026-07-29 实际使用可靠性测试与故障治理

- HTML 技术参考已审计：附件描述的是 `HTML -> html2pptx -> PptxGenJS` 浏览器布局转换，只作为经验参考；生产 PPTX 继续保持 DeckIR 1.9 到 python-pptx，不引入 HTML/PptxGenJS/浏览器渲染。
- 新增异步任务失败契约：`code`、`stage`、`retryable`、`message`、`suggestion`、`support_id`；失败任务生成受控 `failure-report`，状态响应和报告均不泄露异常堆栈、原始 Prompt、输入正文或模型原文预览。
- 修复真实开发路径问题：直接使用仓库 `.venv` 执行 pytest 原先缺少 `PYTHONPATH=backend`；已由 `pytest.ini` 固定。超限上传会清理本次新建的空 job 目录；工作台补充空 favicon，浏览器控制台不再出现 404。
- 新增 `scripts/reliability_test.py`，输出 JSON、JUnit、静态 HTML QA 摘要；默认执行离线 `verify.py` 和全量 pytest，可选 `--ui` 开发浏览器验证或 `--real-model` 显式真实模型冒烟。报告只保存测试名、失败类型和错误码。
- 新增开发专用 Playwright 工作台检查、PowerPoint/Word COM 导图脚本和 Pillow PNG 差异工具；它们不进入生产 lock，也不参与 PPT 渲染。HIT Deck 已由 PowerPoint COM 成功导出 PDF/PNG；自比对通过。
- 开发质量依赖固定为 `ruff==0.16.0`，以 `E9/F` 正确性规则作为现阶段仓库门禁；由此发现并修复了 Word 模式携带 `--template` 时引用未定义 `parser` 的 CLI 崩溃，新增无 traceback 的参数错误回归。
- 当前验收：`verify.ps1` 通过（parsers 93.64%、IR 93.99%、lint 93.89%、整体 89.07%）；`scripts/reliability_test.py --skip-verify --ui` 的 QA 报告为 516 tests、501 passed、0 failed、15 skipped；桌面 1280px 与移动 390px 均无横向溢出和控制台错误。`pip check` 与 ruff 正确性检查通过。
- 仍待人工：真实脱敏 docx/xlsx/pptx 各至少 3 个、真实模型稳定端点验收、固定 Office/字体环境下人工批准视觉 baseline 与最终审美签字。

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
- `docs/history/2026-07/TASKBOOK_GAP_PLAN.md` has 34 P0 atomic rows, but several are aggregate acceptance rows. Implementation is organized around five root workstreams: contract gates, CLI failures, prompt/stub flow, parser robustness, and lint scope.
- Captured immutable canonical schema baselines before editing: Word 1.0 `88cf3a...e9a9`, Document 1.0 `915a98...9604`, Deck 1.4 `d8683d...277`.
- Contract batch decision: separate schema verification from explicit export, add version/hash history, and evolve DocumentIR 1.0 to 1.1 for format/content and preview-bound enforcement.
- Contract batch complete: DocumentIR 1.1, positive/negative samples, schema history/version gate, and read-only verify behavior are implemented. Targeted result: `97 passed`; three schema snapshots independently verified.
- CLI failure batch complete. Shared coded JSON boundary covers arguments and I/O; corrupt/missing Office checks write structured reports. Targeted result: `34 passed`; no traceback in negative subprocess cases.
- Prompt/stub content batch complete. Independent parse runs now produce byte-identical prompts; sample-backed few-shot and `est_chars` are present; four-format stub outputs carry a source fact. Targeted result: `17 passed`.
- Parser robustness batch complete. Targeted parser result: `44 passed`; actual >10MB/30,000-row worksheet is parsed under the 5-second test limit with bounded previews/scans.
- PPTX lint scope batch complete. Expanded lint result: `45 passed`; renderer/sample result: `16 passed`; representative rendered layouts have no new warnings.
- P0 closure complete: `docs/history/2026-07/TASKBOOK_GAP_PLAN.md` has 34/34 P0 rows marked ✅ with implementation/test evidence; `docs/history/2026-07/TASKBOOK_COMPLIANCE.md` was independently recounted as 106 satisfied, 22 partial, 13 unmet, with 25 remaining [A] items all belonging to P1/P2.
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

- Started from `docs/history/2026-07/P0_REVIEW.md`: 23/34 satisfied, 11/34 partial, with seven root defects and four dependent aggregate rows.
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
- `docs/history/2026-07/P0_REVIEW.md` and `docs/history/2026-07/TASKBOOK_GAP_PLAN.md` now record 34/34 P0 rows as independently satisfied with current file/test evidence.
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
- `docs/history/2026-07/P0_REVIEW.md` and `docs/history/2026-07/TASKBOOK_GAP_PLAN.md` now record 34/34 P0 rows as independently satisfied with current file/test evidence.
- Final full pytest: `288 passed in 31.30s`. Final verify: parsers 93.30%, IR 93.37%, lint 92.88%, overall 89.58%; four-format multi-fact E2E and C0 pass. Schema snapshots/history and ruff are green; no skip/xfail.

## 2026-07-20 Composite 组合页版式

- 从提交 `fb0cd24` 的干净基线开始；设计报告为 `docs/design/COMPOSITE_LAYOUT_DESIGN.md`。
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

## 2026-07-29 Windows、模板驱动 PPT 与图表质量升级

### 已完成并通过阶段验收

- Windows 基线固定为仓库 `.venv` / Python 3.12.10；依赖闭包加入 `colorama==0.4.6`，28 个 Windows wheel 的 lock、manifest 与 SHA-256 已更新，离线 `pip --dry-run --require-hashes` 成功。
- 新增 `bootstrap_windows.ps1`、强化 `verify.ps1`，并生成 `output/environment_report.json`；Graphviz 优先本地 `tools\graphviz\bin\dot.exe`，其次系统 `dot.exe`，当前系统 Graphviz 15.1.0 的版本和 SHA-256 已记录。
- DeckIR 保持 1.9；新增严格的 `TemplateProfile 1.0`、`TemplatePlan 1.0`、独立 JSON Schema、原型评分、Pillow 字体测量、运行时容量回退、W201/W202 与模板感知 lint。
- 模板包限制覆盖 50 MB 压缩、500 MB 解包、200 页、5000 形状、路径穿越、宏、ActiveX、OLE、外部关系、XML/Content Types/关系目标和 XML 关系反向引用。
- 模板 renderer 复用 master/layout/theme，安全复制内部图片；不复制 transition、timing、notes、comments、外部超链接、chart/OLE/embedding；表格、图表和图形重绘保持原生可编辑。
- CLI、`scripts/generate.py`、`demo_e2e.py`、异步 Flask API 和工作台均支持可选 `.pptx`；Word 明确拒绝模板；下载资产固定为 output/lint/profile/plan/package-report。
- 图表实现了零轴、正/负/混合/全负范围、折线窄区间、1/2/2.5/5 漂亮刻度、字面量单位格式、长类目旋转/skip、折线 marker、饼图类别百分比及 HW-W10/W11/W12；Prompt 已加入图表选择规则。
- HIT 32 页真实模板生成 14 页验收 Deck。修复了模板 tags 关系被剥离后遗留空 `<p:tags/>` 导致 PowerPoint 拒绝打开的问题；PowerPoint 16 已成功打开并导出 14 页 PDF/PNG。自动结果为 0 Error、0 HW-W03、无 `XXXX`、每页密级完整、包关系通过。

### 降级或近似

- 14 页官方样例中 5 页使用安全原型替换，9 页因版式不支持或运行时容量不足使用同 master/layout/theme 下的 `master_redraw`，均记录 W201；缺失字体按字体聚合为 3 条 W202。
- HIT 联系表证明 PowerPoint 可打开、页面非空且无明显裁切，但该官方 IR 是版式边界样例，部分页面信息量较低，不代表真实业务内容质量。

### 阻塞待人输入

- 真实脱敏 docx/xlsx/pptx 各至少 3 个仍需业务侧提供；详见 `QUESTIONS.md`。
- PowerPoint 自动导出不替代最终审美签字；HIT 联系表位于 `output/hit_template_acceptance/powerpoint_visual_20260729/contact_sheet.png`。

### 仍不确定

- 当前系统已完成联网 Windows 环境的 wheelhouse dry-run，但“全新干净 Windows + 物理断网”的安装记录仍属于交付流程证据，不冒充为已完成。
- 最终 `verify.ps1` 已通过:四格式 word/deck stub E2E 全绿,覆盖率 parsers 93.64%、IR 93.99%、lint 93.89%、整体 89.04%,输出 `C0 verify passed`。联合模板/API/图表/renderer/lint/文档回归为 `179 passed`。
- 工作台已启动于 5056 并完成浏览器验收:1280px 桌面和 390px 窄屏均无横向溢出、文本裁切或控件重叠,控制台无 error/warning。

## 2026-07-29 PPT 双引擎融合与自主决策

### 已完成并通过验收

- 生产默认仍是 `DeckIR 1.9 -> python-pptx`；DeckIR、生产 API、工作台和 Windows 离线依赖闭包均未引入 Node、浏览器或 PptxGenJS。
- 模板输出新增 `template_structure.json`、`template_structure.md` 与 `template_replacement_audit.json`；受控下载和工作台均展示 structure/replacement-audit。审计只记录形状 ID、替换动作、哈希和检查状态，不记录正文或 Prompt。
- 模板感知 lint 以 Profile 的字体、色板和正文安全区为准；它只排除已归档的装饰形状，继续检查密级、动画、字号、溢出、业务对象重叠和页码。边界序列化的 4 EMU 容差防止精确安全线被误报。
- `scripts/template_inspect.py` 可独立运行并自行设置 `backend` 导入路径；新增 PNG 联系表、Office PDF/PNG 导出、视觉差异和 `manual_pending` 状态。
- 新建隔离的 `experiments/html2pptx/`。它只接收 Schema 已验证的 DeckIR，固定映射 HTML 后用 Playwright 测量，再由 PptxGenJS 生成可编辑对象；Node 25.2.1、PptxGenJS 4.0.1、Playwright 1.62.0、Sharp 0.35.3 均不属于生产依赖。
- 最终 HIT 源模板对照集位于 `output/html2pptx-final-office/`。Python 对三个固定样例均通过 Schema、包关系、lint、无 HW-W03/HW-W07、Office 打开和原生文本/表格/图表门禁；HTML 无模板样例可继续实验，但模板样例明确 `native_editability=false`，因此 `engine_assessment.json` 的推荐为 `keep_python`，没有自动切换生产。
- Office 已成功导出两套引擎共六份 PPTX 的 PDF/PNG 联系表；所有视觉状态为 `manual_pending`，没有人工基线时没有伪装成通过。
- 最终回归：`510 passed, 15 skipped`；可靠性门禁含工作台 UI 为 `525` 测试、`510` 通过、`15` 跳过；ruff 和 `git diff --check` 通过；`verify.ps1` C0 通过，parsers 93.75%、IR 93.99%、lint 94.24%、整体 89.25%。

### 阻塞待人输入

- 真实脱敏业务语料和最终 PowerPoint 审美签字仍按 `QUESTIONS.md` 执行。HTML 对照结论不会替代此人工门禁，也不会更改生产架构。

## 2026-07-29 PPT 图生成与视觉制作能力升级

### 已完成并通过验收

- DeckIR 已按契约先行升级并冻结为 2.0；1.4-1.9 仅在校验入口深拷贝迁移，不覆盖用户原文件。Schema、正反样例、迁移器、快照和 v2 样例矩阵均已通过。
- 新增独立 `AssetManifest 1.0` / `AssetUsageAudit 1.0`：PNG/JPEG/WebP 完整解码、EXIF 方向修正、元数据移除、SHA-256、去重、白名单/Office media 提取、20 MB/40MP/20 张/100 MB 限制及 A001-A006 已落地。合法 `image_ref` 嵌入真图，缺失引用以 A005 阻断，不再静默占位。
- 图片渲染支持 contain/cover、焦点、caption/credit/alt、`image_text` 和 2-4 图 `image_grid`；模板替换审计记录资产哈希、图片槽、fit/crop/focal 与回退原因。
- 新增 funnel/quadrant/cycle/matrix 原生可编辑信息图和 24 个企业语义 AutoShape 图标；architecture/process/timeline 保持原生 shape、文本框与 connector。
- 图表增加 scatter、combo、主次轴元数据、轴标题、显式数字格式、数据来源/口径/备注；新增 HW-W13-W16，且不合并、删除、排序或改写业务数据。
- 新增 `VisualPlan 1.0` / `VisualSelectionAudit 1.0` 和默认禁用的 `ImageProvider`。生成链路、CLI、API、工作台均输出并提供受控下载；模型仍只能产出通过 DeckIR Schema 的 JSON。
- API/工作台支持重复 `asset_files`、多图移除、Word 隔离、normalizing_assets/planning_visuals 阶段和资产/视觉审计下载。浏览器实测发现并修复同步 API 错误 payload 被前端降级为 E001 的问题；损坏模板现在正确显示 E003。
- 全量 pytest 为 `539 passed, 15 skipped`；可靠性报告 `output/qa/report.json` 为 554 项、539 通过、15 跳过、0 失败。`scripts/verify.py` 通过，覆盖率 parsers 93.75%、IR 93.82%、lint 94.26%、整体 88.72%；`verify.ps1` 通过，覆盖率 parsers 93.75%、IR 93.82%、lint 94.34%、整体 89.30%。ruff 与 `git diff --check` 全绿。
- 当前工作台已由仓库 `.venv` 启动于 `http://127.0.0.1:5056/static/index.html`。真实浏览器完成带图片 Deck 成功流和损坏模板失败流；图片资产清单、使用审计、VisualPlan、选择审计均可下载。默认 1265px 与 390px 视口无横向溢出、控件越界或文本裁切，控制台无 error/warning。

### 降级或近似

- combo 以两张对齐的 PowerPoint 原生图表实现：主轴 bar 与次轴 line 分别可编辑，不是单一 OOXML combo chart 对象，也没有把页面栅格化。
- 24 个语义图标是主题一致的基础 AutoShape 组合，不是复杂插画库。默认 `DisabledImageProvider` 保持离线生产边界，AI 生图未作为可用生产能力。
- Graphviz 在正式 `verify.ps1` 中检测到系统 `dot.exe`；未注入 PATH 的独立 pytest 子进程会发出确定性 fallback warning，但测试和输出不会失败。

### 阻塞待人输入

- 真实脱敏 docx/xlsx/pptx 和有明确版权/署名/替代文本的真实图片语料仍需业务侧提供，详见 `QUESTIONS.md`。
- PowerPoint 自动打开、lint、联系表和像素检查不替代目标字体环境下的最终内容与视觉签字。

### 仍不确定

- combo 的主次轴在当前自动结构回读中通过，但仍需用真实双量纲业务数据在目标 PowerPoint 版本中确认往返保存后的右轴语义和人工可读性。
- 当前 wheelhouse dry-run 与 Windows 本机门禁通过；全新干净 Windows 物理断网安装记录仍需按交付流程补证据，不能由本机结果替代。

### 2026-07-29 OLE 模板错误治理

- 实际模板触发 `E003: ppt/embeddings/oleobject1.bin`。确认这是既定安全门禁，而非 renderer 崩溃；OLE、宏、ActiveX 和外部关系继续禁止执行或复制。
- 包校验现在反查 `.rels`，把嵌入部件定位到具体幻灯片；同步 API 错误返回 `loc=template_file`、`retryable=false` 和“删除嵌入对象或转 PNG”的处理建议，工作台显示定位信息，不再提示稍后重试。
- 新增关系定位、API 结构化建议和前端定位文本回归，专项 `3 passed`；最终全量 pytest 为 `540 passed, 15 skipped`，ruff 与 `git diff --check` 通过。
- `verify.ps1` 完整通过：四格式 word/deck stub 链路全绿，覆盖率 parsers 93.75%、IR 93.82%、lint 94.34%、整体 89.32%，输出 `C0 verify passed`。
- 开发专用浏览器回归新增真实 OLE 上传拒绝场景；1280px 桌面与 390px 窄屏均确认显示 E003、`template_file`、引用页码和删除/转 PNG 建议，且不显示不存在的失败报告。报告位于 `output/qa/workbench-ui-ole/workbench_ui_report.json`。
- 清理了 5056 端口残留的旧工作台父子进程并以仓库 `.venv` 重启；实时 multipart 请求已确认当前服务返回第 1 页定位、`retryable=false` 和可执行建议，而非旧版笼统错误。

## 2026-07-29 上线前发布加固终验

### 已完成并通过验收

- Office 包预检修复了 ZIP 纯目录项 `ppt/embeddings/` 被误判为危险嵌入的问题。扫描器只忽略以 `/` 结尾的目录记录；未归属 `ppt/embeddings/*.xlsx`、任何 `.bin`、OLE、宏、ActiveX 和外部关系仍保持阻断，只有图表内部 `/package` 关系明确拥有的 `.xlsx` 可通过并接受嵌套 OOXML 安全检查。
- 界面文档回归已对齐当前 `start_workbench.ps1`、5056 端口和稳定失败字段，不再断言废弃的 5055 同步启动命令。包安全、文档和 HTML 对照专项 `18 passed`；HTML 无模板样例恢复为 `expand_html_experiment`，生产默认仍为 `python-pptx`。
- 最终全量 pytest 为 `573 passed, 15 skipped`，0 失败；Ruff 全绿，`git diff --check` 无空白错误。29 个 Windows CPython 3.12 依赖 wheel 通过 `--no-index --find-links wheelhouse --require-hashes --dry-run`。
- `verify.ps1` 完整通过：四格式 Word/Deck stub 链路全绿，Graphviz 使用 `C:\Program Files\Graphviz\bin\dot.exe`；覆盖率 parsers 93.51%、IR 93.82%、lint 94.34%、整体 89.10%，输出 `C0 verify passed`。
- 统一可靠性门禁位于 `output/qa/release-final/`：共 588 项，573 通过、15 跳过、0 失败；offline_verify、pytest、workbench_ui 三个 gate 均通过。浏览器在 1280x900 与 390x844 两个视口通过，无失败用例。

### 降级或近似

- 无本轮新增功能降级。普通 pytest 未注入 Graphviz PATH 时仍会记录确定性 fallback warning；正式 Windows 验收已识别并使用系统 Graphviz，不影响产物与门禁。

### 阻塞待人输入

- 真实脱敏业务语料、授权真实图片、PowerPoint 最终审美签字和全新 Windows 物理断网安装证据仍按 `QUESTIONS.md` 执行；自动绿色结果不替代这四项人工交付证据。

### 仍不确定

- 自动化范围内未发现未解决的软件失败。真实业务内容语义、目标字体环境审美及干净内网机器安装结果只能由后续人工验收确认。

## 2026-07-30 Windows 原生 EXE 与 NGA 配置

### 已完成并通过验收

- 从交付基线 `a99f4bf` 创建 `codex/windows-native-app`。新增 .NET 8 WPF 原生客户端，未使用 WebView2、Electron、PySide6 或第三方 UI 框架；生成、任务、设置、诊断、关于及 NGA 二级设置页已落地。
- 新增 `NgaHttpConfig 1.0`、OpenAI-compatible Chat Completions adapter、`GeneratorManager`、配置测试/激活 API、E010-E014、任务 generator 名称/修订快照和桌面会话鉴权。启用 NGA 后配置失败阻断，不回退 Stub。
- NGA Token 只由 WPF 写入 Windows Credential Manager `HuaweiDocumentGenerator/NGA`；非敏感配置位于 `%LOCALAPPDATA%\HuaweiDocumentGenerator\settings.json`。任务状态、失败报告、API 响应和便携包不包含凭据。
- 桌面宿主使用 Waitress 绑定 `127.0.0.1` 随机端口；一次性 bootstrap 由当前 Windows 用户 ACL 保护，后端读取即删。后端状态文件不含会话密钥，父进程退出后看门狗停止服务。
- 便携构建脚本锁定 .NET SDK 8.0.423、CPython embeddable 3.12.10 和 Graphviz 15.1.0，输出运行时清单、第三方许可、逐文件 SHA-256 与 ZIP SHA-256；生产包排除 xUnit/FlaUI/Playwright、缓存、设置、凭据和任务。
- 修复 Windows 异常退出生命周期：`OpenProcess` 能打开“已退出但句柄仍被测试框架持有”的进程，旧探测会误判为存活并留下 pythonw。当前同时使用 `GetExitCodeProcess == STILL_ACTIVE` 判定，并增加真实 Windows 进程句柄回归；WPF 测试后确认无遗留 `app.desktop_host`。
- 最新验证：`verify.ps1` 通过，Graphviz 使用 `C:\Program Files\Graphviz\bin\dot.exe`；覆盖率 parsers 93.51%、IR 93.82%、lint 94.34%、整体 88.82%。可靠性报告 `output/qa/windows-native-final/report.json` 为 613 项、598 通过、15 跳过、0 失败；1280x900 与 390x844 浏览器工作台均通过。WPF build 为 0 warning/0 error，xUnit/FlaUI 3/3 通过。

### 降级或近似

- NGA 首版仅支持 OpenAI-compatible、非流式 Chat Completions；自定义协议需新增 adapter。真实 NGA 未配置时默认 Stub，明确启用后不允许降级。
- WPF 自动化覆盖原生启动、导航、键盘可达和设置持久化；完整模板/图片/取消/恢复/审计下载已由后端与浏览器回归覆盖，并在本机 WPF Stub PPT 实跑通过。干净机器上的完整原生交互仍属于人工便携验收。

### 阻塞待人输入

- 真实 NGA 地址、模型、Token、证书链和实际响应兼容性冒烟；内网代码签名证书；干净物理断网 Windows 10/11 x64 便携包验收；真实脱敏业务语料、授权图片和 PowerPoint 最终审美签字，均见 `QUESTIONS.md`。

### 仍不确定

- 自动测试无法证明目标内网网关完全兼容 OpenAI Chat Completions，也不能替代企业签名策略、目标机安全软件兼容性和 Office 最终审美结论。

## 2026-08-01 仓库治理与分阶段架构重构

### 已完成并通过验收

- 在 `codex/repository-cleanup-20260731` 分支实施；基线提交为 `c9e000e99c30d1f680a0f5574296be0a51e02c1a`。迁移备份为 `dist/huawei_document_generator_windows_dev_20260731.zip`，SHA-256 为 `9aece8fcd42bfb555a21e26130238cdffb45080a280c08c292dacb09c9389245`。
- 新增 `REPO_AUDIT.md`、`ARCHITECTURE.md`、`REFACTOR_PLAN.md`、`docs/GIT_WORKFLOW.md` 和 `docs/GENERATION.md`；当前运行文档统一归入 `docs/`，设计记录归入 `docs/design/`，历史审计归入 `docs/history/2026-07/`。
- 删除无正式引用且已有替代实现的旧同步 Web、placeholder renderer、synthetic passing lint、空 storage 包和对应旧测试；删除由 Git 历史可恢复、已被当前文档替代的状态快照与周报。
- `scripts/demo_e2e.py` 现在始终执行真实 PPT lint；`--lint` 仅作为隐藏兼容参数保留。CLI Word/PPT 分支已拆分，API 的路由装配、请求处理、任务失败映射和产物上下文已按职责分解，未修改公共路由、IR、错误码或输出格式。
- 仓库治理特征测试锁定正式 `web_api` 入口、IR 唯一契约、HTML 实验隔离、文档归档位置和旧 Web 不得恢复。
- 全量 Python 回归为 `595 passed, 15 skipped`。`scripts/verify.py` 通过，覆盖率 parsers 93.51%、IR 93.82%、lint 94.30%、整体 88.95%；`verify.ps1` 通过，Graphviz 使用系统 `dot.exe`，整体覆盖率 89.17%。
- 可靠性报告 `output/qa/report.json` 共 610 项：595 通过、15 跳过、0 失败；JSON、JUnit 与静态 HTML 报告均已生成。
- WPF 使用锁定 .NET SDK 8.0.423 完成 Release 构建，0 warning/0 error；xUnit/FlaUI 3/3 通过。Ruff、`git diff --check`、删除入口残留扫描和敏感配置扫描均通过。

### 降级或近似

- `pptx_renderer.py`、`pptx_lint.py` 和 WPF `MainWindow.xaml.cs` 仍偏大。本轮没有为减少行数而切割高风险 Office/视觉逻辑；继续拆分须先补稳定的 Office 视觉 golden 与往返保存基线，已列为 R7 独立后续任务。
- Composio 未配置且本次未获得外部 issue/PR 权限，因此按 `codebase-migrate` 的本地小批次、逐批测试与回滚原则执行，没有创建远程事项。

### 阻塞待人输入

- 真实脱敏业务语料、授权图片、PowerPoint 最终视觉签字、全新 Windows 物理断网验收、真实 NGA 配置及正式代码签名仍按 `QUESTIONS.md` 执行，自动测试不能替代。
- 本地存在多个 `backup-*` 分支且没有 release tag；需人工确认保留策略后再归档或删除。Codex checkpoint refs 有宿主工具级损坏警告，本轮没有直接编辑 `.git`。

### 仍不确定

- 自动化范围内未发现重构引入的行为回归。目标内网 NGA 协议差异、终端安全软件对便携 EXE 的影响及 Office 最终审美，只能在交付环境继续确认。

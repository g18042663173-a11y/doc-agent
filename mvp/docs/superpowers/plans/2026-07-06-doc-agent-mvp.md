# Doc Agent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the local `doc-agent-mvp` project described in `PROJECT_SPEC.md`.

**Architecture:** The project uses a typed IR boundary: parsers produce `DocumentIR`, planners produce `DeckIR` or `WordIR`, validators enforce style rules, and renderers create editable PPTX/DOCX files. The default workflow is a pure-function stub flow; LangGraph is optional.

**Tech Stack:** Python 3.11+, Pydantic v2, Typer, python-pptx, python-docx, Streamlit, FastAPI, optional LangGraph/OpenAI-compatible client.

---

### Task 1: Scaffold And Tests

**Files:**
- Create: `tests/test_schemas.py`
- Create: `tests/test_md_parser.py`
- Create: `tests/test_mock_llm.py`
- Create: `tests/test_pptx_renderer.py`
- Create: `tests/test_docx_renderer.py`
- Create: `tests/test_workflow_generate.py`

- [ ] Write tests for the core MVP behaviors before production implementation.
- [ ] Run `pytest` and confirm the tests fail because the package does not exist yet.

### Task 2: Core Data And Parsing

**Files:**
- Create: `doc_agent/config.py`
- Create: `doc_agent/ir/schemas.py`
- Create: `doc_agent/parsers/*.py`
- Create: `doc_agent/utils/*.py`

- [ ] Implement settings, style loading, Pydantic schemas, JSON helpers, and md/docx/pptx parsers.
- [ ] Run schema and parser tests until they pass.

### Task 3: Planning, Validation, Rendering

**Files:**
- Create: `doc_agent/llm/*.py`
- Create: `doc_agent/planners/*.py`
- Create: `doc_agent/validators/*.py`
- Create: `doc_agent/renderers/*.py`

- [ ] Implement stub and legacy OpenAI-compatible LLM clients, prompt loading, planners, validators, PPTX renderer, DOCX renderer, and internal socket placeholders.
- [ ] Run mock and renderer tests until they pass.

### Task 4: Workflow And Entrypoints

**Files:**
- Create: `doc_agent/workflow.py`
- Create: `doc_agent/cli.py`
- Create: `doc_agent/__main__.py`
- Create: `app/streamlit_app.py`
- Create: `app/api.py`

- [ ] Implement `run_generate`, CLI commands, Streamlit upload/download, and FastAPI health/generate endpoints.
- [ ] Run workflow and CLI smoke tests.

### Task 5: Docs And Demo Verification

**Files:**
- Create: `README.md`
- Create: `.env.example`
- Create: `examples/input.md`
- Create: `examples/sample_deck_ir.json`
- Create: `examples/sample_word_ir.json`

- [ ] Write README setup/deployment notes.
- [ ] Run `pytest`, `python -m compileall doc_agent app`, and demo `md -> pptx/docx` commands.

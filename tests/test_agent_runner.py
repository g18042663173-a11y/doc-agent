from pathlib import Path

import pytest

from doc_agent.agent import AgentRunRequest, AgentRunner, friendly_error
from doc_agent.api.task_history import TaskHistoryManager


def test_agent_runner_generates_result_with_structured_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("PPT_RENDERER", "stub")
    source = tmp_path / "input.md"
    source.write_text("# Agent Runner\n\n- 解析\n- 规划\n- 渲染\n", encoding="utf-8")

    result = AgentRunner().run(
        AgentRunRequest(
            input_path=source,
            target="pptx",
            output_path=tmp_path / "out.pptx",
            slides=6,
        )
    )

    assert result.output_path is not None
    assert result.output_path.exists()
    assert result.workflow_state["target"] == "pptx"
    assert isinstance(result.warnings, list)


def test_agent_runner_records_failed_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    history = TaskHistoryManager(tmp_path / "data" / "tasks")
    history.create_task("task", "queued", 0, "任务已创建")

    runner = AgentRunner(task_history=history)
    runner.run_task(
        "task",
        AgentRunRequest(
            input_path=tmp_path / "missing.md",
            target="pptx",
            output_path=tmp_path / "out.pptx",
            slides=6,
        ),
    )

    task = history.get_task("task")
    assert task is not None
    assert task.status == "failed"
    assert task.friendly_error
    assert "不存在" in task.friendly_error or "检查" in task.friendly_error


def test_friendly_error_mentions_local_relay_connection() -> None:
    message = friendly_error(RuntimeError("Local relay LLM request failed: connection refused"))

    assert "模型服务连接失败" in message

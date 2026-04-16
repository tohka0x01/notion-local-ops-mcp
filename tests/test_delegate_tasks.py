import time
from pathlib import Path

from notion_local_ops_mcp.executors import ExecutorRegistry
from notion_local_ops_mcp.tasks import TaskStore


def test_executor_registry_prefers_codex_when_present(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "state")
    registry = ExecutorRegistry(
        store=store,
        codex_command="python3 -c \"print('codex')\"",
        claude_command="python3 -c \"print('claude')\"",
    )

    task = registry.submit(task="say hi", executor="auto", cwd=tmp_path, timeout=5)
    loaded = store.get(task["task_id"])

    assert loaded["executor"] == "codex"


def test_task_store_persists_status_updates(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "state")
    created = store.create(task="check", executor="codex", cwd=str(tmp_path))
    store.update(created["task_id"], status="running")
    loaded = store.get(created["task_id"])

    assert loaded["status"] == "running"


def test_submitted_task_eventually_succeeds(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "state")
    registry = ExecutorRegistry(
        store=store,
        codex_command="python3 -c \"print('done')\"",
        claude_command="python3 -c \"print('claude')\"",
    )

    task = registry.submit(task="finish", executor="codex", cwd=tmp_path, timeout=5)

    for _ in range(50):
        loaded = store.get(task["task_id"])
        if loaded["status"] == "succeeded":
            break
        time.sleep(0.05)

    loaded = store.get(task["task_id"])
    assert loaded["status"] == "succeeded"
    assert "done" in store.read_stdout(task["task_id"])


def test_cancel_marks_long_running_task_cancelled(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "state")
    registry = ExecutorRegistry(
        store=store,
        codex_command="python3 -c \"import time; time.sleep(2)\"",
        claude_command="python3 -c \"print('claude')\"",
    )

    task = registry.submit(task="cancel", executor="codex", cwd=tmp_path, timeout=5)
    cancelled = registry.cancel(task["task_id"])
    result = registry.wait(task["task_id"], timeout=2, poll_interval=0.05)

    assert cancelled["cancelled"] is True
    assert result["status"] == "cancelled"
    assert result["completed"] is True


def test_wait_returns_completed_task_metadata(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "state")
    registry = ExecutorRegistry(
        store=store,
        codex_command="python3 -c \"print('done')\"",
        claude_command="python3 -c \"print('claude')\"",
    )

    task = registry.submit(task="finish", executor="codex", cwd=tmp_path, timeout=5)
    result = registry.wait(task["task_id"], timeout=2, poll_interval=0.05)

    assert result["status"] == "succeeded"
    assert "done" in result["stdout_tail"]
    assert result["completed"] is True


def test_submit_command_runs_shell_task_in_background(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "state")
    registry = ExecutorRegistry(
        store=store,
        codex_command="python3 -c \"print('codex')\"",
        claude_command="python3 -c \"print('claude')\"",
    )

    task = registry.submit_command(
        command="python3 -c \"print('shell')\"",
        cwd=tmp_path,
        timeout=5,
    )
    result = registry.wait(task["task_id"], timeout=2, poll_interval=0.05)

    assert result["executor"] == "shell"
    assert result["status"] == "succeeded"
    assert "shell" in result["stdout_tail"]
    assert result["completed"] is True


def test_cancel_marks_background_command_cancelled(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "state")
    registry = ExecutorRegistry(
        store=store,
        codex_command="python3 -c \"print('codex')\"",
        claude_command="python3 -c \"print('claude')\"",
    )

    task = registry.submit_command(
        command="python3 -c \"import time; time.sleep(2)\"",
        cwd=tmp_path,
        timeout=5,
    )
    cancelled = registry.cancel(task["task_id"])
    result = registry.wait(task["task_id"], timeout=2, poll_interval=0.05)

    assert cancelled["cancelled"] is True
    assert cancelled["status"] == "cancelled"
    assert result["status"] == "cancelled"
    assert result["completed"] is True


def test_submit_persists_structured_delegate_metadata(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "state")
    registry = ExecutorRegistry(
        store=store,
        codex_command="python3 -c \"print('codex')\"",
        claude_command="python3 -c \"print('claude')\"",
    )

    task = registry.submit(
        task="Implement the fallback flow",
        goal="Ship a working fallback task runner",
        executor="codex",
        cwd=tmp_path,
        timeout=5,
        context_files=["README.md"],
        acceptance_criteria=["Tool returns structured status"],
        verification_commands=["pytest -q"],
        commit_mode="allowed",
    )
    stored = store.get(task["task_id"])

    assert stored["goal"] == "Ship a working fallback task runner"
    assert stored["acceptance_criteria"] == ["Tool returns structured status"]
    assert stored["verification_commands"] == ["pytest -q"]
    assert stored["commit_mode"] == "allowed"


def test_build_prompt_includes_structured_delegate_sections(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "state")
    registry = ExecutorRegistry(
        store=store,
        codex_command="python3 -c \"print('codex')\"",
        claude_command="python3 -c \"print('claude')\"",
    )

    prompt = registry._build_prompt(
        task="Implement the fallback flow",
        goal="Ship a working fallback task runner",
        context_files=["README.md", "src/app.py"],
        acceptance_criteria=["Tool returns structured status", "Tests pass"],
        verification_commands=["pytest -q", "python -m compileall src tests"],
        commit_mode="required",
    )

    assert "Goal:" in prompt
    assert "Ship a working fallback task runner" in prompt
    assert "Acceptance criteria:" in prompt
    assert "- Tool returns structured status" in prompt
    assert "Verification commands:" in prompt
    assert "- pytest -q" in prompt
    assert "Commit mode: required" in prompt

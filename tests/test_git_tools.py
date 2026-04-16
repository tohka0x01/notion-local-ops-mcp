from __future__ import annotations

import subprocess
from pathlib import Path

from notion_local_ops_mcp.gitops import git_commit, git_diff, git_log, git_status


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True, capture_output=True, text=True)


def test_git_status_reports_staged_unstaged_and_untracked(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    tracked.write_text("two\n", encoding="utf-8")
    staged = tmp_path / "staged.txt"
    staged.write_text("stage me\n", encoding="utf-8")
    subprocess.run(["git", "add", "staged.txt"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "new.txt").write_text("new\n", encoding="utf-8")

    result = git_status(cwd=tmp_path)

    assert result["success"] is True
    assert result["clean"] is False
    assert "tracked.txt" in result["unstaged"]
    assert "staged.txt" in result["staged"]
    assert "new.txt" in result["untracked"]


def test_git_diff_returns_unified_diff(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    target = tmp_path / "app.py"
    target.write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    target.write_text("after\n", encoding="utf-8")

    result = git_diff(cwd=tmp_path)

    assert result["success"] is True
    assert result["files"] == ["app.py"]
    assert "-before" in result["diff"]
    assert "+after" in result["diff"]


def test_git_commit_can_stage_paths_and_return_commit_metadata(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    target = tmp_path / "feature.txt"
    target.write_text("hello\n", encoding="utf-8")

    result = git_commit(cwd=tmp_path, message="feat: add feature file", paths=["feature.txt"])

    assert result["success"] is True
    assert len(result["commit"]) == 40
    assert result["summary"] == "feat: add feature file"


def test_git_log_returns_recent_commits(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    target = tmp_path / "note.txt"
    target.write_text("v1\n", encoding="utf-8")
    git_commit(cwd=tmp_path, message="feat: add note", paths=["note.txt"])
    target.write_text("v2\n", encoding="utf-8")
    git_commit(cwd=tmp_path, message="fix: update note", paths=["note.txt"])

    result = git_log(cwd=tmp_path, limit=2)

    assert result["success"] is True
    assert [entry["summary"] for entry in result["entries"]] == ["fix: update note", "feat: add note"]

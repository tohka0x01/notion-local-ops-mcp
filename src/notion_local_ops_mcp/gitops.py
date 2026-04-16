from __future__ import annotations

import subprocess
from pathlib import Path


def _error(code: str, message: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    payload.update(extra)
    return payload


def _cwd_error(cwd: Path) -> dict[str, object] | None:
    if not cwd.exists():
        return _error("cwd_not_found", f"Working directory not found: {cwd}", cwd=str(cwd))
    if not cwd.is_dir():
        return _error("cwd_not_directory", f"Working directory is not a directory: {cwd}", cwd=str(cwd))
    return None


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )


def _require_repo(cwd: Path) -> tuple[Path, str] | dict[str, object]:
    cwd_error = _cwd_error(cwd)
    if cwd_error:
        return cwd_error

    root_result = _run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    if root_result.returncode != 0:
        return _error(
            "not_a_git_repo",
            "Working directory is not inside a git repository.",
            cwd=str(cwd),
            stderr=root_result.stderr.strip(),
        )

    branch_result = _run_git(["branch", "--show-current"], cwd=cwd)
    branch = branch_result.stdout.strip() or "HEAD"
    return Path(root_result.stdout.strip()), branch


def _normalize_pathspec(pathspec: str, *, cwd: Path, repo_root: Path) -> str:
    raw = Path(pathspec).expanduser()
    absolute = (cwd / raw).resolve(strict=False) if not raw.is_absolute() else raw.resolve(strict=False)
    try:
        return str(absolute.relative_to(repo_root))
    except ValueError:
        return pathspec


def git_status(*, cwd: Path) -> dict[str, object]:
    repo_info = _require_repo(cwd)
    if isinstance(repo_info, dict):
        return repo_info
    repo_root, branch = repo_info

    result = _run_git(["status", "--short", "--branch"], cwd=cwd)
    if result.returncode != 0:
        return _error("git_status_failed", result.stderr.strip() or "git status failed.", cwd=str(cwd))

    staged: list[str] = []
    unstaged: list[str] = []
    untracked: list[str] = []
    entries: list[dict[str, object]] = []

    for line in result.stdout.splitlines():
        if line.startswith("## "):
            continue
        code = line[:2]
        raw_path = line[3:]
        path = raw_path.split(" -> ", 1)[-1]
        entries.append(
            {
                "path": path,
                "index_status": code[0],
                "worktree_status": code[1],
            }
        )
        if code == "??":
            untracked.append(path)
            continue
        if code[0] != " ":
            staged.append(path)
        if code[1] != " ":
            unstaged.append(path)

    return {
        "success": True,
        "cwd": str(cwd),
        "repo_root": str(repo_root),
        "branch": branch,
        "clean": not entries,
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "entries": entries,
    }


def git_diff(
    *,
    cwd: Path,
    staged: bool = False,
    paths: list[str] | None = None,
    max_bytes: int = 65536,
) -> dict[str, object]:
    repo_info = _require_repo(cwd)
    if isinstance(repo_info, dict):
        return repo_info
    repo_root, _branch = repo_info
    normalized_paths = [_normalize_pathspec(path, cwd=cwd, repo_root=repo_root) for path in (paths or [])]

    args = ["diff", "--no-color"]
    if staged:
        args.append("--cached")
    if normalized_paths:
        args.extend(["--", *normalized_paths])

    result = _run_git(args, cwd=cwd)
    if result.returncode != 0:
        return _error("git_diff_failed", result.stderr.strip() or "git diff failed.", cwd=str(cwd))

    files_args = ["diff", "--name-only"]
    if staged:
        files_args.append("--cached")
    if normalized_paths:
        files_args.extend(["--", *normalized_paths])
    files_result = _run_git(files_args, cwd=cwd)
    files = [line for line in files_result.stdout.splitlines() if line]

    encoded = result.stdout.encode("utf-8")
    truncated = len(encoded) > max_bytes
    diff_text = encoded[:max_bytes].decode("utf-8", errors="ignore") if truncated else result.stdout

    return {
        "success": True,
        "cwd": str(cwd),
        "repo_root": str(repo_root),
        "staged": staged,
        "files": files,
        "diff": diff_text,
        "truncated": truncated,
    }


def git_commit(
    *,
    cwd: Path,
    message: str,
    paths: list[str] | None = None,
    stage_all: bool = False,
) -> dict[str, object]:
    repo_info = _require_repo(cwd)
    if isinstance(repo_info, dict):
        return repo_info
    repo_root, branch = repo_info
    normalized_paths = [_normalize_pathspec(path, cwd=cwd, repo_root=repo_root) for path in (paths or [])]

    if stage_all:
        stage_result = _run_git(["add", "-A"], cwd=cwd)
        if stage_result.returncode != 0:
            return _error("git_add_failed", stage_result.stderr.strip() or "git add -A failed.", cwd=str(cwd))
    elif normalized_paths:
        stage_result = _run_git(["add", "--", *normalized_paths], cwd=cwd)
        if stage_result.returncode != 0:
            return _error("git_add_failed", stage_result.stderr.strip() or "git add failed.", cwd=str(cwd))

    staged_result = _run_git(["diff", "--cached", "--name-only"], cwd=cwd)
    staged_files = [line for line in staged_result.stdout.splitlines() if line]
    if not staged_files:
        return _error("nothing_to_commit", "No staged changes to commit.", cwd=str(cwd))

    commit_result = _run_git(["commit", "-m", message], cwd=cwd)
    if commit_result.returncode != 0:
        return _error(
            "git_commit_failed",
            commit_result.stderr.strip() or commit_result.stdout.strip() or "git commit failed.",
            cwd=str(cwd),
        )

    head_result = _run_git(["rev-parse", "HEAD"], cwd=cwd)
    commit_hash = head_result.stdout.strip()
    return {
        "success": True,
        "cwd": str(cwd),
        "repo_root": str(repo_root),
        "branch": branch,
        "commit": commit_hash,
        "short_commit": commit_hash[:7],
        "summary": message,
        "files": staged_files,
    }


def git_log(*, cwd: Path, limit: int = 10) -> dict[str, object]:
    repo_info = _require_repo(cwd)
    if isinstance(repo_info, dict):
        return repo_info
    repo_root, branch = repo_info

    result = _run_git(
        ["log", f"--max-count={max(limit, 1)}", "--pretty=format:%H%x1f%h%x1f%s%x1f%an%x1f%aI"],
        cwd=cwd,
    )
    if result.returncode != 0:
        return _error("git_log_failed", result.stderr.strip() or "git log failed.", cwd=str(cwd))

    entries: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        commit, short_commit, summary, author, committed_at = line.split("\x1f")
        entries.append(
            {
                "commit": commit,
                "short_commit": short_commit,
                "summary": summary,
                "author": author,
                "committed_at": committed_at,
            }
        )

    return {
        "success": True,
        "cwd": str(cwd),
        "repo_root": str(repo_root),
        "branch": branch,
        "entries": entries,
    }

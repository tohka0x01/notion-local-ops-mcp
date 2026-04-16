from __future__ import annotations

import shlex
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .tasks import TaskStore


TERMINAL_TASK_STATUSES = {"succeeded", "failed", "cancelled"}
ALLOWED_COMMIT_MODES = {"allowed", "required", "forbidden"}


def _command_available(command: str | None) -> bool:
    if not command:
        return False
    parts = shlex.split(command)
    if not parts:
        return False
    binary = parts[0]
    if Path(binary).exists():
        return True
    return shutil.which(binary) is not None


def _summarize(stdout: str, stderr: str) -> str:
    for candidate in (stdout.strip(), stderr.strip()):
        if candidate:
            return candidate.splitlines()[-1]
    return ""


def _cwd_error(command: str, cwd: Path) -> dict[str, object] | None:
    if not cwd.exists():
        return {
            "success": False,
            "error": {
                "code": "cwd_not_found",
                "message": f"Working directory not found: {cwd}",
            },
            "cwd": str(cwd),
            "command": command,
        }
    if not cwd.is_dir():
        return {
            "success": False,
            "error": {
                "code": "cwd_not_directory",
                "message": f"Working directory is not a directory: {cwd}",
            },
            "cwd": str(cwd),
            "command": command,
        }
    return None


@dataclass(frozen=True)
class Invocation:
    args: list[str] | str
    use_shell: bool


class ExecutorRegistry:
    def __init__(self, *, store: TaskStore, codex_command: str | None, claude_command: str | None) -> None:
        self.store = store
        self.codex_command = codex_command
        self.claude_command = claude_command
        self._lock = threading.Lock()
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._cancel_events: dict[str, threading.Event] = {}

    def submit(
        self,
        *,
        task: str | None,
        goal: str | None = None,
        executor: str,
        cwd: Path,
        timeout: int,
        context_files: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        verification_commands: list[str] | None = None,
        commit_mode: str = "allowed",
    ) -> dict[str, object]:
        normalized_task = (task or "").strip()
        normalized_goal = (goal or "").strip()
        if not normalized_task and not normalized_goal:
            raise ValueError("delegate_task requires task or goal.")
        if commit_mode not in ALLOWED_COMMIT_MODES:
            raise ValueError(f"Unsupported commit_mode: {commit_mode}")

        chosen_executor, command = self._resolve_executor(executor)
        created = self.store.create(
            task=normalized_task or normalized_goal,
            executor=chosen_executor,
            cwd=str(cwd),
            timeout=timeout,
            context_files=context_files,
            metadata={
                "goal": normalized_goal or None,
                "acceptance_criteria": acceptance_criteria or [],
                "verification_commands": verification_commands or [],
                "commit_mode": commit_mode,
            },
        )
        cancel_event = threading.Event()
        with self._lock:
            self._cancel_events[created["task_id"]] = cancel_event
        thread = threading.Thread(
            target=self._run_task,
            args=(
                created["task_id"],
                chosen_executor,
                command,
                normalized_task or None,
                normalized_goal or None,
                cwd,
                timeout,
                cancel_event,
                context_files or [],
                acceptance_criteria or [],
                verification_commands or [],
                commit_mode,
            ),
            daemon=True,
        )
        thread.start()
        return {
            "task_id": created["task_id"],
            "executor": chosen_executor,
            "status": created["status"],
        }

    def submit_command(
        self,
        *,
        command: str,
        cwd: Path,
        timeout: int,
    ) -> dict[str, object]:
        cwd_error = _cwd_error(command, cwd)
        if cwd_error:
            return cwd_error
        created = self.store.create(
            task=command,
            executor="shell",
            cwd=str(cwd),
            timeout=timeout,
            context_files=[],
        )
        cancel_event = threading.Event()
        with self._lock:
            self._cancel_events[created["task_id"]] = cancel_event
        thread = threading.Thread(
            target=self._run_command_task,
            args=(created["task_id"], command, cwd, timeout, cancel_event),
            daemon=True,
        )
        thread.start()
        return {
            "task_id": created["task_id"],
            "executor": "shell",
            "status": created["status"],
        }

    def get(self, task_id: str) -> dict[str, object]:
        meta = self.store.get(task_id)
        meta["summary"] = self.store.read_summary(task_id)
        meta["stdout_tail"] = self.store.read_stdout(task_id)[-4000:]
        meta["stderr_tail"] = self.store.read_stderr(task_id)[-4000:]
        meta["artifacts"] = []
        meta["completed"] = meta["status"] in TERMINAL_TASK_STATUSES
        return meta

    def wait(self, task_id: str, timeout: float, poll_interval: float = 0.5) -> dict[str, object]:
        deadline = time.monotonic() + max(timeout, 0)
        interval = max(poll_interval, 0.05)
        while True:
            meta = self.get(task_id)
            if meta["completed"]:
                meta["timed_out"] = False
                return meta
            if time.monotonic() >= deadline:
                meta["timed_out"] = True
                return meta
            time.sleep(interval)

    def cancel(self, task_id: str) -> dict[str, object]:
        with self._lock:
            cancel_event = self._cancel_events.get(task_id)
            process = self._processes.get(task_id)
        if cancel_event is not None:
            cancel_event.set()
        if process is not None and process.poll() is None:
            process.kill()
        updated = self.store.update(task_id, status="cancelled")
        return {
            "task_id": task_id,
            "status": updated["status"],
            "cancelled": True,
        }

    def _resolve_executor(self, executor: str) -> tuple[str, str]:
        if executor == "codex":
            if not _command_available(self.codex_command):
                raise RuntimeError("Codex command is not available.")
            return "codex", self.codex_command or ""
        if executor == "claude-code":
            if not _command_available(self.claude_command):
                raise RuntimeError("Claude Code command is not available.")
            return "claude-code", self.claude_command or ""
        if _command_available(self.codex_command):
            return "codex", self.codex_command or ""
        if _command_available(self.claude_command):
            return "claude-code", self.claude_command or ""
        raise RuntimeError("No delegate executor command is available.")

    def _run_task(
        self,
        task_id: str,
        executor_name: str,
        command: str,
        task: str | None,
        goal: str | None,
        cwd: Path,
        timeout: int,
        cancel_event: threading.Event,
        context_files: list[str],
        acceptance_criteria: list[str],
        verification_commands: list[str],
        commit_mode: str,
    ) -> None:
        if cancel_event.is_set():
            self.store.update(task_id, status="cancelled")
            return

        self.store.update(task_id, status="running")
        invocation = self._build_invocation(
            executor_name=executor_name,
            command=command,
            task=task,
            goal=goal,
            cwd=cwd,
            context_files=context_files,
            acceptance_criteria=acceptance_criteria,
            verification_commands=verification_commands,
            commit_mode=commit_mode,
        )
        process = subprocess.Popen(
            invocation.args,
            cwd=str(cwd),
            shell=invocation.use_shell,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        with self._lock:
            self._processes[task_id] = process

        if cancel_event.is_set() and process.poll() is None:
            process.kill()

        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            self.store.write_logs(task_id, stdout=stdout, stderr=stderr)
            self.store.write_summary(task_id, _summarize(stdout, stderr))
            self.store.update(task_id, status="failed", timed_out=True)
            return
        finally:
            with self._lock:
                self._processes.pop(task_id, None)

        self.store.write_logs(task_id, stdout=stdout, stderr=stderr)
        self.store.write_summary(task_id, _summarize(stdout, stderr))

        if cancel_event.is_set() or self.store.get(task_id)["status"] == "cancelled":
            self.store.update(task_id, status="cancelled")
            return

        status = "succeeded" if process.returncode == 0 else "failed"
        self.store.update(task_id, status=status, exit_code=process.returncode)

    def _run_command_task(
        self,
        task_id: str,
        command: str,
        cwd: Path,
        timeout: int,
        cancel_event: threading.Event,
    ) -> None:
        if cancel_event.is_set():
            self.store.update(task_id, status="cancelled")
            return

        self.store.update(task_id, status="running")
        try:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                shell=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            self.store.write_logs(task_id, stdout="", stderr=str(exc))
            self.store.write_summary(task_id, str(exc))
            self.store.update(task_id, status="failed")
            return
        with self._lock:
            self._processes[task_id] = process

        if cancel_event.is_set() and process.poll() is None:
            process.kill()

        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            self.store.write_logs(task_id, stdout=stdout, stderr=stderr)
            self.store.write_summary(task_id, _summarize(stdout, stderr))
            self.store.update(task_id, status="failed", timed_out=True)
            return
        finally:
            with self._lock:
                self._processes.pop(task_id, None)

        self.store.write_logs(task_id, stdout=stdout, stderr=stderr)
        self.store.write_summary(task_id, _summarize(stdout, stderr))

        if cancel_event.is_set() or self.store.get(task_id)["status"] == "cancelled":
            self.store.update(task_id, status="cancelled")
            return

        status = "succeeded" if process.returncode == 0 else "failed"
        self.store.update(task_id, status=status, exit_code=process.returncode)

    def _build_invocation(
        self,
        *,
        executor_name: str,
        command: str,
        task: str | None,
        goal: str | None,
        cwd: Path,
        context_files: list[str],
        acceptance_criteria: list[str],
        verification_commands: list[str],
        commit_mode: str,
    ) -> Invocation:
        prompt = self._build_prompt(
            task=task,
            goal=goal,
            context_files=context_files,
            acceptance_criteria=acceptance_criteria,
            verification_commands=verification_commands,
            commit_mode=commit_mode,
        )
        if executor_name == "codex":
            parts = shlex.split(command)
            if Path(parts[0]).name == "codex":
                args = [
                    *parts,
                    "exec",
                    "--dangerously-bypass-approvals-and-sandbox",
                    "-C",
                    str(cwd),
                ]
                if not (cwd / ".git").exists():
                    args.append("--skip-git-repo-check")
                args.append(prompt)
                return Invocation(args=args, use_shell=False)
        if executor_name == "claude-code":
            parts = shlex.split(command)
            if Path(parts[0]).name == "claude":
                return Invocation(
                    args=[
                        *parts,
                        "--print",
                        "--dangerously-skip-permissions",
                        "--permission-mode",
                        "bypassPermissions",
                        "--output-format",
                        "text",
                        prompt,
                    ],
                    use_shell=False,
                )
        return Invocation(args=command, use_shell=True)

    def _build_prompt(
        self,
        *,
        task: str | None,
        goal: str | None,
        context_files: list[str],
        acceptance_criteria: list[str],
        verification_commands: list[str],
        commit_mode: str,
    ) -> str:
        lines: list[str] = []
        if goal:
            lines.extend(["Goal:", goal, ""])
        if task:
            lines.extend(["Task:", task, ""])
        if acceptance_criteria:
            lines.append("Acceptance criteria:")
            lines.extend(f"- {item}" for item in acceptance_criteria)
            lines.append("")
        if verification_commands:
            lines.append("Verification commands:")
            lines.extend(f"- {item}" for item in verification_commands)
            lines.append("")
        lines.append(f"Commit mode: {commit_mode}")
        if context_files:
            lines.extend(["", "Context files:"])
            lines.extend(f"- {path}" for path in context_files)
        return "\n".join(lines)

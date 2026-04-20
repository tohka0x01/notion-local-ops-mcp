# AGENTS.md — notion-local-ops-mcp

## What is this?

A local MCP (Model Context Protocol) server that gives Notion AI agents the ability to operate on your local filesystem and shell. Built with **Python 3.11+** and **FastMCP**, served over SSE on `http://127.0.0.1:8766/mcp`.

## Architecture

```
Notion Agent ──SSE──▶ FastMCP Server (uvicorn)
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    Direct Tools     Shell Tool     Delegate Tasks
   (files/search)   (run_command)  (codex/claude-code)
```

### Source layout

```
src/notion_local_ops_mcp/
├── server.py      # FastMCP app, tool registration, uvicorn entrypoint
├── config.py      # All env-var driven settings (host, port, paths, timeouts…)
├── pathing.py     # Path resolution: relative → absolute under WORKSPACE_ROOT
├── files.py       # list_files, read_text/read_file(s), write_file, replace_in_file
├── search.py      # search/search_files/glob_files/grep_files implementations
├── shell.py       # run_command — subprocess with timeout
├── tasks.py       # TaskStore — persistent task metadata & logs on disk
└── executors.py   # ExecutorRegistry — async delegate_task via codex / claude-code
```

## Tools exposed

| Tool | Purpose |
|---|---|
| `server_info` | Inspect runtime config and available MCP tools |
| `set_default_cwd` / `get_default_cwd` | Manage session default working directory |
| `list_files` | List directory contents (flat or recursive) |
| `search` | Canonical unified query tool (glob/regex/text) |
| `glob_files` / `grep_files` / `search_files` | Legacy compatibility aliases for `search` |
| `read_text` | Canonical single/batch text reader with line pagination |
| `read_file` / `read_files` | Legacy compatibility aliases for `read_text` |
| `write_file` | Create or overwrite a file (`dry_run` supported) |
| `replace_in_file` | Replace unique/all exact text fragments (`dry_run` supported) |
| `apply_patch` | Apply codex-style patch with validation/dry-run support |
| `git_status` / `git_diff` / `git_commit` / `git_log` / `git_show` / `git_blame` | Structured git workflows |
| `run_command` | Execute a shell command (sync or background) |
| `run_command_stream` | Start long shell command and poll via task id |
| `delegate_task` | Submit long-running task to codex/claude-code with optional structured output parsing |
| `get_task` / `wait_task` | Poll or block on delegated/background task completion |
| `cancel_task` | Cancel a running delegated task |
| `purge_tasks` | GC old task logs under `STATE_DIR/tasks` |

## Key concepts

- **WORKSPACE_ROOT** — Relative-path anchor and default cwd only (not a sandbox boundary). Set via `NOTION_LOCAL_OPS_WORKSPACE_ROOT`; defaults to `$HOME`.
- **Bearer auth** — Optional `NOTION_LOCAL_OPS_AUTH_TOKEN`; if set, every request must include a matching `Authorization: Bearer <token>` header.
- **Delegate executors** — `delegate_task` spawns a background thread running either OpenAI Codex CLI or Claude Code CLI. The executor is chosen automatically (`auto`) or explicitly (`codex` / `claude-code`). Task state is persisted under `STATE_DIR/tasks/<id>/`.
- **Safety** — `replace_in_file` enforces single-match uniqueness. `read_file` caps output at 200 lines / 32 KB. Binary files are rejected.

## Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `NOTION_LOCAL_OPS_HOST` | `127.0.0.1` | Bind address |
| `NOTION_LOCAL_OPS_PORT` | `8766` | Bind port |
| `NOTION_LOCAL_OPS_WORKSPACE_ROOT` | `$HOME` | Root for relative path resolution |
| `NOTION_LOCAL_OPS_STATE_DIR` | `~/.notion-local-ops-mcp` | Persistent task metadata |
| `NOTION_LOCAL_OPS_AUTH_TOKEN` | *(empty)* | Bearer token (auth disabled if empty) |
| `NOTION_LOCAL_OPS_CODEX_COMMAND` | `codex` | Codex CLI binary |
| `NOTION_LOCAL_OPS_CLAUDE_COMMAND` | `claude` | Claude Code CLI binary |
| `NOTION_LOCAL_OPS_COMMAND_TIMEOUT` | `120` | Default shell command timeout (seconds) |
| `NOTION_LOCAL_OPS_DELEGATE_TIMEOUT` | `1800` | Default delegate task timeout (seconds) |

## Quick start

```bash
cp .env.example .env   # edit values
python -m venv .venv && source .venv/bin/activate
pip install -e .
notion-local-ops-mcp   # starts SSE server on :8766
```

## Dev

```bash
pip install -e ".[dev]"
pytest
```

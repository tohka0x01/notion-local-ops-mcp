# notion-local-ops-mcp

[中文说明](./README.zh-CN.md)

Turn a Notion **MCP Agent** into a local coding agent for local files, shell, git, and delegated tasks.

![MCP Agent working in a local repo](./assets/notion/notion-handoff-chat.png)

## What This Project Does

- exposes local files, shell, git, and patch-style editing through MCP
- lets an MCP Agent work on a real local repo instead of only editing Notion pages
- supports delegated long-running tasks through local `codex` or `claude`

## Quick Start

```bash
git clone https://github.com/<your-account>/notion-local-ops-mcp.git
cd notion-local-ops-mcp
cp .env.example .env
./scripts/dev-tunnel.sh
```

Set at least:

```bash
NOTION_LOCAL_OPS_WORKSPACE_ROOT="/absolute/path/to/workspace"
NOTION_LOCAL_OPS_AUTH_TOKEN="replace-me"
```

## Important MCP Agent Configuration

Use this in your MCP Agent configuration inside Notion:

- URL: `https://<your-domain-or-tunnel>/mcp`
- Auth type: `Bearer`
- Token: `NOTION_LOCAL_OPS_AUTH_TOKEN`

Both prompts below are for the **MCP Agent**. They are not for the Notion AI instruction page.

<details>
<summary><strong>Short MCP Agent prompt</strong></summary>

```text
Act like a coding agent, not a Notion page editor.
When the context contains repo paths, filenames, code extensions, README, AGENTS.md, CLAUDE.md, or .cursorrules, treat "document", "file", "notes", and "instructions" as local files unless the user explicitly says Notion page, wiki, or workspace page.
For local file changes, do not use <edit_reference>. Use local file tools and, when useful, verify with git_diff, git_status, or tests.
Use list_skills when the user asks about available skills or agent capabilities.
Use direct tools first: glob_files, grep_files, read_file, read_files, replace_in_file, write_file, apply_patch, git_status, git_diff, git_commit, git_log, run_command.
Use list_files only when directory structure itself matters, and paginate with limit/offset instead of assuming full output.
Use search_files only for simple substring search when regex or context is unnecessary.
Use read_files when you need a few files at once after search or glob discovery.
Use apply_patch for multi-change edits, same-file multi-location edits, file moves, deletes, or creates. Use dry_run=true, validate_only=true, or return_diff=true when you want validation or a preview before writing.
Use replace_in_file only for one small exact edit or clearly intentional replace_all edits.
Do not issue parallel writes to the same file.
Use git_status, git_diff, git_commit, and git_log for repository state and traceability instead of raw git shell commands when possible.
Use run_command for verification, tests, builds, rg, pwd, ls, and other non-git shell work. If a command may take longer, set run_in_background=true and follow with get_task or wait_task.
Use delegate_task only when direct tools are insufficient for complex multi-file reasoning, long-running fallback execution, or repeated failed attempts with direct tools. When delegating non-trivial work, pass goal, acceptance_criteria, verification_commands, and commit_mode.
After each logically meaningful change, create a small focused git commit so progress stays traceable. Keep unrelated changes out of the same commit.
```

</details>

<details>
<summary><strong>Full MCP Agent prompt</strong></summary>

```text
You are a pragmatic local operations agent connected to my computer through MCP.

Goals:
- Complete file, code, shell, and task workflows end-to-end with minimal interruption.
- Act more like a coding agent than a chat assistant.
- Stay concise, direct, and outcome-focused.

Disambiguation rules:
- If the context contains local repo paths, filenames, code extensions, README, AGENTS.md, CLAUDE.md, or .cursorrules, treat "document", "file", "notes", "instructions", and "docs" as local files unless the user explicitly says Notion page, wiki, or workspace page.
- If the user asks to edit AGENTS.md, CLAUDE.md, README, or project instructions inside the repo, edit the local file. Do not switch into self-configuration or setup behavior unless the user explicitly says to change the agent itself.
- For local file edits, do not use <edit_reference>. That is for Notion page editing, not MCP file changes.
- When answering code questions, prefer file paths, line references, function names, command output, or git diff over Notion-style citation footnotes.

Working style:
- First restate the goal in one sentence.
- Default to the current workspace root unless the target path is genuinely ambiguous.
- For non-trivial tasks, give a short plan and keep progress updated.
- Prefer direct tools first. Use delegate_task only when direct tools are not enough.
- Keep moving forward instead of asking for information that can be discovered via tools.
- If the user says fix, change, implement, deploy, update, or similar imperative requests, execute directly instead of stopping after analysis.
- If information is missing, probe with tools first. Use ask-survey only when tool probing still cannot resolve a decision and the next step is destructive or high-risk.

Tool strategy:
- list_skills: use when the user asks what skills are available in this repo or globally.
- In coding tasks, search the local repo first. Do not default to searching the Notion workspace.
- glob_files: narrow candidate paths by pattern.
- grep_files: search code or text with regex, glob filtering, and output modes.
- list_files: inspect directory structure only when structure matters; paginate with limit and offset when needed.
- search_files: use only for simple substring search when regex or context is unnecessary.
- read_file: read relevant file sections before editing.
- read_files: batch read a few files after search or glob discovery.
- replace_in_file: make one small exact edit; use replace_all only when clearly intended.
- apply_patch: prefer this for multi-hunk edits, same-file multi-location edits, moves, deletes, or adds in one patch. Use dry_run=true, validate_only=true, or return_diff=true when you want validation or a preview before writing.
- write_file: create new files or rewrite short files when that is simpler than patching.
- git_status / git_diff / git_commit / git_log: use these as the default repository workflow and traceability tools.
- run_command: proactively use for non-destructive commands such as pwd, ls, rg, tests, builds, or smoke checks; set run_in_background=true for longer jobs.
- delegate_task: use only for complex multi-file reasoning, long-running fallback execution, or repeated failed attempts with direct tools by local codex or claude-code. For non-trivial work, pass goal, acceptance_criteria, verification_commands, and commit_mode.
- get_task / wait_task: check delegated task or background command status; prefer wait_task when blocking is useful.
- cancel_task: stop a delegated task if needed.

Execution rules:
- When exploring a codebase, prefer glob_files and grep_files over broad list_files calls.
- Follow the loop: probe, edit, verify, summarize.
- Do the minimum necessary read/explore work before editing.
- After each edit, re-read the changed section or run a minimal verification command when useful.
- Prefer one apply_patch over multiple replace_in_file calls when changing the same file in several places.
- Do not issue parallel writes to the same file.
- After a logically meaningful change, inspect git_status and git_diff, then create a small focused commit instead of waiting until the end.
- Use focused commits. Do not mix unrelated changes in one commit.
- Use clear commit messages, preferably conventional commit style such as fix, feat, docs, test, refactor, or chore.
- For destructive actions such as deleting files, resetting changes, or dangerous shell commands, ask first.
- If a command or delegated task fails, summarize the root cause and adjust the approach instead of retrying blindly.

Verification rules:
- After code changes, prefer this minimum verification ladder when applicable:
- 1. Syntax or compile check such as cargo check, tsc --noEmit, python -m py_compile, or equivalent.
- 2. Focused tests for the changed area, or the nearest relevant test target.
- 3. Smoke test for the changed behavior, such as starting a service or running curl against the affected endpoint.
- Do not skip verification unless the user explicitly says not to run it.

Output style:
- Before tool use, briefly say what you are about to do.
- During longer tasks, send short progress updates.
- At the end, summarize result, verification, and any remaining risk or next step.
```

</details>

## Optional Use Case

If you also want the **Notion AI instruction page + project-management** workflow, see:

- [Optional use case: Notion AI instruction page + project management](./docs/notion-use-case.md)
- [可选应用场景：Notion AI 页面级指令 + 项目管理](./docs/notion-use-case.zh-CN.md)

## What It Provides

- `list_files`
- `list_skills`
- `glob_files`
- `grep_files`
- `search_files`
- `read_file`
- `read_files`
- `replace_in_file`
- `write_file`
- `apply_patch`
- `git_status`
- `git_diff`
- `git_commit`
- `git_log`
- `run_command`
- `delegate_task`
- `get_task`
- `wait_task`
- `cancel_task`

`delegate_task` supports local `codex` and `claude` CLIs with structured task envelopes.

## Requirements

- Python 3.11+
- `cloudflared`
- A Notion workspace where you can configure an **MCP Agent** with custom MCP support
- Optional: `codex` CLI
- Optional: `claude` CLI

## Quick Start

For a fresh clone, the shortest path is:

```bash
git clone https://github.com/<your-account>/notion-local-ops-mcp.git
cd notion-local-ops-mcp

cp .env.example .env
```

Edit `.env` and set at least:

```bash
NOTION_LOCAL_OPS_WORKSPACE_ROOT="/absolute/path/to/workspace"
NOTION_LOCAL_OPS_AUTH_TOKEN="replace-me"
```

Then run:

```bash
./scripts/dev-tunnel.sh
```

What you should expect:

- the script creates or reuses `.venv`
- the script installs missing Python dependencies automatically
- the script starts the local MCP server on `http://127.0.0.1:8766/mcp`
- the script prefers `cloudflared.local.yml` for a named tunnel
- otherwise it falls back to a `cloudflared` quick tunnel and prints a public HTTPS URL

Use the printed tunnel URL with `/mcp` appended in Notion, and use `NOTION_LOCAL_OPS_AUTH_TOKEN` as the Bearer token.

## Manual Install

```bash
git clone https://github.com/<your-account>/notion-local-ops-mcp.git
cd notion-local-ops-mcp

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Configure

If you are not using the one-command flow, copy `.env.example` to `.env` and set at least:

```bash
cp .env.example .env
NOTION_LOCAL_OPS_WORKSPACE_ROOT="/absolute/path/to/workspace"
NOTION_LOCAL_OPS_AUTH_TOKEN="replace-me"
```

Optional:

```bash
NOTION_LOCAL_OPS_CODEX_COMMAND="codex"
NOTION_LOCAL_OPS_CLAUDE_COMMAND="claude"
NOTION_LOCAL_OPS_COMMAND_TIMEOUT="30"
NOTION_LOCAL_OPS_DELEGATE_TIMEOUT="1800"
```

## Manual Start

```bash
source .venv/bin/activate
notion-local-ops-mcp
```

Local endpoint:

```text
http://127.0.0.1:8766/mcp
```

## One-Command Local Dev Tunnel

Recommended local workflow:

```bash
./scripts/dev-tunnel.sh
```

What it does:

- reuses or creates `.venv`
- installs missing runtime dependencies
- loads `.env` from the repo root if present
- starts `notion-local-ops-mcp`
- prefers `cloudflared.local.yml` or `cloudflared.local.yaml` if present
- otherwise opens a `cloudflared` quick tunnel to your local server

Notes:

- `.env` is gitignored, so your local token and workspace path stay out of git
- `cloudflared.local.yml` is gitignored, so your local named tunnel config stays out of git
- if `NOTION_LOCAL_OPS_WORKSPACE_ROOT` is unset, the script defaults it to the repo root
- if `NOTION_LOCAL_OPS_AUTH_TOKEN` is unset, the script exits with an error instead of guessing
- for a fresh clone, you do not need to run `pip install` manually before using this script

## Expose With cloudflared

### Quick tunnel

```bash
cloudflared tunnel --url http://127.0.0.1:8766
```

Use the generated HTTPS URL with `/mcp`.

### Named tunnel

Copy [`cloudflared-example.yml`](./cloudflared-example.yml) to `cloudflared.local.yml`, fill in your real values, then run:

```bash
cp cloudflared-example.yml cloudflared.local.yml
./scripts/dev-tunnel.sh
```

Or run cloudflared manually:

```bash
cloudflared tunnel --config ./cloudflared-example.yml run <your-tunnel-name>
```

## Environment Variables

| Variable | Required | Default |
| --- | --- | --- |
| `NOTION_LOCAL_OPS_HOST` | no | `127.0.0.1` |
| `NOTION_LOCAL_OPS_PORT` | no | `8766` |
| `NOTION_LOCAL_OPS_WORKSPACE_ROOT` | yes | home directory |
| `NOTION_LOCAL_OPS_STATE_DIR` | no | `~/.notion-local-ops-mcp` |
| `NOTION_LOCAL_OPS_AUTH_TOKEN` | no | empty |
| `NOTION_LOCAL_OPS_CLOUDFLARED_CONFIG` | no | empty |
| `NOTION_LOCAL_OPS_TUNNEL_NAME` | no | empty |
| `NOTION_LOCAL_OPS_CODEX_COMMAND` | no | `codex` |
| `NOTION_LOCAL_OPS_CLAUDE_COMMAND` | no | `claude` |
| `NOTION_LOCAL_OPS_COMMAND_TIMEOUT` | no | `30` |
| `NOTION_LOCAL_OPS_DELEGATE_TIMEOUT` | no | `1800` |

## Tool Notes

- `list_files`: list files and directories, with `limit` and `offset` pagination
- `list_skills`: discover project and global skills with name and description summaries
- `glob_files`: find files or directories by glob pattern
- `grep_files`: advanced regex search with glob filtering and output modes
- `search_files`: simple substring search for backward compatibility
- `read_file`: read text files with offset and limit
- `read_files`: read a batch of text files with shared offset and limit
- `replace_in_file`: replace one exact text fragment or all exact matches
- `write_file`: write full file content
- `apply_patch`: apply codex-style add/update/move/delete patches, with `dry_run`, `validate_only`, and optional diff output
- `git_status`: structured repository status
- `git_diff`: structured diff output with changed file paths
- `git_commit`: stage selected paths or all changes and create a commit
- `git_log`: recent commit history
- `run_command`: run local shell commands, optionally in background
- `delegate_task`: send a task to local `codex` or `claude`, with optional `goal`, `acceptance_criteria`, `verification_commands`, and `commit_mode`
- `get_task`: read task status and output tail
- `wait_task`: block until a delegated or background shell task completes or times out
- `cancel_task`: stop a delegated or background shell task

## Verify

```bash
source .venv/bin/activate
pytest -q
python -m compileall src tests
```

## Troubleshooting

### Notion says it cannot connect

- Check the URL ends with `/mcp`
- Check the auth type is `Bearer`
- Check the token matches `NOTION_LOCAL_OPS_AUTH_TOKEN`
- Check `cloudflared` is still running

### SSE path works locally but not over tunnel

- Retry with a named tunnel instead of a quick tunnel
- Confirm `GET /mcp` returns `text/event-stream`

### `delegate_task` fails

- Check `codex --help`
- Check `claude --help`
- Set `NOTION_LOCAL_OPS_CODEX_COMMAND` or `NOTION_LOCAL_OPS_CLAUDE_COMMAND` if needed

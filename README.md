# notion-local-ops-mcp

Use Notion AI with your local files, shell, and fallback local agents.

📖 **[Project Introduction (Notion Page)](https://www.notion.so/notion-local-ops-mcp-344b4da3979d80e8958ae3fdf1d5e4d9?source=copy_link)**


## What It Provides

- `list_files`
- `search_files`
- `read_file`
- `replace_in_file`
- `write_file`
- `run_command`
- `delegate_task`
- `get_task`
- `cancel_task`

`delegate_task` supports local `codex` and `claude` CLIs.

## Requirements

- Python 3.11+
- `cloudflared`
- Notion Custom Agent with custom MCP support
- Optional: `codex` CLI
- Optional: `claude` CLI

## Install

```bash
git clone https://github.com/<your-account>/notion-local-ops-mcp.git
cd notion-local-ops-mcp

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Configure

Copy `.env.example` to `.env` and set at least:

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

## Start

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
- opens a `cloudflared` quick tunnel to your local server

Notes:

- `.env` is gitignored, so your local token and workspace path stay out of git
- if `NOTION_LOCAL_OPS_WORKSPACE_ROOT` is unset, the script defaults it to the repo root
- if `NOTION_LOCAL_OPS_AUTH_TOKEN` is unset, the script exits with an error instead of guessing

## Expose With cloudflared

### Quick tunnel

```bash
cloudflared tunnel --url http://127.0.0.1:8766
```

Use the generated HTTPS URL with `/mcp`.

### Named tunnel

Edit [`cloudflared-example.yml`](./cloudflared-example.yml), then run:

```bash
cloudflared tunnel --config ./cloudflared-example.yml run <your-tunnel-name>
```

## Add To Notion

Use:

- URL: `https://<your-domain-or-tunnel>/mcp`
- Auth type: `Bearer`
- Token: your `NOTION_LOCAL_OPS_AUTH_TOKEN`

Recommended agent instruction:

```text
Use direct tools first: list_files, search_files, read_file, replace_in_file, write_file, run_command.
Use delegate_task only for complex multi-file work, long-running tasks, or when direct tools are insufficient.
```

## Environment Variables

| Variable | Required | Default |
| --- | --- | --- |
| `NOTION_LOCAL_OPS_HOST` | no | `127.0.0.1` |
| `NOTION_LOCAL_OPS_PORT` | no | `8766` |
| `NOTION_LOCAL_OPS_WORKSPACE_ROOT` | yes | home directory |
| `NOTION_LOCAL_OPS_STATE_DIR` | no | `~/.notion-local-ops-mcp` |
| `NOTION_LOCAL_OPS_AUTH_TOKEN` | no | empty |
| `NOTION_LOCAL_OPS_CODEX_COMMAND` | no | `codex` |
| `NOTION_LOCAL_OPS_CLAUDE_COMMAND` | no | `claude` |
| `NOTION_LOCAL_OPS_COMMAND_TIMEOUT` | no | `30` |
| `NOTION_LOCAL_OPS_DELEGATE_TIMEOUT` | no | `1800` |

## Tool Notes

- `list_files`: list files and directories
- `search_files`: search text in files
- `read_file`: read text files with offset and limit
- `replace_in_file`: replace one exact text fragment
- `write_file`: write full file content
- `run_command`: run local shell commands
- `delegate_task`: send a task to local `codex` or `claude`
- `get_task`: read task status and output tail
- `cancel_task`: stop a delegated task

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

# MCP Server

The swarm ships an optional **Model Context Protocol** server so any MCP client
(Claude Desktop, Cursor, opencode, etc.) can run a full multi-agent research
swarm as a single tool call.

The server exposes one tool:

- **`swarm_research(goal, workers?, model?, skill?, mix?, auto?, synthesize?)`**
  — runs `run_swarm()` and returns the full result dict: worker reports,
  scratchpad findings, the synthesized markdown answer with inline `[N]`
  citations, the `citations` array, `sources_used`/`sources_total`, and the
  `cost` accounting.

Preflight and synthesis tokens are streamed to the client as MCP progress
notifications, so a connected client sees live research progress.

## Install

The `mcp` SDK is an **optional extra** — the library core stays stdlib-only.

```bash
pip install -e ".[mcp]"
```

This also installs the `swarm-mcp` console script. Without the extra, importing
`swarm.integrations.mcp` raises a clear `ImportError` with install instructions.

## Run

Stdio transport (the default for desktop clients):

```bash
python3 -m swarm.integrations.mcp
# or
swarm-mcp
```

The server reads the same `swarm_config.json` and env vars as the CLI
(`OLLAMA_HOST`, `SWARM_CONFIG`, `SEARCH_BACKEND`, `SWARM_CACHE*`, etc.).

## Client configuration

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "swarm-research": {
      "command": "swarm-mcp",
      "args": []
    }
  }
}
```

### opencode

Add to `opencode.json`:

```json
{
  "mcp": {
    "swarm-research": {
      "type": "local",
      "command": ["swarm-mcp"],
      "enabled": true
    }
  }
}
```

### Cursor

Add a new MCP server in Cursor Settings → MCP with command `swarm-mcp`.

## Example

Ask the client: *"Research the current state of fusion energy funding and cite
your sources."* The client calls `swarm_research`, the swarm spawns parallel
workers, and the returned synthesis is markdown with `[1]`, `[2]` markers plus
a numbered `## Sources` section.

## Notes

- The tool is **synchronous** — a research run can take 30s–2min depending on
  worker count. Clients should surface the progress notifications.
- `mix=True` uses the full 5-model team; `skill="research"` loads the research
  skill's `team.json`.
- The result dict is JSON-serializable and matches the CLI `--json` output
  shape (plus the new `citations` / `cost` keys).

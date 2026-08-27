# Persistent TUI

Run with `python3 -m swarm --tui`. The TUI is a Textual-based terminal
interface (`textual>=0.70.0`, installed via `pip install -e .`).

- Three-pane layout: sessions sidebar, chat + worker dashboard, live sources panel
- **Persistent session sidebar**: previous research sessions are loaded from
  `swarm_sessions.db`
- **Follow-up questions** inject the previous run's synthesis + top scratchpad
  findings as context
- **Live worker grid**: each worker shows status, model, skill, elapsed time,
  and a hybrid progress bar (fills per tool round, capped at 5)
- **Live sources panel**: shows worker name + tool + query/URL as research happens
- **Preflight auto-detects research mode** (`objective` vs `subjective`) and
  adapts synthesis style:
  - **Objective** mode aims for a clear factual answer
  - **Subjective** mode maps perspectives, attributes claims, and flags
    contradictions
- Markdown is auto-saved to `swarm_outputs/` on every completed run (using the
  existing `save_markdown()`)
- Sessions are saved to SQLite (`swarm_sessions.db`) automatically

## Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+N` | New session |
| `Ctrl+S` | Export the current run to markdown |
| `Ctrl+Q` | Quit |

"""Custom Textual widgets for the Swarm TUI."""

from __future__ import annotations

from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Input, Label, ListItem, ListView, RichLog, Static


class SessionList(ListView):
    """Sidebar list of research sessions."""

    DEFAULT_CSS = """
    SessionList {
        width: 100%;
        height: 1fr;
        border: solid $primary;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sessions: list[dict] = []

    def refresh_sessions(self, sessions: list[dict]) -> None:
        self.sessions = sessions
        self.clear()
        for s in sessions:
            self.append(
                ListItem(Label(f"{s['title'][:40]} ({s['id']})"), name=s["id"])
            )


class ChatLog(RichLog):
    """Scrollable chat / activity log."""

    DEFAULT_CSS = """
    ChatLog {
        width: 100%;
        height: 2fr;
        border: solid $primary;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(highlight=True, markup=True, wrap=True, **kwargs)

    def add_user(self, text: str) -> None:
        self.write(f"[b][#A78BFA]You:[/] {text}[/b]")

    def add_orchestrator(self, text: str) -> None:
        self.write(f"[#FBBF24]🎯 Orchestrator:[/] {text}")

    def add_system(self, text: str) -> None:
        self.write(f"[#6EE7B7]ℹ {text}[/]")

    def add_worker(self, name: str, status: str, detail: str = "") -> None:
        self.write(f"[#38BDF8]🐝 {name}[/] [{status}] {detail}")


class WorkerGrid(DataTable):
    """Live table of worker status."""

    DEFAULT_CSS = """
    WorkerGrid {
        width: 100%;
        height: 1fr;
        border: solid $primary;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.workers: dict[int, dict] = {}
        self.add_columns("Worker", "Model", "Bundle", "Status", "Time", "Rounds")
        self.cursor_type = "none"

    def update_worker(self, worker_id: int, data: dict) -> None:
        self.workers[worker_id] = data
        self._refresh_rows()

    def _refresh_rows(self) -> None:
        self.clear()
        for worker_id in sorted(self.workers):
            w = self.workers[worker_id]
            self.add_row(
                w.get("name", f"Worker {worker_id}"),
                w.get("model", "").split(":")[0],
                w.get("bundle", "default"),
                w.get("status", "idle"),
                f"{w.get('duration_s', 0):.1f}s",
                str(w.get("rounds", 0)),
            )

    def clear_workers(self) -> None:
        self.workers.clear()
        self.clear()


class InputBar(Horizontal):
    """Bottom input row with submit button."""

    DEFAULT_CSS = """
    InputBar {
        width: 100%;
        height: auto;
        margin: 1 0 0 0;
    }
    InputBar Input {
        width: 1fr;
    }
    InputBar Button {
        width: auto;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input = Input(placeholder="Ask the swarm...", id="query-input")
        self.submit = Button("Submit", variant="primary", id="submit-btn")
        self.loading = Label("⚡ Ready", id="status-label")

    def compose(self):
        yield self.input
        yield self.submit
        yield self.loading

    def set_loading(self, text: str) -> None:
        self.loading.update(text)


class FooterHint(Static):
    """Footer with keyboard shortcuts."""

    DEFAULT_CSS = """
    FooterHint {
        dock: bottom;
        height: 1;
        width: 100%;
        color: $text-muted;
        background: $surface;
    }
    """

    def __init__(self, **kwargs):
        super().__init__("Enter submit  |  Ctrl+N new session  |  Ctrl+S save  |  Ctrl+Q quit", **kwargs)

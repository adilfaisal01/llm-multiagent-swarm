"""Custom Textual widgets for the Swarm TUI."""

from __future__ import annotations

from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Input, Label, ListItem, ListView, ProgressBar, RichLog, Static


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


class WorkerCard(Horizontal):
    """Single worker row with name, progress bar, status, and time."""

    DEFAULT_CSS = """
    WorkerCard {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    WorkerCard Static {
        width: auto;
        content-align: center middle;
    }
    WorkerCard #worker-name {
        width: 12;
    }
    WorkerCard ProgressBar {
        width: 20;
    }
    WorkerCard #worker-status {
        width: 1fr;
    }
    """

    def __init__(self, worker_id: int, **kwargs):
        super().__init__(**kwargs)
        self.worker_id = worker_id
        self.name_label = Static(f"W{worker_id}", id="worker-name")
        self.progress = ProgressBar(total=5, id="worker-progress")
        self.status_label = Static("idle", id="worker-status")

    def compose(self):
        yield self.name_label
        yield self.progress
        yield self.status_label

    def update(self, data: dict) -> None:
        name = data.get("name", f"Worker {self.worker_id}")
        model = data.get("model", "").split(":")[0]
        bundle = data.get("bundle", "default")
        status = data.get("status", "idle")
        duration = data.get("duration_s", 0)
        rounds = data.get("rounds", 0)
        self.name_label.update(f"{name}")
        self.status_label.update(
            f"{model} | {bundle} | {status} | {duration:.1f}s | {rounds}/5"
        )

    def advance(self) -> None:
        self.progress.advance(1)


class WorkerGrid(Vertical):
    """Container of worker cards."""

    DEFAULT_CSS = """
    WorkerGrid {
        width: 100%;
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cards: dict[int, WorkerCard] = {}

    def update_worker(self, worker_id: int, data: dict) -> None:
        if worker_id not in self._cards:
            card = WorkerCard(worker_id)
            self._cards[worker_id] = card
            self.mount(card)
        self._cards[worker_id].update(data)

    def advance_worker(self, worker_id: int) -> None:
        card = self._cards.get(worker_id)
        if card:
            card.advance()

    def clear_workers(self) -> None:
        for card in self._cards.values():
            card.remove()
        self._cards.clear()


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
        self.status_label = Label("⚡ Ready", id="status-label")

    def compose(self):
        yield self.input
        yield self.submit
        yield self.status_label

    def set_loading(self, text: str) -> None:
        self.status_label.update(text)


class SourcesPanel(RichLog):
    """Live feed of sources and tool calls."""

    DEFAULT_CSS = """
    SourcesPanel {
        width: 100%;
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(highlight=True, markup=True, wrap=True, **kwargs)

    def add_source(self, worker: str, tool: str, detail: str) -> None:
        self.write(f"[#38BDF8]{worker}[/] [{tool}] {detail}")

    def clear_sources(self) -> None:
        self.clear()


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

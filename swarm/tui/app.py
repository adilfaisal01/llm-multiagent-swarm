"""Main Textual app for the persistent Swarm TUI."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Header, Static

from ..output import save_markdown
from ..runner import run_swarm
from .session import Session
from .store import SessionStore
from .widgets import ChatLog, FooterHint, InputBar, SessionList, SourcesPanel, WorkerGrid


class SwarmTUI(App):
    """Persistent terminal UI for the multi-agent swarm."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #main-row {
        width: 100%;
        height: 1fr;
    }
    #sidebar {
        width: 20%;
        height: 100%;
        border: solid $primary;
    }
    #content {
        width: 55%;
        height: 100%;
    }
    #sources-panel {
        width: 25%;
        height: 100%;
        border: solid $primary;
    }
    """
    BINDINGS = [
        ("ctrl+n", "new_session", "New Session"),
        ("ctrl+s", "save_session", "Save Markdown"),
        ("ctrl+q", "quit", "Quit"),
    ]

    active_session: reactive[Session | None] = reactive(None)
    running: reactive[bool] = reactive(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = SessionStore()
        self.sessions: list[Session] = []
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._event_queue: asyncio.Queue | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-row"):
            with Vertical(id="sidebar"):
                yield Static("[b]Sessions[/b]", id="sidebar-title")
                yield SessionList(id="session-list")
            with Vertical(id="content"):
                yield ChatLog(id="chat-log")
                yield WorkerGrid(id="worker-grid")
                yield InputBar(id="input-bar")
            with Vertical(id="sources-panel"):
                yield Static("[b]Sources[/b]", id="sources-title")
                yield SourcesPanel(id="sources-log")
        yield FooterHint()

    async def on_mount(self) -> None:
        self._event_queue = asyncio.Queue()
        self._load_sessions()
        if not self.sessions:
            await self._new_session()
        else:
            self.active_session = self.sessions[0]

    async def watch_active_session(self, session: Session | None) -> None:
        if session is None:
            return
        chat = self.query_one("#chat-log", ChatLog)
        chat.clear()
        chat.add_system(f"Loaded session: {session.title} ({session.id})")
        for msg in session.messages:
            role = msg.get("role")
            if role == "user":
                chat.add_user(msg.get("content", ""))
            elif role == "orchestrator":
                chat.add_orchestrator(msg.get("content", ""))
            elif role == "worker":
                chat.add_worker(
                    msg.get("name", "Worker"),
                    msg.get("status", "ok"),
                    f"{msg.get('duration_s', 0):.1f}s",
                )
        grid = self.query_one("#worker-grid", WorkerGrid)
        grid.clear_workers()
        sources = self.query_one("#sources-log", SourcesPanel)
        sources.clear_sources()
        self._refresh_sidebar()

    def _refresh_sidebar(self) -> None:
        sidebar = self.query_one("#session-list", SessionList)
        sidebar.refresh_sessions([
            {"id": s.id, "title": s.title, "active": s.id == getattr(self.active_session, "id", None)}
            for s in self.sessions
        ])

    def _load_sessions(self) -> None:
        self.sessions = self.store.list_sessions()

    async def _new_session(self) -> None:
        session = Session()
        self.sessions.insert(0, session)
        self.active_session = session
        self.store.save(session)
        chat = self.query_one("#chat-log", ChatLog)
        chat.clear()
        chat.add_system("New session started. Ask the swarm a question.")

    def action_new_session(self) -> None:
        asyncio.create_task(self._new_session())

    def action_save_session(self) -> None:
        if not self.active_session:
            return
        result = self.active_session.last_result()
        if not result:
            chat = self.query_one("#chat-log", ChatLog)
            chat.add_system("No completed run to save yet.")
            return
        path = save_markdown(result, result.get("goal", "swarm"))
        chat = self.query_one("#chat-log", ChatLog)
        chat.add_system(f"Saved markdown to {path}")

    def on_list_view_selected(self, event) -> None:
        item = event.item
        if not item:
            return
        session_id = item.name
        session = self.store.load(session_id)
        if session:
            self.active_session = session

    def on_button_pressed(self, event) -> None:
        if event.button.id == "submit-btn":
            self._submit_query()

    def on_input_submitted(self, event) -> None:
        if event.input.id == "query-input":
            self._submit_query()

    def _submit_query(self) -> None:
        if self.running:
            return
        input_bar = self.query_one("#input-bar", InputBar)
        text = input_bar.input.value.strip()
        if not text:
            return
        input_bar.input.value = ""
        input_bar.set_loading("Running swarm...")
        if self.active_session is None:
            asyncio.create_task(self._new_session())
            if self.active_session is None:
                return
        self.active_session.add_user_message(text)
        chat = self.query_one("#chat-log", ChatLog)
        chat.add_user(text)
        grid = self.query_one("#worker-grid", WorkerGrid)
        grid.clear_workers()
        sources = self.query_one("#sources-log", SourcesPanel)
        sources.clear_sources()
        self.running = True

        # Build context from previous run if available
        context = self.active_session.context_for_followup()
        full_goal = text
        if context:
            full_goal = (
                f"{text}\n\n"
                f"[FOLLOW-UP CONTEXT FROM PREVIOUS SWARM RUN]:\n"
                f"{context}\n\n"
                f"Use the context above only if it is relevant to the current question."
            )
            chat.add_system("Injected context from previous run.")

        # Run swarm in a background thread, pumping progress events
        progress = partial(self._sync_progress)
        self._executor.submit(self._run_swarm_thread, full_goal, text, progress)
        asyncio.create_task(self._drain_events())

    def _run_swarm_thread(self, goal: str, original_query: str, progress) -> None:
        try:
            result = run_swarm(
                goal=goal,
                mix=True,
                progress_callback=progress,
            )
            result["_original_query"] = original_query
            progress("final_result", result)
        except Exception as exc:
            progress("error", {"message": str(exc)})

    def _sync_progress(self, event: str, payload) -> None:
        """Thread-safe callback used by the worker/orchestrator threads."""
        if self._event_queue is not None:
            try:
                self._event_queue.put_nowait((event, payload))
            except asyncio.QueueFull:
                pass

    async def _drain_events(self) -> None:
        while self._event_queue is not None:
            event, payload = await self._event_queue.get()
            await self._handle_event(event, payload)
            if event in ("final_result", "error"):
                break

    async def _handle_event(self, event: str, payload) -> None:
        chat = self.query_one("#chat-log", ChatLog)
        grid = self.query_one("#worker-grid", WorkerGrid)
        sources = self.query_one("#sources-log", SourcesPanel)
        if event == "preflight_start":
            chat.add_system("Preflight: analyzing question...")
        elif event == "preflight_done":
            mode = payload.get("mode", "parallel")
            research_mode = payload.get("research_mode", "objective")
            bundles = payload.get("bundles", [])
            emoji = "🎭" if research_mode == "subjective" else "🔬"
            chat.add_system(
                f"Preflight done — mode: {mode}, research: {research_mode} {emoji}, bundles: {', '.join(bundles)}"
            )
        elif event == "worker_start":
            grid.update_worker(
                payload["worker_id"],
                {
                    "name": payload.get("name", f"Worker {payload['worker_id']}"),
                    "model": payload.get("model", ""),
                    "bundle": payload.get("bundle", "default"),
                    "status": "running",
                    "duration_s": 0,
                    "rounds": 0,
                },
            )
        elif event == "worker_tool_call":
            grid.update_worker(
                payload["worker_id"],
                {
                    "name": payload.get("name", f"Worker {payload['worker_id']}"),
                    "model": "",
                    "bundle": payload.get("bundle", "default"),
                    "status": f"tool: {payload.get('tool', '')}",
                    "duration_s": 0,
                    "rounds": 0,
                },
            )
            grid.advance_worker(payload["worker_id"])
            args = payload.get("args", {})
            tool = payload.get("tool", "")
            detail = ""
            if tool == "web_search":
                detail = args.get("query", "")
            elif tool == "web_extract":
                detail = args.get("url", "")
            elif tool == "read_image":
                detail = args.get("path", "") or args.get("question", "")
            elif tool == "read_file":
                detail = args.get("path", "")
            elif tool == "python_exec":
                detail = args.get("code", "")[:60]
            if detail:
                sources.add_source(
                    payload.get("name", f"Worker {payload['worker_id']}"),
                    tool,
                    detail,
                )
        elif event == "worker_done":
            grid.update_worker(
                payload["worker_id"],
                {
                    "name": payload.get("name", f"Worker {payload['worker_id']}"),
                    "model": payload.get("model", ""),
                    "bundle": payload.get("tool_bundle", "default"),
                    "status": payload.get("status", "ok"),
                    "duration_s": payload.get("duration_s", 0),
                    "rounds": payload.get("search_rounds", 0),
                },
            )
            chat.add_worker(
                payload.get("name", f"Worker {payload['worker_id']}"),
                payload.get("status", "ok"),
                f"{payload.get('duration_s', 0):.1f}s, {payload.get('search_rounds', 0)} rounds",
            )
        elif event == "synthesis_start":
            chat.add_system("Orchestrator synthesizing...")
        elif event == "synthesis_done":
            chat.add_system(
                f"Synthesis done ({payload.get('time_s', 0):.1f}s, {payload.get('chars', 0)} chars)"
            )
        elif event == "final_result":
            result = payload
            synthesis = result.get("synthesis", "")
            if synthesis and not synthesis.startswith("[Synthesis error"):
                chat.add_orchestrator(synthesis[:2000])
                if len(synthesis) > 2000:
                    chat.add_system(f"... synthesis truncated ({len(synthesis)} chars total)")
            else:
                chat.add_orchestrator(result.get("workers", [{}])[0].get("response", "No result"))
            if self.active_session:
                self.active_session.add_orchestrator_message(synthesis or "No synthesis", result)
                self.active_session.add_worker_messages(result.get("workers", []))
                self.store.save(self.active_session)
                self._load_sessions()
                self._refresh_sidebar()
                original_query = result.pop("_original_query", self.active_session.last_user_query())
                path = save_markdown(result, original_query or result.get("goal", "swarm"))
                chat.add_system(f"Auto-saved markdown to {path}")
            input_bar = self.query_one("#input-bar", InputBar)
            input_bar.set_loading("Ready")
            self.running = False
        elif event == "error":
            chat.add_system(f"Error: {payload.get('message', 'unknown')}")
            input_bar = self.query_one("#input-bar", InputBar)
            input_bar.set_loading("Ready")
            self.running = False

    async def action_quit(self) -> None:
        self._executor.shutdown(wait=False)
        await super().action_quit()


def run_tui() -> None:
    """Entry point for the persistent TUI."""
    app = SwarmTUI()
    app.run()

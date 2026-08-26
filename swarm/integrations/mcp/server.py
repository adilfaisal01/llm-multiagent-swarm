"""MCP server implementation — stdio transport, single swarm_research tool.

The server wraps ``run_swarm()`` and relays preflight + synthesis streamed
tokens to the client as progress notifications, so a connected MCP client
sees live research progress. The full result dict (including ``citations``
and ``cost``) is returned as the tool result.
"""

from __future__ import annotations

import sys

from swarm.runner import run_swarm

try:
    from mcp.server.fastmcp import Context, FastMCP
except ImportError as e:  # pragma: no cover - exercised only when mcp is absent
    raise ImportError(
        "The MCP server requires the optional 'mcp' extra. "
        "Install it with: pip install -e '.[mcp]'"
    ) from e

_SERVER_NAME = "swarm-research"


def _stream_to_progress(ctx, chunk: str, phase: str):
    """Forward a streamed token to the MCP client as a progress notification."""
    if ctx is None:
        return
    try:
        ctx.report_progress(0.0, None, message=f"[{phase}] {chunk}")
    except Exception:
        pass


def run_mcp_server() -> None:
    """Start the stdio MCP server and block until the client disconnects."""
    mcp = FastMCP(_SERVER_NAME)

    @mcp.tool()
    def swarm_research(
        goal: str,
        workers: int | None = None,
        model: str | None = None,
        skill: str | None = None,
        mix: bool = False,
        auto: bool = False,
        synthesize: bool = True,
        ctx: Context | None = None,
    ) -> dict:
        """Run a multi-agent research swarm on a question and return a cited answer.

        Use this when you need current, multi-source research on a factual
        question, a number/date/name, or a topic with multiple perspectives.
        The swarm spawns parallel research workers (each with web search and
        extraction tools), collects their findings in a shared scratchpad, and
        synthesizes a unified markdown answer with inline [N] citations.

        Args:
            goal: The research question to answer.
            workers: Number of workers (1-5). Defaults to 3, or the full team
                with mix=True.
            model: Model alias or full tag for uniform mode (ignored if mix).
            skill: Named skill from swarm/skills/ (e.g. 'research',
                'reverse-engineering'). Loads its team.json if present.
            mix: Use the mixed 5-model team (Vera/Cyrus/Romy/Ash/Zara).
            auto: Auto-estimate worker count from question complexity.
            synthesize: Whether to run the final synthesis pass (default True).

        Returns:
            A dict with the full swarm result: workers, scratchpad, synthesis
            (markdown with [N] citations), citations, sources_used/total, cost.
        """
        stream_cb = (lambda chunk, phase: _stream_to_progress(ctx, chunk, phase)) if ctx else None
        return run_swarm(
            goal,
            workers=workers,
            model=model,
            skill=skill,
            mix=mix,
            auto=auto,
            synthesize=synthesize,
            stream_callback=stream_cb,
        )

    mcp.run()


def main() -> None:
    """Console-script entry point (swarm-mcp)."""
    run_mcp_server()


if __name__ == "__main__":
    sys.exit(main())

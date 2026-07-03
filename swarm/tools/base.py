"""Base class for all swarm tools."""
from __future__ import annotations
from typing import Any


class BaseTool:
    """Extend this to create a new tool.

    Required overrides:
        name        — unique tool identifier (e.g. 'web_search')
        description — shown to the LLM
        parameters  — JSON schema for function arguments
        run(args)   — execute the tool, return str

    Example:
        class MyTool(BaseTool):
            name = "my_tool"
            description = "Does something useful"
            parameters = {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"],
            }
            def run(self, args, worker_name=""):
                return f"Result: {args['query']}"
    """

    name: str = ""
    description: str = ""
    parameters: dict = {}

    def to_ollama_tool(self) -> dict:
        """Convert to Ollama function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Execute the tool. Override this."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Tool: {self.name}>"
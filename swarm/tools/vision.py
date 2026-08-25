"""Vision tool — read images using Gemma4 vision model."""
from __future__ import annotations
import base64
import json
import os
import urllib.request
from .base import BaseTool


class ReadImage(BaseTool):
    """Read an image file and extract its visual contents.

    Sends the image (base64-encoded) to the Gemma4 vision model via Ollama
    and returns the model's description. Used for questions that reference
    an image, screenshot, chart, or figure.
    """

    name = "read_image"
    description = (
        "Read an image file and extract its contents (text, numbers, "
        "diagrams, visual information). Use this when the question "
        "refers to an image, screenshot, chart, or figure."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the image file (.png, .jpg, .jpeg)",
            },
            "question": {
                "type": "string",
                "description": "Optional: specific question about the image content",
            },
        },
        "required": ["path"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Read an image via the vision model.

        Args:
            args: Tool arguments. ``path`` is required (absolute path to a
                .png/.jpg/.jpeg file); ``question`` is an optional prompt
                about the image content.
            worker_name: Unused by this tool; accepted for interface parity.

        Returns:
            The vision model's description, or an error string starting
            with ``Error:`` / ``[ReadImage error:`` on failure.
        """
        path = args.get("path", "")
        question = args.get("question", "Describe what you see in this image in detail.")

        if not os.path.exists(path):
            return f"Error: file not found at {path}"

        try:
            with open(path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
        except Exception as e:
            return f"[ReadImage error: {e}]"

        payload = json.dumps({
            "model": "qwen3.5:397b-cloud",  # vision model (bake-off winner Aug 2026: most precise on values/scales/app-ID, clean content output)
            "messages": [
                {"role": "user", "content": question, "images": [img_b64]}
            ],
            "stream": False,
            "options": {"num_predict": 1024, "temperature": 0.1},
        }).encode()

        ollama_base = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        if not ollama_base.startswith("http"):
            ollama_base = f"http://{ollama_base}"

        req = urllib.request.Request(
            f"{ollama_base}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                content = data.get("message", {}).get("content", "")
                return content.strip() or "(vision model returned empty)"
        except Exception as e:
            return f"[ReadImage error: {e}]"


TOOLS = [ReadImage()]
BUNDLES = ["vision", "files", "all"]
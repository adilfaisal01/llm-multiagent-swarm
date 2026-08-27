"""Vision tool — read images using a vision-capable model."""
from __future__ import annotations
import base64
import os
from .base import BaseTool
from ..llm import call_llm


class ReadImage(BaseTool):
    """Read an image file and extract its visual contents.

    Sends the image (base64-encoded) to a vision-capable model and
    returns the model's description. Used for questions that reference
    an image, screenshot, chart, or figure. The model defaults to
    ``ollama/qwen3.5:397b-cloud`` and can be overridden via the
    ``SWARM_VISION_MODEL`` env var (or ``vision_model`` in config, which
    the runner mirrors to the env var).
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

        vision_model = os.environ.get(
            "SWARM_VISION_MODEL", "ollama/qwen3.5:397b-cloud"
        )

        content = call_llm(
            vision_model,
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                        },
                    ],
                }
            ],
            temperature=0.1,
            max_tokens=1024,
            timeout=120,
            purpose="vision",
        )

        if content.startswith("[LLM error"):
            return f"[ReadImage error: {content}]"
        return content.strip() or "(vision model returned empty)"


TOOLS = [ReadImage()]
BUNDLES = ["vision", "files", "all"]
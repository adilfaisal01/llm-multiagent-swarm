"""Python execution tool — run Python code and return the result.

WARNING: This allows arbitrary code execution. Only use in trusted environments.
"""
from __future__ import annotations
import io
import sys
import contextlib
from .base import BaseTool


class PythonExec(BaseTool):
    name = "python_exec"
    description = (
        "Execute Python code and return the output. Use this for "
        "calculations, statistics, data processing, or any task "
        "that needs computation. The code runs in an isolated context "
        "with access to math, statistics, json, re, collections. "
        "Use print() to output results."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute",
            }
        },
        "required": ["code"],
    }

    SAFE_GLOBALS = {
        "__builtins__": {
            "abs": abs,
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "int": int,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "print": print,
            "range": range,
            "round": round,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "type": type,
            "zip": zip,
            "True": True,
            "False": False,
            "None": None,
            "__import__": __import__,
            "isinstance": isinstance,
            "hasattr": hasattr,
            "getattr": getattr,
            "setattr": setattr,
            "open": None,  # deny file access
            "eval": None,  # deny eval
            "exec": None,  # deny nested exec
        },
        "math": __import__("math"),
        "re": __import__("re"),
        "json": __import__("json"),
        "statistics": __import__("statistics"),
        "collections": __import__("collections"),
        "itertools": __import__("itertools"),
        "functools": __import__("functools"),
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        code = args.get("code", "")
        if not code:
            return "Error: no code provided"

        # Collect stdout
        stdout = io.StringIO()
        result = None
        error = None

        try:
            with contextlib.redirect_stdout(stdout):
                exec(code, self.SAFE_GLOBALS.copy())
        except Exception as e:
            error = str(e)

        output = stdout.getvalue()
        if error:
            return f"Output:\n{output}\nError: {error}"
        return output.strip() or "(no output — use print() to show results)"


TOOLS = [PythonExec()]
BUNDLES = ["code", "all"]
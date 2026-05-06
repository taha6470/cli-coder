from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable

from .llm import LLMClient, LLMError
from .neuron import Neuron
from .tools import ToolError, list_directory, read_file, run_terminal_command, write_file


SYSTEM_PROMPT = """You are a local AI coding agent. You can ONLY interact with the user's computer using the provided tools.

Rules:
- Use tools when you need to inspect or modify files, list directories, or run commands.
- Prefer small, safe changes.
- After implementing changes, ensure the result works by running an appropriate command when feasible.
- If a tool fails, diagnose and try again.
- When you are done, respond with a concise answer and a test plan.
- Include exactly ONE line that starts with "Summary: " (one sentence). This will be used for local memory commits.

Performance rules:
- Do NOT output <|channel|>thought or any hidden reasoning. Only output user-facing results.
"""


def openai_tools_spec() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a text file from disk.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "max_bytes": {"type": "integer", "minimum": 1, "maximum": 2000000},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write a text file to disk (UTF-8). Creates parent directories.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "List entries in a directory.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_terminal_command",
                "description": "Run a shell command and return stdout/stderr + exit code.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "cwd": {"type": "string"},
                        "timeout_s": {"type": "integer", "minimum": 1, "maximum": 3600},
                    },
                    "required": ["command"],
                },
            },
        },
    ]


ToolFn = Callable[..., dict[str, Any]]


def _tool_dispatch() -> dict[str, ToolFn]:
    return {
        "read_file": lambda path, max_bytes=250_000: read_file(path, max_bytes=max_bytes),
        "write_file": lambda path, content: write_file(path, content),
        "list_directory": lambda path=".": list_directory(path),
        "run_terminal_command": lambda command, cwd=None, timeout_s=120: run_terminal_command(
            command, cwd=cwd, timeout_s=timeout_s
        ),
    }


@dataclass
class RunResult:
    final_text: str
    wrote_files: list[str] = field(default_factory=list)
    tool_events: list[dict[str, Any]] = field(default_factory=list)


class Agent:
    def __init__(self, *, llm: LLMClient, neuron: Neuron):
        self.llm = llm
        self.neuron = neuron
        self.tools_spec = openai_tools_spec()
        self.tool_fns = _tool_dispatch()

    def run_once(self, *, user_instruction: str) -> RunResult:
        # Context truncation: only inject the last 10 lines of Neuron.
        full_neuron = self.neuron.read()
        tail_lines = full_neuron.splitlines()[-10:]
        neuron_text = "\n".join(tail_lines).strip()

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "system",
                "content": f"Neuron memory (most recent, truncated if needed):\n\n{neuron_text}",
            },
            {"role": "user", "content": user_instruction},
        ]

        wrote_files: list[str] = []
        tool_events: list[dict[str, Any]] = []

        # Single-call guarantee: exactly ONE request to the LLM per user instruction.
        resp = self.llm.chat_completions(messages=messages, tools=self.tools_spec)
        choice = (resp.get("choices") or [{}])[0]
        msg = choice.get("message") or {}

        # OpenAI tool calls shape:
        # message: { role, content, tool_calls: [ { id, type:"function", function:{name,arguments} } ] }
        tool_calls = msg.get("tool_calls") or []
        content = msg.get("content")

        if tool_calls:
            for tc in tool_calls:
                fn = (tc.get("function") or {}).get("name")
                raw_args = (tc.get("function") or {}).get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}
                try:
                    if fn not in self.tool_fns:
                        raise ToolError(f"Unknown tool: {fn}")
                    result = self.tool_fns[fn](**(args or {}))
                    if fn == "write_file":
                        wrote_files.append(result.get("path", ""))
                    tool_events.append({"tool": fn, "ok": "error" not in result, "args": args or {}, "result": result})
                except Exception as e:
                    tool_events.append(
                        {"tool": fn, "ok": False, "args": args or {}, "result": {"error": str(e), "tool": fn}}
                    )

            # Since we do not do a second LLM roundtrip, emit a minimal local response.
            errors = [ev for ev in tool_events if not ev.get("ok")]
            if errors:
                first = errors[0].get("result") or {}
                final = f"Tool error: {first.get('error', 'Unknown error')}"
                summary = "Summary: Tool execution failed."
                return RunResult(final_text=final + "\n" + summary, wrote_files=[p for p in wrote_files if p], tool_events=tool_events)

            tool_list = ", ".join(sorted({str(ev.get('tool')) for ev in tool_events if ev.get('tool')}))
            final = f"Executed tools: {tool_list}" if tool_list else "Executed tools."
            if wrote_files:
                short = ", ".join([Path(p).name for p in wrote_files[:3] if p])
                more = " (and more)" if len(wrote_files) > 3 else ""
                summary = f"Summary: Wrote {len(wrote_files)} file(s): {short}{more}."
            else:
                summary = "Summary: Executed requested tools."
            return RunResult(final_text=final + "\n" + summary, wrote_files=[p for p in wrote_files if p], tool_events=tool_events)

        if isinstance(content, str) and content.strip():
            final = content.strip()
        else:
            final = "Done."

        # Enforce in-process summarization contract.
        lower_lines = [ln.strip().lower() for ln in final.splitlines() if ln.strip()]
        has_summary = any(ln.startswith("summary:") for ln in lower_lines)
        if not has_summary:
            first_line = next((ln.strip() for ln in final.splitlines() if ln.strip()), "")
            fallback = first_line[:120].rstrip()
            if not fallback:
                fallback = "Completed task."
            final = final + "\n" + f"Summary: {fallback}"

        return RunResult(final_text=final, wrote_files=[p for p in wrote_files if p], tool_events=tool_events)


from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Neuron:
    obsidian_dir: Path
    neuron_path: Path

    def ensure(self) -> None:
        self.obsidian_dir.mkdir(parents=True, exist_ok=True)
        if not self.neuron_path.exists():
            self.neuron_path.write_text(
                "# Neuron\n\nThis file is automatically maintained by the local coding agent.\n",
                encoding="utf-8",
            )

    def read(self, *, max_chars: int = 25_000) -> str:
        self.ensure()
        text = self.neuron_path.read_text(encoding="utf-8")
        if len(text) > max_chars:
            # Keep the tail (most recent info) to maximize usefulness.
            return text[-max_chars:]
        return text

    @staticmethod
    def _cap_approx_tokens(text: str, *, max_tokens: int = 150) -> str:
        """
        Hard cap output size to protect the primary model's KV cache.
        We approximate tokens as ~4 chars/token (rough but effective).
        """
        if max_tokens <= 0:
            return ""
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1].rstrip() + "…"

    @staticmethod
    def _format_summary(bullets: Iterable[str]) -> str:
        clean: list[str] = []
        for b in bullets:
            b = (b or "").strip()
            if not b:
                continue
            # Normalize leading bullet markers if caller already included them.
            if b.startswith(("-", "*")):
                b = b[1:].strip()
            clean.append(b)
            if len(clean) >= 3:
                break
        if not clean:
            clean = ["No major milestone recorded."]
        return "<summary>\n" + "\n".join(f"- {b}" for b in clean) + "\n</summary>"

    def append_success(self, *, summary: str, why: str) -> None:
        self.ensure()
        ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        # Backwards-compatible wrapper.
        summary_xml = self._format_summary([summary.strip()])
        why_capped = self._cap_approx_tokens(why.strip(), max_tokens=150)
        block = (
            "\n\n---\n"
            f"## {ts}\n\n"
            f"{summary_xml}\n\n"
            f"**Why**: {why_capped}\n"
        )
        with self.neuron_path.open("a", encoding="utf-8") as f:
            f.write(block)

    def append_milestone(self, *, bullets: list[str], why: str = "") -> None:
        """
        Append a compact, token-capped milestone entry.
        Format is intentionally minimal to reduce prompt bloat.
        """
        self.ensure()
        ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        summary_xml = self._format_summary(bullets)
        payload = summary_xml
        if why.strip():
            payload += "\n\n" + f"**Why**: {why.strip()}"
        payload = self._cap_approx_tokens(payload, max_tokens=150)
        block = "\n\n---\n" + f"## {ts}\n\n" + payload + "\n"
        with self.neuron_path.open("a", encoding="utf-8") as f:
            f.write(block)


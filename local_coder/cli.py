from __future__ import annotations

import argparse
import os
from pathlib import Path

from .agent import Agent
from .config import load_config
from .llm import LLMClient, LLMError
from .neuron import Neuron


def _print_banner(cfg) -> None:
    print("Local Coder (100% local)")
    print(f"- Base URL: {cfg.base_url}")
    print(f"- Model:    {cfg.model}")
    print(f"- Obsidian: {cfg.obsidian_dir}")
    print(f"- Neuron:   {cfg.neuron_path}")
    print("Type 'exit' to quit. Type 'commit' to write a memory milestone.\n")


def _extract_summary_line(text: str) -> str | None:
    for line in (text or "").splitlines():
        line = line.strip()
        if line.lower().startswith("summary:"):
            # Keep it 1-line, trim prefix.
            rest = line.split(":", 1)[1].strip()
            return rest or None
    return None


def _is_major_write(*, tool_events: list[dict], obsidian_dir: Path) -> bool:
    """
    Major write heuristic:
    - any write_file outside the Obsidian directory
    - and at least ~200 bytes written (to avoid tiny touch-ups)
    """
    try:
        obsidian_dir_resolved = obsidian_dir.expanduser().resolve()
    except Exception:
        obsidian_dir_resolved = obsidian_dir

    for ev in tool_events or []:
        if ev.get("tool") != "write_file":
            continue
        res = ev.get("result") or {}
        path = (res.get("path") or "").strip()
        bytes_written = int(res.get("bytes_written") or 0)
        if not path:
            continue
        try:
            p = Path(path).expanduser().resolve()
        except Exception:
            p = Path(path)
        if str(p).startswith(str(obsidian_dir_resolved)):
            continue
        if bytes_written >= 200:
            return True
    return False


def _commit_neuron(*, neuron: Neuron, neuron_path: Path, summary: str) -> None:
    if not summary.strip():
        return
    neuron.append_milestone(bullets=[summary.strip()])
    if os.getenv("LOCAL_CODER_QUIET") != "1":
        print(f"[Neuron] committed milestone to {neuron_path}\n")


def main() -> int:
    parser = argparse.ArgumentParser(prog="local_coder", add_help=True)
    parser.add_argument("--once", metavar="INSTRUCTION", help="Run a single instruction and exit.")
    args = parser.parse_args()

    cfg = load_config()
    neuron = Neuron(obsidian_dir=cfg.obsidian_dir, neuron_path=cfg.neuron_path)
    llm = LLMClient(base_url=cfg.base_url, api_key=cfg.api_key, model=cfg.model)
    agent = Agent(llm=llm, neuron=neuron)

    pending_summary: str | None = None

    if args.once:
        try:
            result = agent.run_once(user_instruction=args.once)
        except LLMError as e:
            print(f"[LLM error] {e}")
            return 1
        except Exception as e:
            print(f"[Error] {e}")
            return 1

        print(result.final_text)

        # Lazy commits: only commit if a major file was written.
        summary = _extract_summary_line(result.final_text) or ""
        if _is_major_write(tool_events=result.tool_events, obsidian_dir=cfg.obsidian_dir) and summary:
            _commit_neuron(neuron=neuron, neuron_path=cfg.neuron_path, summary=summary)
        return 0

    _print_banner(cfg)

    while True:
        try:
            user = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not user:
            continue
        if user.lower() in {"exit", "quit"}:
            return 0
        if user.lower() == "commit":
            if pending_summary:
                _commit_neuron(neuron=neuron, neuron_path=cfg.neuron_path, summary=pending_summary)
                pending_summary = None
            else:
                if os.getenv("LOCAL_CODER_QUIET") != "1":
                    print("[Neuron] nothing pending to commit.\n")
            continue

        try:
            result = agent.run_once(user_instruction=user)
        except LLMError as e:
            print(f"\n[LLM error] {e}\n")
            continue
        except Exception as e:
            print(f"\n[Error] {e}\n")
            continue

        print("\n" + result.final_text + "\n")

        # In-process summarization: capture the model's 1-line Summary.
        pending_summary = _extract_summary_line(result.final_text) or pending_summary

        # Lazy commits: auto-commit only when a major file is written.
        if pending_summary and _is_major_write(tool_events=result.tool_events, obsidian_dir=cfg.obsidian_dir):
            _commit_neuron(neuron=neuron, neuron_path=cfg.neuron_path, summary=pending_summary)
            pending_summary = None


if __name__ == "__main__":
    raise SystemExit(main())


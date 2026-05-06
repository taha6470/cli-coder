from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    base_url: str
    api_key: str
    model: str
    obsidian_dir: Path
    neuron_filename: str

    @property
    def neuron_path(self) -> Path:
        return self.obsidian_dir / self.neuron_filename


def load_config() -> Config:
    base_url = os.getenv("LOCAL_CODER_BASE_URL", "http://localhost:1234/v1").rstrip("/")
    api_key = os.getenv("LOCAL_CODER_API_KEY", "local")
    model = os.getenv("LOCAL_CODER_MODEL", "local-model")
    obsidian_dir = Path(os.getenv("LOCAL_CODER_OBSIDIAN_DIR", "./obsidian")).expanduser().resolve()
    neuron_filename = os.getenv("LOCAL_CODER_NEURON_FILE", "neuron.md")
    return Config(
        base_url=base_url,
        api_key=api_key,
        model=model,
        obsidian_dir=obsidian_dir,
        neuron_filename=neuron_filename,
    )


"""Minimal file-based model registry.

Phase 1 keeps model artifacts and metadata on the local filesystem (or a mounted
volume). Phase 2 promotes this to MLflow (docs/05-machine-learning.md - Model
lifecycle). The interface here mirrors the concepts we'll need later: immutable
versions, per-model "production" pointer, and a JSON model card.
"""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class ModelVersion:
    name: str
    version: str
    path: Path
    metadata: dict[str, Any]


class FileModelRegistry:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _model_dir(self, name: str) -> Path:
        return self.root / name

    def _pointer(self, name: str) -> Path:
        return self._model_dir(name) / "production.json"

    def save(self, name: str, model: object, metadata: dict[str, Any]) -> ModelVersion:
        version = "v" + datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
        vdir = self._model_dir(name) / version
        vdir.mkdir(parents=True, exist_ok=True)
        with (vdir / "model.pkl").open("wb") as fh:
            pickle.dump(model, fh)
        card = {"name": name, "version": version, "created_at": _now_iso(), **metadata}
        (vdir / "metadata.json").write_text(json.dumps(card, indent=2, default=str))
        return ModelVersion(name=name, version=version, path=vdir, metadata=card)

    def list_versions(self, name: str) -> list[str]:
        model_dir = self._model_dir(name)
        if not model_dir.exists():
            return []
        return sorted(p.name for p in model_dir.iterdir() if p.is_dir() and p.name.startswith("v"))

    def set_production(self, name: str, version: str) -> None:
        if version not in self.list_versions(name):
            raise FileNotFoundError(f"Unknown version {name}:{version}")
        self._pointer(name).write_text(json.dumps({"version": version, "updated_at": _now_iso()}))

    def get_production_version(self, name: str) -> Optional[str]:
        pointer = self._pointer(name)
        if pointer.exists():
            return str(json.loads(pointer.read_text())["version"])
        versions = self.list_versions(name)
        return versions[-1] if versions else None

    def load(self, name: str, version: Optional[str] = None) -> tuple[Any, dict[str, Any]]:
        resolved = version or self.get_production_version(name)
        if resolved is None:
            raise FileNotFoundError(f"No versions registered for model {name!r}")
        vdir = self._model_dir(name) / resolved
        with (vdir / "model.pkl").open("rb") as fh:
            model = pickle.load(fh)
        metadata = json.loads((vdir / "metadata.json").read_text())
        return model, metadata


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

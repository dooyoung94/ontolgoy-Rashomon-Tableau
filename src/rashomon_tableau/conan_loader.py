from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import Literal


@dataclass
class ConanPerspective:
    story: str
    perspective: str
    text: str | None
    propositions: list[Literal]


def _normalize_predicate(label: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in label.strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_").lower()


def load_relation_json(path: Path, story: str, perspective: str) -> list[Literal]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: list[Literal] = []
    for subject, pairs in raw.items():
        if not isinstance(pairs, list):
            continue
        for pair in pairs:
            if not isinstance(pair, list) or len(pair) < 2:
                continue
            obj, relation = pair[0], pair[1]
            out.append(Literal(_normalize_predicate(str(relation)), str(subject).strip(), str(obj).strip(), False, perspective, story, str(path)))
    return out


def iter_perspectives(conan_root: str | Path, language: str = "english", max_stories: int | None = None) -> Iterable[ConanPerspective]:
    root = Path(conan_root)
    label_root = root / "data" / language / "label"
    text_root = root / "data" / language / "data_final"
    if not label_root.exists():
        raise FileNotFoundError(f"CONAN label directory not found: {label_root}. Run scripts/download_conan.py first or pass --conan-root.")
    story_dirs = sorted(p for p in label_root.iterdir() if p.is_dir())
    if max_stories is not None:
        story_dirs = story_dirs[:max_stories]
    for story_dir in story_dirs:
        story = story_dir.name
        txt_dir = text_root / story / "txt"
        for label_path in sorted(story_dir.glob("*.json")):
            if label_path.stem.lower() == "all":
                continue
            perspective = label_path.stem
            text_path = txt_dir / f"{perspective}.txt"
            text = text_path.read_text(encoding="utf-8", errors="ignore") if text_path.exists() else None
            yield ConanPerspective(story, perspective, text, load_relation_json(label_path, story, perspective))


def load_all_gold(conan_root: str | Path, language: str = "english", max_stories: int | None = None) -> dict[str, dict[str, list[Literal]]]:
    stories: dict[str, dict[str, list[Literal]]] = {}
    for item in iter_perspectives(conan_root, language, max_stories):
        stories.setdefault(item.story, {})[item.perspective] = item.propositions
    return stories


def relation_inventory(conan_root: str | Path, language: str = "english", max_stories: int | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in iter_perspectives(conan_root, language, max_stories):
        for lit in item.propositions:
            counts[lit.predicate] = counts.get(lit.predicate, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

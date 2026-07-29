from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_tree_passes_privacy_scan() -> None:
    module = _load("privacy_scan", ROOT / "scripts" / "privacy_scan.py")
    assert module.scan(ROOT) == []


def test_markdown_local_links_exist() -> None:
    module = _load("check_markdown_links", ROOT / "scripts" / "check_markdown_links.py")
    assert module.check_links(ROOT) == []

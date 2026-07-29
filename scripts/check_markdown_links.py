from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote

LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
SKIP_PARTS = {".git", ".venv", "private", "build", "dist"}


def check_links(root: Path) -> list[str]:
    errors: list[str] = []
    for markdown in root.rglob("*.md"):
        if any(part in SKIP_PARTS for part in markdown.relative_to(root).parts):
            continue
        content = markdown.read_text(encoding="utf-8")
        for raw_target in LINK.findall(content):
            target = raw_target.strip().split()[0].strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = unquote(target.split("#", maxsplit=1)[0])
            if not target:
                continue
            resolved = (markdown.parent / target).resolve()
            if not resolved.exists():
                errors.append(f"{markdown.relative_to(root)} -> {raw_target}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local links in Markdown files")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = check_links(args.root.resolve())
    if errors:
        print("Markdown link check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Markdown link check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

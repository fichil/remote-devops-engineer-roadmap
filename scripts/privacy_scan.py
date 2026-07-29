from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

TEXT_SUFFIXES = {".md", ".py", ".json", ".yml", ".yaml", ".toml", ".txt"}
SKIP_PARTS = {".git", ".venv", "private", "build", "dist", "__pycache__"}
PATTERNS = {
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{24,}", re.IGNORECASE),
    "private_email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@(?!example\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
}


def candidate_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and not any(part in SKIP_PARTS for part in path.relative_to(root).parts)
    ]


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in candidate_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{path.relative_to(root)}:{line_number}: {name}")

    if (root / ".git").exists():
        result = subprocess.run(
            ["git", "ls-files", "private"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            findings.append("Git tracks files under private/")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan public learning files for common secrets")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    findings = scan(args.root.resolve())
    if findings:
        print("Privacy scan failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Privacy scan passed: no known credential or personal-email patterns found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

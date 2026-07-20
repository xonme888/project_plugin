#!/usr/bin/env python3
"""Check whether split LoaRing repos still describe monorepo coupling."""

from __future__ import annotations

import sys
from pathlib import Path


TEXT_SUFFIXES = {
    ".md",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".txt",
}

FORBIDDEN_PATTERNS = {
    "../product": "Use the loaring-product repository or approved product contract reference, not a sibling path.",
    "../backend": "Backend must be an external repository, not a sibling path.",
    "../frontend": "Frontend must be an external repository, not a sibling path.",
    "product/docs/api": "Use product repo-relative docs/api paths or an external product contract reference.",
    "루트 AGENTS.md": "Each repository owns its own AGENTS.md.",
    "root AGENTS.md": "Each repository owns its own AGENTS.md.",
    "monorepo": "Split repositories should not rely on monorepo assumptions.",
}

IGNORED_DIRS = {
    ".git",
    ".gradle",
    ".idea",
    ".next",
    ".venv",
    "build",
    "node_modules",
}


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            yield path


def audit(root: Path) -> list[str]:
    findings: list[str] = []
    for path in iter_text_files(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, 1):
            for pattern, reason in FORBIDDEN_PATTERNS.items():
                if pattern in line:
                    findings.append(f"{path}:{line_no}: {pattern!r}: {reason}")
    return findings


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: audit_independence.py <repo-root> [<repo-root> ...]", file=sys.stderr)
        return 2

    all_findings: list[str] = []
    for arg in sys.argv[1:]:
        root = Path(arg).resolve()
        if not root.exists():
            all_findings.append(f"{root}: path does not exist")
            continue
        all_findings.extend(audit(root))

    if all_findings:
        print("\n".join(all_findings))
        return 1

    print("No monorepo coupling patterns found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

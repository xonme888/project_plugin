#!/usr/bin/env python3
"""Validate LoaRing commit messages."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ALLOWED_TYPES = {
    "feat",
    "fix",
    "docs",
    "refactor",
    "test",
    "chore",
    "ci",
    "build",
    "perf",
    "revert",
}
HEADER_RE = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[a-z0-9][a-z0-9-]*)\))?(?P<breaking>!)?: (?P<summary>.+)$"
)
HANGUL_RE = re.compile(r"[가-힣]")
MAX_HEADER_LENGTH = 72
MAX_BODY_LINE_LENGTH = 100


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a LoaRing git commit message.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--message", help="Commit message text to validate.")
    source.add_argument("--file", type=Path, help="Path to a git commit message file.")
    source.add_argument("--latest", action="store_true", help="Validate HEAD commit message.")
    args = parser.parse_args()

    message = read_message(args)
    errors = validate_commit_message(message)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Commit message validation passed.")
    return 0


def read_message(args: argparse.Namespace) -> str:
    if args.message is not None:
        return args.message
    if args.file is not None:
        return args.file.read_text(encoding="utf-8")
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=%B"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def validate_commit_message(message: str) -> list[str]:
    lines = normalize_git_message(message)
    if not lines:
        return ["Commit message must not be empty."]

    errors: list[str] = []
    header = lines[0]
    if header.startswith("Merge "):
        return []

    if len(header) > MAX_HEADER_LENGTH:
        errors.append(f"Commit header must be {MAX_HEADER_LENGTH} characters or less.")

    match = HEADER_RE.match(header)
    if not match:
        errors.append("Header must match '<type>(<scope>): <summary>'.")
    else:
        commit_type = match.group("type")
        summary = match.group("summary")
        if commit_type not in ALLOWED_TYPES:
            errors.append(f"Commit type '{commit_type}' is not allowed.")
        if summary.endswith("."):
            errors.append("Summary must not end with a period.")
        if not HANGUL_RE.search(summary):
            errors.append("Summary must be written in Korean.")

    if len(lines) > 1 and lines[1] != "":
        errors.append("Second line must be blank when a body is present.")

    has_breaking_marker = bool(match and match.group("breaking"))
    has_breaking_footer = any(line.startswith("BREAKING CHANGE:") for line in lines[1:])
    if has_breaking_marker and not has_breaking_footer:
        errors.append("Breaking commits must include a 'BREAKING CHANGE:' footer.")

    for index, line in enumerate(lines[1:], start=2):
        if len(line) > MAX_BODY_LINE_LENGTH and "://" not in line:
            errors.append(f"Body line {index} must be {MAX_BODY_LINE_LENGTH} characters or less.")

    return errors


def normalize_git_message(message: str) -> list[str]:
    lines = [line.rstrip() for line in message.replace("\r\n", "\n").split("\n")]
    lines = [line for line in lines if not line.lstrip().startswith("#")]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


if __name__ == "__main__":
    raise SystemExit(main())

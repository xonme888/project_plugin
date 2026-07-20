#!/usr/bin/env python3
"""Fetch LoaRing product contract files from GitHub without cloning product."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path


DEFAULT_REPO = "loaring-story/loaring-product"
DEFAULT_REF = "develop"
DEFAULT_PATHS = [
    "docs/contracts/registry.yml",
    "docs/contracts/error-codes.yml",
    "docs/contracts/naming-rules.yml",
    "docs/contracts/response-envelope.yml",
    "docs/api/api-catalog.yml",
]


def gh_api(path: str) -> dict:
    result = subprocess.run(
        ["gh", "api", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def fetch_file(repo: str, ref: str, path: str) -> str:
    payload = gh_api(f"repos/{repo}/contents/{path}?ref={ref}")
    if payload.get("type") != "file":
        raise RuntimeError(f"{path}: expected a file in {repo}@{ref}")
    encoded = payload.get("content")
    if not isinstance(encoded, str):
        raise RuntimeError(f"{path}: GitHub response did not include file content")
    return base64.b64decode(encoded).decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub repo, default: {DEFAULT_REPO}")
    parser.add_argument("--ref", default=DEFAULT_REF, help=f"branch, tag, or SHA, default: {DEFAULT_REF}")
    parser.add_argument("--path", action="append", dest="paths", help="product repo file path to fetch")
    parser.add_argument("--out-dir", type=Path, help="write fetched files under this directory")
    args = parser.parse_args()

    paths = args.paths or DEFAULT_PATHS
    fetched: dict[str, str] = {}

    try:
        for path in paths:
            fetched[path] = fetch_file(args.repo, args.ref, path)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or exc.stdout or str(exc), file=sys.stderr)
        return exc.returncode or 1
    except Exception as exc:  # noqa: BLE001 - CLI error boundary
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.out_dir:
        for path, content in fetched.items():
            target = args.out_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        print(f"Fetched {len(fetched)} file(s) from {args.repo}@{args.ref} into {args.out_dir}")
        return 0

    for path, content in fetched.items():
        print(f"--- {args.repo}@{args.ref}:{path}")
        print(content.rstrip())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

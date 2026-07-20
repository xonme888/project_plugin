#!/usr/bin/env python3
"""Sync read-only GitHub Story issues and Project fields into sqlite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loaring_ops.github_sync import sync_github, sync_project, sync_stories


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="Story issue repo, default: loaring-story/loaring-product")
    parser.add_argument("--project-number", type=int)
    parser.add_argument("--label")
    parser.add_argument("--include-legacy", action="store_true")
    parser.add_argument("--stories-only", action="store_true")
    parser.add_argument("--project-only", action="store_true")
    args = parser.parse_args()

    if args.stories_only and args.project_only:
        parser.error("--stories-only and --project-only are mutually exclusive")
    if args.stories_only:
        result = sync_stories(repo=args.repo, label=args.label, include_legacy=args.include_legacy)
    elif args.project_only:
        result = sync_project(repo=args.repo, number=args.project_number)
    else:
        result = sync_github(repo=args.repo, number=args.project_number, include_legacy=args.include_legacy)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a read-only legacy Story migration plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loaring_ops.migration import migration_dry_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-sync", action="store_true", help="Use existing sqlite cache without fetching GitHub.")
    parser.add_argument("--include-bodies", action="store_true", help="Include full legacy issue bodies in the JSON report.")
    parser.add_argument("--issue", action="append", type=int, dest="issues", help="Legacy issue number to include. Repeatable.")
    args = parser.parse_args()
    result = migration_dry_run(
        sync=not args.no_sync,
        include_bodies=args.include_bodies,
        issue_numbers=args.issues,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Sync product docs into the local LoaRing Product Ops sqlite cache."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loaring_ops.product_sync import sync_product


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo")
    parser.add_argument("--ref")
    args = parser.parse_args()
    print(json.dumps(sync_product(repo=args.repo, ref=args.ref), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

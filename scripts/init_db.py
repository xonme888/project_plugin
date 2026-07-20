#!/usr/bin/env python3
"""Initialize the local LoaRing Product Ops sqlite cache."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loaring_ops.config import db_path
from loaring_ops.db import connect, init_db


def main() -> int:
    conn = connect()
    init_db(conn)
    print(f"Initialized {db_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

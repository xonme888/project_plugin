"""SQLite cache for product metadata."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .config import db_path


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS product_snapshots (
  repo TEXT NOT NULL,
  ref TEXT NOT NULL,
  path TEXT NOT NULL,
  sha TEXT,
  content TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (repo, ref, path)
);

CREATE TABLE IF NOT EXISTS api_specs (
  path TEXT PRIMARY KEY,
  domain TEXT,
  title TEXT,
  story_issue INTEGER,
  requirement_ids_json TEXT NOT NULL DEFAULT '[]',
  endpoints_json TEXT NOT NULL DEFAULT '[]',
  lifecycle TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requirements (
  requirement_id TEXT PRIMARY KEY,
  title TEXT,
  status TEXT,
  epic TEXT,
  story_issues_json TEXT NOT NULL DEFAULT '[]',
  api_specs_json TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stories (
  repo TEXT NOT NULL,
  issue_number INTEGER NOT NULL,
  title TEXT NOT NULL,
  state TEXT NOT NULL,
  url TEXT,
  labels_json TEXT NOT NULL DEFAULT '[]',
  assignees_json TEXT NOT NULL DEFAULT '[]',
  body TEXT,
  updated_at TEXT NOT NULL,
  synced_at TEXT NOT NULL,
  PRIMARY KEY (repo, issue_number)
);

CREATE TABLE IF NOT EXISTS project_items (
  repo TEXT NOT NULL,
  project_number INTEGER NOT NULL,
  issue_number INTEGER NOT NULL,
  item_id TEXT,
  fields_json TEXT NOT NULL DEFAULT '{}',
  synced_at TEXT NOT NULL,
  PRIMARY KEY (repo, project_number, issue_number)
);

CREATE TABLE IF NOT EXISTS sync_state (
  source TEXT PRIMARY KEY,
  repo TEXT NOT NULL,
  ref TEXT NOT NULL,
  last_synced_at TEXT NOT NULL
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)

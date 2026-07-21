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
  repo TEXT NOT NULL,
  ref TEXT NOT NULL,
  path TEXT NOT NULL,
  domain TEXT,
  title TEXT,
  story_issue INTEGER,
  requirement_ids_json TEXT NOT NULL DEFAULT '[]',
  endpoints_json TEXT NOT NULL DEFAULT '[]',
  lifecycle TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (repo, ref, path)
);

CREATE TABLE IF NOT EXISTS requirements (
  repo TEXT NOT NULL,
  ref TEXT NOT NULL,
  requirement_id TEXT NOT NULL,
  title TEXT,
  status TEXT,
  epic TEXT,
  story_issues_json TEXT NOT NULL DEFAULT '[]',
  api_specs_json TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT NOT NULL,
  PRIMARY KEY (repo, ref, requirement_id)
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
    migrate_product_index_scope(conn)
    conn.commit()


def migrate_product_index_scope(conn: sqlite3.Connection) -> None:
    migrate_api_specs_scope(conn)
    migrate_requirements_scope(conn)


def migrate_api_specs_scope(conn: sqlite3.Connection) -> None:
    columns = table_columns(conn, "api_specs")
    if not columns or {"repo", "ref"} <= columns:
        return
    repo, ref = current_product_scope(conn)
    conn.execute("ALTER TABLE api_specs RENAME TO api_specs_legacy")
    conn.execute(
        """
        CREATE TABLE api_specs (
          repo TEXT NOT NULL,
          ref TEXT NOT NULL,
          path TEXT NOT NULL,
          domain TEXT,
          title TEXT,
          story_issue INTEGER,
          requirement_ids_json TEXT NOT NULL DEFAULT '[]',
          endpoints_json TEXT NOT NULL DEFAULT '[]',
          lifecycle TEXT,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (repo, ref, path)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO api_specs (
          repo, ref, path, domain, title, story_issue, requirement_ids_json,
          endpoints_json, lifecycle, updated_at
        )
        SELECT ?, ?, path, domain, title, story_issue, requirement_ids_json,
          endpoints_json, lifecycle, updated_at
        FROM api_specs_legacy
        """,
        (repo, ref),
    )
    conn.execute("DROP TABLE api_specs_legacy")


def migrate_requirements_scope(conn: sqlite3.Connection) -> None:
    columns = table_columns(conn, "requirements")
    if not columns or {"repo", "ref"} <= columns:
        return
    repo, ref = current_product_scope(conn)
    conn.execute("ALTER TABLE requirements RENAME TO requirements_legacy")
    conn.execute(
        """
        CREATE TABLE requirements (
          repo TEXT NOT NULL,
          ref TEXT NOT NULL,
          requirement_id TEXT NOT NULL,
          title TEXT,
          status TEXT,
          epic TEXT,
          story_issues_json TEXT NOT NULL DEFAULT '[]',
          api_specs_json TEXT NOT NULL DEFAULT '[]',
          updated_at TEXT NOT NULL,
          PRIMARY KEY (repo, ref, requirement_id)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO requirements (
          repo, ref, requirement_id, title, status, epic,
          story_issues_json, api_specs_json, updated_at
        )
        SELECT ?, ?, requirement_id, title, status, epic,
          story_issues_json, api_specs_json, updated_at
        FROM requirements_legacy
        """,
        (repo, ref),
    )
    conn.execute("DROP TABLE requirements_legacy")


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def current_product_scope(conn: sqlite3.Connection) -> tuple[str, str]:
    row = conn.execute("SELECT repo, ref FROM sync_state WHERE source = 'product-docs'").fetchone()
    if row:
        return str(row["repo"]), str(row["ref"])
    row = conn.execute("SELECT repo, ref FROM product_snapshots ORDER BY fetched_at DESC LIMIT 1").fetchone()
    if row:
        return str(row["repo"]), str(row["ref"])
    return "", ""


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)

"""Filename: cgsdb.py"""

from __future__ import annotations

import asyncio
import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
CSV_PATH = DATA_DIR / "games.csv"
DISCOVERY_DIR = DATA_DIR / "discovery"
DISCOVERY_CANDIDATES_PATH = DISCOVERY_DIR / "candidates.csv"
DISCOVERY_EVIDENCE_PATH = DISCOVERY_DIR / "evidence.csv"
DISCOVERY_RUNS_PATH = DISCOVERY_DIR / "runs.csv"
DB_PATH = DATA_DIR / "games.db"
SCHEMA_VERSION = 3

GITHUB_RE = re.compile(r"https?://github\.com/([^/]+)/([^/#?]+)", re.IGNORECASE)
NON_ALNUM = re.compile(r"[^a-z0-9]+")

CREATE_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY,
    popularity_rank INTEGER NOT NULL,
    game TEXT NOT NULL,
    game_key TEXT NOT NULL UNIQUE,
    original_year TEXT,
    original_developer TEXT,
    source_release TEXT,
    license_status TEXT,
    source_scope TEXT,
    assets_data TEXT,
    official_repository TEXT,
    modern_source_port TEXT,
    engine_architecture TEXT,
    modding_potential INTEGER,
    rust_port_candidate INTEGER,
    github_stars INTEGER,
    github_stars_live INTEGER,
    github_checked_at TEXT,
    verification_notes TEXT,
    primary_source TEXT,
    github_owner TEXT,
    github_repo TEXT,
    license_family TEXT NOT NULL,
    source_status TEXT NOT NULL,
    rust_score_computed INTEGER NOT NULL,
    provenance_class TEXT NOT NULL DEFAULT 'unknown',
    leak_status TEXT NOT NULL DEFAULT 'not-leak',
    content_types TEXT NOT NULL DEFAULT '',
    access_status TEXT NOT NULL DEFAULT 'unknown',
    redistribution_status TEXT NOT NULL DEFAULT 'unknown',
    classification_tags TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_games_popularity ON games(popularity_rank);
CREATE INDEX IF NOT EXISTS idx_games_rust ON games(rust_port_candidate DESC, modding_potential DESC);
CREATE INDEX IF NOT EXISTS idx_games_developer ON games(original_developer);
CREATE INDEX IF NOT EXISTS idx_games_license ON games(license_family);
CREATE INDEX IF NOT EXISTS idx_games_status ON games(source_status);
CREATE INDEX IF NOT EXISTS idx_games_github ON games(github_owner, github_repo);
CREATE INDEX IF NOT EXISTS idx_games_title ON games(game COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS discovery_candidates (
    candidate_id TEXT PRIMARY KEY,
    game_key TEXT,
    candidate_title TEXT NOT NULL,
    original_year TEXT,
    developer TEXT,
    linked_game_status TEXT NOT NULL,
    discovery_sources TEXT NOT NULL,
    first_discovered_at TEXT,
    discovery_query TEXT,
    discovery_url TEXT,
    review_status TEXT NOT NULL,
    exact_license TEXT,
    license_family TEXT,
    source_completeness TEXT,
    authorization_status TEXT,
    provenance_class TEXT NOT NULL DEFAULT 'unknown',
    leak_status TEXT NOT NULL DEFAULT 'not-leak',
    content_types TEXT NOT NULL DEFAULT '',
    access_status TEXT NOT NULL DEFAULT 'unknown',
    redistribution_status TEXT NOT NULL DEFAULT 'unknown',
    classification_tags TEXT NOT NULL DEFAULT '',
    provenance_confidence TEXT,
    evidence_confidence TEXT,
    notes TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_discovery_candidates_game_key ON discovery_candidates(game_key);
CREATE INDEX IF NOT EXISTS idx_discovery_candidates_review ON discovery_candidates(review_status);
CREATE INDEX IF NOT EXISTS idx_discovery_candidates_source ON discovery_candidates(discovery_sources);
CREATE INDEX IF NOT EXISTS idx_discovery_candidates_auth ON discovery_candidates(authorization_status);
CREATE INDEX IF NOT EXISTS idx_discovery_candidates_completeness ON discovery_candidates(source_completeness);
CREATE INDEX IF NOT EXISTS idx_discovery_candidates_title ON discovery_candidates(candidate_title COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS discovery_evidence (
    evidence_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    evidence_fingerprint TEXT NOT NULL UNIQUE,
    evidence_source TEXT NOT NULL,
    evidence_url TEXT NOT NULL,
    evidence_title TEXT,
    accessed_at TEXT,
    evidence_type TEXT NOT NULL,
    publisher_or_owner TEXT,
    source_release_date TEXT,
    license_claim TEXT,
    source_scope_claim TEXT,
    authorization_signal TEXT,
    source_completeness_claim TEXT,
    provenance_class_claim TEXT,
    leak_status_claim TEXT,
    content_type_claim TEXT,
    access_status_claim TEXT,
    redistribution_status_claim TEXT,
    classification_tags TEXT,
    confidence TEXT,
    notes TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_discovery_evidence_candidate ON discovery_evidence(candidate_id);
CREATE INDEX IF NOT EXISTS idx_discovery_evidence_source ON discovery_evidence(evidence_source);
CREATE INDEX IF NOT EXISTS idx_discovery_evidence_confidence ON discovery_evidence(confidence);

CREATE TABLE IF NOT EXISTS discovery_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    discovery_source TEXT NOT NULL,
    query_or_collection TEXT NOT NULL,
    status TEXT NOT NULL,
    candidates_found INTEGER NOT NULL DEFAULT 0,
    candidates_added INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_source ON discovery_runs(discovery_source);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_started ON discovery_runs(started_at DESC);

"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def normalize_game_key(name: str) -> str:
    return NON_ALNUM.sub("-", name.lower()).strip("-") or "game"


def parse_github(url: str) -> tuple[str | None, str | None]:
    match = GITHUB_RE.search(url or "")
    if not match:
        return None, None
    return match.group(1), match.group(2).removesuffix(".git")


def classify_license(value: str) -> str:
    text = (value or "").lower()
    if any(x in text for x in ("gpl", "lgpl", "mit", "apache", "bsd", "isc", "mpl", "mozilla public license", "zlib", "artistic", "cpal")):
        return "open-source"
    if "public domain" in text or "cc0" in text or "unlicense" in text:
        return "public-domain"
    if any(x in text for x in ("source-available", "source available", "source released")):
        return "source-available"
    if any(x in text for x in ("proprietary", "sdk")):
        return "proprietary/source-sdk"
    if any(x in text for x in ("found", "recovered")):
        return "unclear/recovered"
    return "unclear"


def infer_provenance_fields(license_status: str, notes: str) -> dict[str, str]:
    combined = f"{license_status} {notes}".casefold()
    if any(p in combined for p in (
        "source code leak", "leaked source", "leaked game",
        "game leak", "stolen source", "unauthorized source",
    )):
        return {"provenance_class": "leak", "leak_status": "reported", "classification_tags": "leaked-content"}
    if any(p in combined for p in ("reverse engineered", "reverse-engineered", "clean-room")):
        return {"provenance_class": "reverse-engineered", "leak_status": "not-leak", "classification_tags": "reverse-engineered"}
    if "recovered" in combined:
        return {"provenance_class": "archival-recovery", "leak_status": "not-leak", "classification_tags": "archival-recovery"}
    if any(p in combined for p in ("official source release", "official repository", "released by the developer")):
        return {"provenance_class": "authorized-source-release", "leak_status": "not-leak", "classification_tags": "authorized-source-release"}
    return {"provenance_class": "unknown", "leak_status": "suspected" if "leak" in combined else "not-leak", "classification_tags": ""}


def classify_source_status(license_status: str, notes: str) -> str:
    combined = f"{license_status} {notes}".lower()
    if "not an authorized" in combined or "unauthorized" in combined or "accidental" in combined:
        return "found-not-authorized"
    family = classify_license(license_status)
    if family in {"open-source", "public-domain"}:
        return "open"
    if family in {"source-available", "proprietary/source-sdk"}:
        return "source-available"
    return "unclear"


def compute_rust_score(row: dict[str, str]) -> int:
    score = 5.0
    scope = row.get("Source Scope", "").lower()
    license_text = row.get("License / Status", "")
    arch = row.get("Engine / Architecture", "").lower()
    notes = row.get("Verification / Notes", "").lower()

    if "game/engine" in scope or "game source" in scope:
        score += 1.2
    elif "source" in scope:
        score += 0.6
    if "server/backend" in scope:
        score -= 0.8

    family = classify_license(license_text)
    if family == "open-source":
        score += 1.0
    elif family == "public-domain":
        score += 0.8
    elif family == "proprietary/source-sdk":
        score -= 0.4

    if any(x in arch for x in ("bsp", "client/server", "scripting", "physics")):
        score += 0.5
    if any(x in arch for x in ("2.5d", "raycasting")):
        score += 0.25
    if "not an authorized" in notes or "license status less clear" in notes:
        score -= 0.9

    try:
        modding = int(row.get("Modding Potential (1-5)") or 0)
    except ValueError:
        modding = 0
    score += max(0, min(5, modding) - 3) * 0.25

    return max(1, min(10, round(score)))


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def init_db() -> None:
    with connect() as conn:
        conn.executescript(CREATE_SQL)
        _ensure_columns(conn, "games", {
            "provenance_class": "TEXT NOT NULL DEFAULT 'unknown'",
            "leak_status": "TEXT NOT NULL DEFAULT 'not-leak'",
            "content_types": "TEXT NOT NULL DEFAULT ''",
            "access_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "redistribution_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "classification_tags": "TEXT NOT NULL DEFAULT ''",
        })
        _ensure_columns(conn, "discovery_candidates", {
            "provenance_class": "TEXT NOT NULL DEFAULT 'unknown'",
            "leak_status": "TEXT NOT NULL DEFAULT 'not-leak'",
            "content_types": "TEXT NOT NULL DEFAULT ''",
            "access_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "redistribution_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "classification_tags": "TEXT NOT NULL DEFAULT ''",
        })
        _ensure_columns(conn, "discovery_evidence", {
            "provenance_class_claim": "TEXT",
            "leak_status_claim": "TEXT",
            "content_type_claim": "TEXT",
            "access_status_claim": "TEXT",
            "redistribution_status_claim": "TEXT",
            "classification_tags": "TEXT",
        })
        conn.execute(
            "INSERT INTO metadata(key,value) VALUES('schema_version',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()


def read_csv(path: Path = CSV_PATH):
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {
            "Popularity Rank", "Game", "Original Year", "Original Developer",
            "Source Release", "License / Status", "Source Scope", "Assets / Data",
            "Official / Primary Repository", "Modern Source Port / Continuation",
            "Engine / Architecture", "Modding Potential (1-5)", "Rust Port Candidate (1-10)",
            "GitHub Stars", "Verification / Notes", "Primary Source",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"CSV missing columns: {sorted(missing)}")
        yield from reader


def import_csv(path: Path = CSV_PATH) -> int:
    init_db()
    rows = list(read_csv(path))
    with connect() as conn:
        conn.execute("DELETE FROM games")
        for row in rows:
            owner, repo = parse_github(row.get("Official / Primary Repository", ""))
            modding = int(row["Modding Potential (1-5)"]) if row["Modding Potential (1-5)"].strip() else None
            candidate = int(row["Rust Port Candidate (1-10)"]) if row["Rust Port Candidate (1-10)"].strip() else None
            stars = int(float(row["GitHub Stars"])) if row["GitHub Stars"].strip() else None
            classification = infer_provenance_fields(
                row["License / Status"], row["Verification / Notes"]
            )
            conn.execute(
                """INSERT INTO games (
                    popularity_rank, game, game_key, original_year, original_developer,
                    source_release, license_status, source_scope, assets_data,
                    official_repository, modern_source_port, engine_architecture,
                    modding_potential, rust_port_candidate, github_stars,
                    verification_notes, primary_source, github_owner, github_repo,
                    license_family, source_status, rust_score_computed,
                    provenance_class, leak_status, content_types, access_status,
                    redistribution_status, classification_tags
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    int(row["Popularity Rank"]), row["Game"], normalize_game_key(row["Game"]),
                    row["Original Year"], row["Original Developer"], row["Source Release"],
                    row["License / Status"], row["Source Scope"], row["Assets / Data"],
                    row["Official / Primary Repository"], row["Modern Source Port / Continuation"],
                    row["Engine / Architecture"], modding, candidate, stars,
                    row["Verification / Notes"], row["Primary Source"], owner, repo,
                    classify_license(row["License / Status"]),
                    classify_source_status(row["License / Status"], row["Verification / Notes"]),
                    compute_rust_score(row),
                    row.get("Provenance Class") or classification["provenance_class"],
                    row.get("Leak Status") or classification["leak_status"],
                    row.get("Content Types") or (
                        "source-code" if "source" in row["Source Scope"].casefold() else ""
                    ),
                    row.get("Access Status") or "unknown",
                    row.get("Redistribution Status") or "unknown",
                    row.get("Classification Tags") or classification["classification_tags"],
                ),
            )
        for key, value in {
            "dataset_imported_at": utc_now(),
            "dataset_rows": str(len(rows)),
        }.items():
            conn.execute(
                "INSERT INTO metadata(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
        conn.commit()
    return len(rows)


GAME_COLUMNS = """
    id, popularity_rank, game, game_key, original_year, original_developer,
    source_release, license_status, source_scope, assets_data,
    official_repository, modern_source_port, engine_architecture,
    modding_potential, rust_port_candidate, github_stars,
    github_stars_live, github_checked_at, verification_notes, primary_source,
    github_owner, github_repo, license_family, source_status, rust_score_computed,
    provenance_class, leak_status, content_types, access_status,
    redistribution_status, classification_tags
"""


DISCOVERY_CANDIDATE_COLUMNS = """
    candidate_id, game_key, candidate_title, original_year, developer,
    linked_game_status, discovery_sources, first_discovered_at,
    discovery_query, discovery_url, review_status, exact_license,
    license_family, source_completeness, authorization_status,
    provenance_confidence, evidence_confidence, notes, updated_at
"""

DISCOVERY_EVIDENCE_COLUMNS = """
    evidence_id, candidate_id, evidence_fingerprint, evidence_source,
    evidence_url, evidence_title, accessed_at, evidence_type,
    publisher_or_owner, source_release_date, license_claim,
    source_scope_claim, authorization_signal, source_completeness_claim,
    confidence, notes, updated_at
"""

DISCOVERY_RUN_COLUMNS = """
    run_id, started_at, completed_at, discovery_source,
    query_or_collection, status, candidates_found, candidates_added, notes
"""


def normalize_fingerprint(*parts: object) -> str:
    payload = "|".join(
        " ".join(str(part or "").split()).strip().casefold()
        for part in parts
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_csv_file(path: Path, required: set[str]):
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"CSV {path} missing columns: {sorted(missing)}")
        yield from reader


def read_discovery_candidates(path: Path = DISCOVERY_CANDIDATES_PATH):
    required = {
        "candidate_id", "game_key", "candidate_title", "original_year", "developer",
        "linked_game_status", "discovery_sources", "first_discovered_at",
        "discovery_query", "discovery_url", "review_status", "exact_license",
        "license_family", "source_completeness", "authorization_status",
        "provenance_confidence", "evidence_confidence", "notes",
    }
    yield from read_csv_file(path, required)


def read_discovery_evidence(path: Path = DISCOVERY_EVIDENCE_PATH):
    required = {
        "evidence_id", "candidate_id", "evidence_source", "evidence_url",
        "evidence_title", "accessed_at", "evidence_type", "publisher_or_owner",
        "source_release_date", "license_claim", "source_scope_claim",
        "authorization_signal", "source_completeness_claim", "confidence", "notes",
    }
    yield from read_csv_file(path, required)


def read_discovery_runs(path: Path = DISCOVERY_RUNS_PATH):
    required = {
        "run_id", "started_at", "completed_at", "discovery_source",
        "query_or_collection", "status", "candidates_found", "candidates_added", "notes",
    }
    yield from read_csv_file(path, required)


def import_discovery_data(
    candidates_path: Path = DISCOVERY_CANDIDATES_PATH,
    evidence_path: Path = DISCOVERY_EVIDENCE_PATH,
    runs_path: Path = DISCOVERY_RUNS_PATH,
) -> dict[str, int]:
    init_db()
    imported = {"candidates": 0, "evidence": 0, "runs": 0}

    with connect() as conn:
        if candidates_path.exists():
            for row in read_discovery_candidates(candidates_path):
                conn.execute(
                    """
                    INSERT INTO discovery_candidates (
                        candidate_id, game_key, candidate_title, original_year, developer,
                        linked_game_status, discovery_sources, first_discovered_at,
                        discovery_query, discovery_url, review_status, exact_license,
                        license_family, source_completeness, authorization_status,
                        provenance_confidence, evidence_confidence, notes, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(candidate_id) DO UPDATE SET
                        game_key=excluded.game_key,
                        candidate_title=excluded.candidate_title,
                        original_year=excluded.original_year,
                        developer=excluded.developer,
                        linked_game_status=excluded.linked_game_status,
                        discovery_sources=excluded.discovery_sources,
                        first_discovered_at=excluded.first_discovered_at,
                        discovery_query=excluded.discovery_query,
                        discovery_url=excluded.discovery_url,
                        review_status=excluded.review_status,
                        exact_license=excluded.exact_license,
                        license_family=excluded.license_family,
                        source_completeness=excluded.source_completeness,
                        authorization_status=excluded.authorization_status,
                        provenance_confidence=excluded.provenance_confidence,
                        evidence_confidence=excluded.evidence_confidence,
                        notes=excluded.notes,
                        updated_at=excluded.updated_at
                    """,
                    (
                        row["candidate_id"], row["game_key"] or None, row["candidate_title"],
                        row["original_year"], row["developer"], row["linked_game_status"],
                        row["discovery_sources"], row["first_discovered_at"],
                        row["discovery_query"], row["discovery_url"], row["review_status"],
                        row["exact_license"], row["license_family"], row["source_completeness"],
                        row["authorization_status"], row["provenance_confidence"],
                        row["evidence_confidence"], row["notes"], utc_now(),
                    ),
                )
                imported["candidates"] += 1

        if evidence_path.exists():
            for row in read_discovery_evidence(evidence_path):
                fingerprint = normalize_fingerprint(
                    row["candidate_id"], row["evidence_source"], row["evidence_url"],
                    row["source_release_date"], row["license_claim"],
                    row["source_scope_claim"], row["authorization_signal"],
                    row["source_completeness_claim"],
                )
                conn.execute(
                    """
                    DELETE FROM discovery_evidence
                    WHERE evidence_id = ?
                       OR (evidence_fingerprint = ? AND evidence_id != ?)
                    """,
                    (row["evidence_id"], fingerprint, row["evidence_id"]),
                )
                conn.execute(
                    """
                    INSERT INTO discovery_evidence (
                        evidence_id, candidate_id, evidence_fingerprint,
                        evidence_source, evidence_url, evidence_title, accessed_at,
                        evidence_type, publisher_or_owner, source_release_date,
                        license_claim, source_scope_claim, authorization_signal,
                        source_completeness_claim, confidence, notes, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(evidence_id) DO UPDATE SET
                        candidate_id=excluded.candidate_id,
                        evidence_fingerprint=excluded.evidence_fingerprint,
                        evidence_source=excluded.evidence_source,
                        evidence_url=excluded.evidence_url,
                        evidence_title=excluded.evidence_title,
                        accessed_at=excluded.accessed_at,
                        evidence_type=excluded.evidence_type,
                        publisher_or_owner=excluded.publisher_or_owner,
                        source_release_date=excluded.source_release_date,
                        license_claim=excluded.license_claim,
                        source_scope_claim=excluded.source_scope_claim,
                        authorization_signal=excluded.authorization_signal,
                        source_completeness_claim=excluded.source_completeness_claim,
                        confidence=excluded.confidence,
                        notes=excluded.notes,
                        updated_at=excluded.updated_at
                    """,
                    (
                        row["evidence_id"], row["candidate_id"], fingerprint,
                        row["evidence_source"], row["evidence_url"], row["evidence_title"],
                        row["accessed_at"], row["evidence_type"],
                        row["publisher_or_owner"], row["source_release_date"],
                        row["license_claim"], row["source_scope_claim"],
                        row["authorization_signal"], row["source_completeness_claim"],
                        row["confidence"], row["notes"], utc_now(),
                    ),
                )
                imported["evidence"] += 1

        if runs_path.exists():
            for row in read_discovery_runs(runs_path):
                conn.execute(
                    """
                    INSERT INTO discovery_runs (
                        run_id, started_at, completed_at, discovery_source,
                        query_or_collection, status, candidates_found, candidates_added, notes
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        started_at=excluded.started_at,
                        completed_at=excluded.completed_at,
                        discovery_source=excluded.discovery_source,
                        query_or_collection=excluded.query_or_collection,
                        status=excluded.status,
                        candidates_found=excluded.candidates_found,
                        candidates_added=excluded.candidates_added,
                        notes=excluded.notes
                    """,
                    (
                        row["run_id"], row["started_at"], row["completed_at"] or None,
                        row["discovery_source"], row["query_or_collection"], row["status"],
                        int(row["candidates_found"] or 0), int(row["candidates_added"] or 0),
                        row["notes"],
                    ),
                )
                imported["runs"] += 1

        conn.execute(
            "INSERT INTO metadata(key,value) VALUES('discovery_imported_at',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (utc_now(),),
        )
        conn.commit()

    return imported


def discovery_stats() -> dict:
    ensure_database()
    with connect() as conn:
        return {
            "candidates": conn.execute("SELECT COUNT(*) FROM discovery_candidates").fetchone()[0],
            "evidence": conn.execute("SELECT COUNT(*) FROM discovery_evidence").fetchone()[0],
            "runs": conn.execute("SELECT COUNT(*) FROM discovery_runs").fetchone()[0],
            "resolved_to_canonical": conn.execute(
                "SELECT COUNT(*) FROM discovery_candidates WHERE linked_game_status='resolved-to-canonical'"
            ).fetchone()[0],
            "review_status": [
                dict(row) for row in conn.execute(
                    "SELECT review_status, COUNT(*) AS count FROM discovery_candidates "
                    "GROUP BY review_status ORDER BY count DESC, review_status"
                )
            ],
            "discovery_sources": [
                dict(row) for row in conn.execute(
                    """
                    SELECT source, COUNT(*) AS count
                    FROM (
                        SELECT TRIM(value) AS source
                        FROM discovery_candidates, json_each(
                            '["' || REPLACE(discovery_sources, ';', '","') || '"]'
                        )
                    )
                    GROUP BY source
                    ORDER BY count DESC, source
                    """
                )
            ],
            "authorization_status": [
                dict(row) for row in conn.execute(
                    "SELECT COALESCE(authorization_status,'unknown') AS status, COUNT(*) AS count "
                    "FROM discovery_candidates GROUP BY authorization_status ORDER BY count DESC, status"
                )
            ],
            "source_completeness": [
                dict(row) for row in conn.execute(
                    "SELECT COALESCE(source_completeness,'unknown') AS completeness, COUNT(*) AS count "
                    "FROM discovery_candidates GROUP BY source_completeness ORDER BY count DESC, completeness"
                )
            ],
        }


def discovery_search(query: str = "", review_status: str | None = None,
                     source: str | None = None, limit: int = 50) -> list[dict]:
    ensure_database()
    clauses: list[str] = []
    params: list[object] = []
    if query:
        needle = f"%{query}%"
        clauses.append(
            "(c.candidate_title LIKE ? OR c.developer LIKE ? OR c.discovery_query LIKE ? "
            "OR c.discovery_url LIKE ? OR c.exact_license LIKE ? OR c.notes LIKE ?)"
        )
        params.extend([needle] * 6)
    if review_status:
        clauses.append("c.review_status = ?")
        params.append(review_status)
    if source:
        clauses.append("c.discovery_sources LIKE ?")
        params.append(f"%{source}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT c.*, COUNT(e.evidence_id) AS evidence_count
        FROM discovery_candidates AS c
        LEFT JOIN discovery_evidence AS e ON e.candidate_id = c.candidate_id
        {where}
        GROUP BY c.candidate_id
        ORDER BY
            CASE c.review_status
                WHEN 'new' THEN 0
                WHEN 'needs-verification' THEN 1
                WHEN 'accepted-canonical-inherited-unreviewed' THEN 2
                ELSE 3
            END,
            c.candidate_title COLLATE NOCASE
        LIMIT ?
    """
    params.append(max(1, min(limit, 500)))
    with connect() as conn:
        return [dict(row) for row in conn.execute(sql, params)]


def export_discovery(candidates_output: Path, evidence_output: Path,
                     runs_output: Path) -> dict[str, int]:
    ensure_database()
    with connect() as conn:
        candidates = conn.execute(
            f"SELECT {DISCOVERY_CANDIDATE_COLUMNS} FROM discovery_candidates ORDER BY candidate_title"
        ).fetchall()
        evidence = conn.execute(
            f"SELECT {DISCOVERY_EVIDENCE_COLUMNS} FROM discovery_evidence ORDER BY candidate_id, evidence_id"
        ).fetchall()
        runs = conn.execute(
            f"SELECT {DISCOVERY_RUN_COLUMNS} FROM discovery_runs ORDER BY started_at"
        ).fetchall()

    outputs = [
        (candidates_output, [
            "candidate_id","game_key","candidate_title","original_year","developer",
            "linked_game_status","discovery_sources","first_discovered_at","discovery_query",
            "discovery_url","review_status","exact_license","license_family","source_completeness",
            "authorization_status","provenance_confidence","evidence_confidence","notes",
        ], candidates),
        (evidence_output, [
            "evidence_id","candidate_id","evidence_source","evidence_url","evidence_title",
            "accessed_at","evidence_type","publisher_or_owner","source_release_date",
            "license_claim","source_scope_claim","authorization_signal",
            "source_completeness_claim","confidence","notes",
        ], evidence),
        (runs_output, [
            "run_id","started_at","completed_at","discovery_source","query_or_collection",
            "status","candidates_found","candidates_added","notes",
        ], runs),
    ]
    counts: dict[str, int] = {}
    for output, fields, rows in outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(fields)
            for row in rows:
                writer.writerow([
                    row[field] if field in row.keys() and row[field] is not None else ""
                    for field in fields
                ])
        counts[output.name] = len(rows)
    return counts


def write_discovery_report(output: Path) -> int:
    rows = discovery_search(limit=500)
    unresolved = [
        row for row in rows
        if row["review_status"] != "accepted-canonical-inherited-unreviewed"
    ]
    lines = [
        "# Discovery Review Report",
        "",
        f"Generated: {utc_now()}",
        "",
        "| Candidate | Review | Authorization | Completeness | Sources | Evidence |",
        "|---|---|---|---|---|---:|",
    ]
    for row in unresolved:
        title = str(row["candidate_title"]).replace("|", "\\|")
        lines.append(
            f"| {title} | {row['review_status']} | {row['authorization_status'] or 'unknown'} | "
            f"{row['source_completeness'] or 'unknown'} | {row['discovery_sources']} | "
            f"{row['evidence_count']} |"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(unresolved)


def iter_discovery_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid discovery JSONL at {path}:{line_number}: {exc}"
                ) from exc


def import_discovery_jsonl(path: Path) -> dict[str, int]:
    init_db()
    imported = {"candidates": 0, "evidence": 0, "runs": 0}
    run_path = path.with_suffix(path.suffix + ".run.json")

    with connect() as conn:
        for payload in iter_discovery_jsonl(path):
            candidate_id = str(payload.get("candidate_id") or "").strip()
            title = str(payload.get("candidate_title") or "").strip()
            if not candidate_id or not title:
                continue

            discovery_sources = payload.get("discovery_sources") or []
            if isinstance(discovery_sources, str):
                discovery_sources = [discovery_sources]
            discovery_sources = ";".join(
                sorted({str(x).strip() for x in discovery_sources if str(x).strip()})
            ) or "unknown"

            conn.execute(
                """
                INSERT INTO discovery_candidates (
                    candidate_id, game_key, candidate_title, original_year, developer,
                    linked_game_status, discovery_sources, first_discovered_at,
                    discovery_query, discovery_url, review_status, exact_license,
                    license_family, source_completeness, authorization_status,
                    provenance_confidence, evidence_confidence, notes, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    game_key=excluded.game_key,
                    candidate_title=excluded.candidate_title,
                    original_year=excluded.original_year,
                    developer=excluded.developer,
                    linked_game_status=excluded.linked_game_status,
                    discovery_sources=excluded.discovery_sources,
                    first_discovered_at=excluded.first_discovered_at,
                    discovery_query=excluded.discovery_query,
                    discovery_url=excluded.discovery_url,
                    review_status=excluded.review_status,
                    exact_license=excluded.exact_license,
                    license_family=excluded.license_family,
                    source_completeness=excluded.source_completeness,
                    authorization_status=excluded.authorization_status,
                    provenance_confidence=excluded.provenance_confidence,
                    evidence_confidence=excluded.evidence_confidence,
                    notes=excluded.notes,
                    updated_at=excluded.updated_at
                """,
                (
                    candidate_id,
                    payload.get("game_key") or None,
                    title,
                    payload.get("original_year", ""),
                    payload.get("developer", ""),
                    payload.get("linked_game_status", "unresolved"),
                    discovery_sources,
                    payload.get("first_discovered_at", ""),
                    payload.get("discovery_query", ""),
                    payload.get("discovery_url", ""),
                    payload.get("review_status", "new"),
                    payload.get("exact_license", ""),
                    payload.get("license_family", ""),
                    payload.get("source_completeness", "unknown"),
                    payload.get("authorization_status", "unknown"),
                    payload.get("provenance_confidence", "low"),
                    payload.get("evidence_confidence", "low"),
                    payload.get("notes", ""),
                    utc_now(),
                ),
            )
            imported["candidates"] += 1

            for evidence in payload.get("evidence") or []:
                evidence_id = str(evidence.get("evidence_id") or "").strip()
                evidence_url = str(evidence.get("evidence_url") or "").strip()
                evidence_source = str(evidence.get("evidence_source") or "").strip()
                if not evidence_id or not evidence_url or not evidence_source:
                    continue

                fingerprint = str(
                    evidence.get("evidence_fingerprint")
                    or normalize_fingerprint(
                        candidate_id,
                        evidence_source,
                        evidence_url,
                        evidence.get("source_release_date", ""),
                        evidence.get("license_claim", ""),
                        evidence.get("source_scope_claim", ""),
                        evidence.get("authorization_signal", ""),
                        evidence.get("source_completeness_claim", ""),
                    )
                )

                conn.execute(
                    """
                    DELETE FROM discovery_evidence
                    WHERE evidence_id = ?
                       OR (evidence_fingerprint = ? AND evidence_id != ?)
                    """,
                    (evidence_id, fingerprint, evidence_id),
                )
                conn.execute(
                    """
                    INSERT INTO discovery_evidence (
                        evidence_id, candidate_id, evidence_fingerprint,
                        evidence_source, evidence_url, evidence_title, accessed_at,
                        evidence_type, publisher_or_owner, source_release_date,
                        license_claim, source_scope_claim, authorization_signal,
                        source_completeness_claim, confidence, notes, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        evidence_id,
                        candidate_id,
                        fingerprint,
                        evidence_source,
                        evidence_url,
                        evidence.get("evidence_title", ""),
                        evidence.get("accessed_at", ""),
                        evidence.get("evidence_type", "discovery"),
                        evidence.get("publisher_or_owner", ""),
                        evidence.get("source_release_date", ""),
                        evidence.get("license_claim", ""),
                        evidence.get("source_scope_claim", ""),
                        evidence.get("authorization_signal", ""),
                        evidence.get("source_completeness_claim", ""),
                        evidence.get("confidence", "low"),
                        evidence.get("notes", ""),
                        utc_now(),
                    ),
                )
                imported["evidence"] += 1

        if run_path.exists():
            run = json.loads(run_path.read_text(encoding="utf-8"))
            conn.execute(
                """
                INSERT INTO discovery_runs (
                    run_id, started_at, completed_at, discovery_source,
                    query_or_collection, status, candidates_found, candidates_added, notes
                ) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id) DO UPDATE SET
                    started_at=excluded.started_at,
                    completed_at=excluded.completed_at,
                    discovery_source=excluded.discovery_source,
                    query_or_collection=excluded.query_or_collection,
                    status=excluded.status,
                    candidates_found=excluded.candidates_found,
                    candidates_added=excluded.candidates_added,
                    notes=excluded.notes
                """,
                (
                    run.get("run_id", run_path.stem),
                    run.get("started_at", ""),
                    run.get("completed_at", ""),
                    run.get("discovery_source", ""),
                    run.get("query_or_collection", ""),
                    run.get("status", "completed"),
                    int(run.get("candidates_found", 0)),
                    int(run.get("candidates_added", 0)),
                    run.get("notes", ""),
                ),
            )
            imported["runs"] += 1

        conn.execute(
            "INSERT INTO metadata(key,value) VALUES('discovery_inbox_imported_at',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (utc_now(),),
        )
        conn.commit()

    # Keep the human-reviewable CSV ledgers synchronized with SQLite.
    export_discovery(
        DISCOVERY_CANDIDATES_PATH,
        DISCOVERY_EVIDENCE_PATH,
        DISCOVERY_RUNS_PATH,
    )
    return imported


def ensure_database() -> None:
    if not DB_PATH.exists():
        import_csv()


def search_games(
    query: str = "",
    license: str | None = None,
    min_rust_score: int | None = None,
    provenance: str | None = None,
    leak_status: str | None = None,
    content_type: str | None = None,
    access_status: str | None = None,
    redistribution_status: str | None = None,
    tag: str | None = None,
    limit: int = 50,
) -> list[dict]:
    ensure_database()
    clauses: list[str] = []
    params: list[object] = []

    if query:
        needle = f"%{query}%"
        clauses.append(
            "(game LIKE ? OR original_developer LIKE ? OR engine_architecture LIKE ? "
            "OR modern_source_port LIKE ? OR verification_notes LIKE ?)"
        )
        params.extend([needle] * 5)

    if license:
        clauses.append("license_family = ?")
        params.append(license)

    if min_rust_score is not None:
        clauses.append("COALESCE(rust_port_candidate, rust_score_computed) >= ?")
        params.append(min_rust_score)
    if provenance:
        clauses.append("provenance_class = ?")
        params.append(provenance)
    if leak_status:
        clauses.append("leak_status = ?")
        params.append(leak_status)
    if content_type:
        clauses.append("(';' || content_types || ';') LIKE ?")
        params.append(f"%;{content_type};%")
    if access_status:
        clauses.append("access_status = ?")
        params.append(access_status)
    if redistribution_status:
        clauses.append("redistribution_status = ?")
        params.append(redistribution_status)
    if tag:
        clauses.append("(';' || classification_tags || ';') LIKE ?")
        params.append(f"%;{tag};%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT {GAME_COLUMNS}
        FROM games
        {where}
        ORDER BY COALESCE(rust_port_candidate, rust_score_computed) DESC,
                 popularity_rank ASC
        LIMIT ?
    """
    params.append(max(1, min(limit, 500)))

    with connect() as conn:
        return [dict(row) for row in conn.execute(sql, params)]


def get_game(game_key: str) -> dict | None:
    ensure_database()
    with connect() as conn:
        row = conn.execute(
            f"SELECT {GAME_COLUMNS} FROM games WHERE game_key = ?",
            (game_key,),
        ).fetchone()
        return dict(row) if row else None


def stats() -> dict:
    ensure_database()
    with connect() as conn:
        return {
            "total_games": conn.execute("SELECT COUNT(*) FROM games").fetchone()[0],
            "open_source": conn.execute("SELECT COUNT(*) FROM games WHERE source_status='open'").fetchone()[0],
            "source_available": conn.execute("SELECT COUNT(*) FROM games WHERE source_status='source-available'").fetchone()[0],
            "unclear": conn.execute("SELECT COUNT(*) FROM games WHERE source_status='unclear'").fetchone()[0],
            "found_not_authorized": conn.execute("SELECT COUNT(*) FROM games WHERE source_status='found-not-authorized'").fetchone()[0],
            "with_github_repo": conn.execute("SELECT COUNT(*) FROM games WHERE github_owner IS NOT NULL").fetchone()[0],
            "github_live_checked": conn.execute("SELECT COUNT(*) FROM games WHERE github_checked_at IS NOT NULL").fetchone()[0],
            "avg_rust_score": conn.execute(
                "SELECT ROUND(AVG(COALESCE(rust_port_candidate,rust_score_computed)),2) FROM games"
            ).fetchone()[0],
            "top_candidates": [
                dict(row) for row in conn.execute(
                    """SELECT popularity_rank, game, rust_port_candidate, rust_score_computed,
                              modding_potential, github_stars_live, github_stars
                       FROM games
                       ORDER BY COALESCE(rust_port_candidate,rust_score_computed) DESC,
                                popularity_rank ASC
                       LIMIT 15"""
                )
            ],
            "top_developers": [
                dict(row) for row in conn.execute(
                    """SELECT original_developer AS developer, COUNT(*) AS count
                       FROM games
                       GROUP BY original_developer
                       ORDER BY count DESC, developer
                       LIMIT 12"""
                )
            ],
        }


def export_csv(output: Path) -> int:
    ensure_database()
    with connect() as conn:
        rows = conn.execute(
            f"SELECT {GAME_COLUMNS} FROM games ORDER BY popularity_rank"
        ).fetchall()

    fields = [
        "Popularity Rank", "Game", "Original Year", "Original Developer",
        "Source Release", "License / Status", "Source Scope", "Assets / Data",
        "Official / Primary Repository", "Modern Source Port / Continuation",
        "Engine / Architecture", "Modding Potential (1-5)", "Rust Port Candidate (1-10)",
        "GitHub Stars", "Verification / Notes", "Primary Source",
        "Provenance Class", "Leak Status", "Content Types", "Access Status",
        "Redistribution Status", "Classification Tags",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(fields)
        for row in rows:
            writer.writerow([
                row["popularity_rank"], row["game"], row["original_year"], row["original_developer"],
                row["source_release"], row["license_status"], row["source_scope"], row["assets_data"],
                row["official_repository"], row["modern_source_port"], row["engine_architecture"],
                row["modding_potential"] if row["modding_potential"] is not None else "",
                row["rust_port_candidate"] if row["rust_port_candidate"] is not None else "",
                row["github_stars"] if row["github_stars"] is not None else "",
                row["verification_notes"], row["primary_source"],
                row["provenance_class"], row["leak_status"], row["content_types"],
                row["access_status"], row["redistribution_status"],
                row["classification_tags"],
            ])
    return len(rows)


def sync_github(limit: int = 500, delay: float = 0.15, token: str | None = None) -> dict:
    ensure_database()
    token = token or os.getenv("GITHUB_TOKEN")

    with connect() as conn:
        repos = conn.execute(
            """SELECT id, github_owner, github_repo
               FROM games
               WHERE github_owner IS NOT NULL AND github_repo IS NOT NULL
               ORDER BY popularity_rank
               LIMIT ?""",
            (max(1, min(limit, 500)),),
        ).fetchall()

    checked = 0
    updated = 0
    errors: list[dict] = []

    for row in repos:
        url = f"https://api.github.com/repos/{row['github_owner']}/{row['github_repo']}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "commercial-games-source-database-2026/0.1",
                **({"Authorization": f"Bearer {token}"} if token else {}),
            },
        )
        stars: int | None = None
        error: str | None = None
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.load(response)
                stars = int(payload.get("stargazers_count", 0))
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            error = str(exc)

        now = utc_now()
        with connect() as conn:
            conn.execute(
                "UPDATE games SET github_stars_live=?, github_checked_at=? WHERE id=?",
                (stars, now, row["id"]),
            )
            conn.commit()

        checked += 1
        if stars is not None:
            updated += 1
        else:
            errors.append({
                "owner": row["github_owner"],
                "repo": row["github_repo"],
                "error": error,
            })

        if delay > 0:
            time.sleep(delay)

    return {"checked": checked, "updated": updated, "errors": errors}


def self_test() -> int:
    if not CSV_PATH.exists():
        print(f"FAIL: missing {CSV_PATH}", file=sys.stderr)
        return 1

    count = import_csv()
    payload = stats()
    doom = get_game("doom")
    quake = search_games("quake")
    discovery = import_discovery_data()
    d_stats = discovery_stats()

    checks = {
        "dataset imported": count >= 100,
        "database has 100+ rows": payload["total_games"] >= 100,
        "DOOM is present": doom is not None,
        "DOOM is open source classified": doom is not None and doom["license_family"] == "open-source",
        "Quake search works": any(x["game"] == "Quake" for x in quake),
        "GitHub repositories parsed": payload["with_github_repo"] > 0,
        "Discovery candidates imported": d_stats["candidates"] >= 200,
        "Discovery evidence imported": d_stats["evidence"] >= 300,
        "Discovery runs imported": d_stats["runs"] >= 1,
    }

    for label, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}: {label}")

    return 0 if all(checks.values()) else 1


class Handler(BaseHTTPRequestHandler):
    server_version = "CGSDB/0.1"

    def json_response(self, payload: object, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/":
            body = (WEB_DIR / "index.html").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/stats":
            self.json_response(stats())
            return

        if parsed.path == "/api/games":
            query = parse_qs(parsed.query)
            try:
                min_rust = int(query.get("min_rust", [""])[0]) if query.get("min_rust", [""])[0] else None
                limit = int(query.get("limit", ["100"])[0] or 100)
            except ValueError:
                self.json_response({"error": "invalid numeric filter"}, HTTPStatus.BAD_REQUEST)
                return

            rows = search_games(
                query.get("q", [""])[0],
                license=query.get("license", [None])[0] or None,
                min_rust_score=min_rust,
                limit=limit,
            )
            self.json_response({"count": len(rows), "games": rows})
            return

        if parsed.path.startswith("/api/games/"):
            key = parsed.path.rsplit("/", 1)[-1]
            game = get_game(key)
            self.json_response(game if game else {"error": "not found"},
                               HTTPStatus.OK if game else HTTPStatus.NOT_FOUND)
            return

        self.json_response({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def serve(host: str, port: int) -> None:
    ensure_database()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Commercial Games Source Database: http://{host}:{port}/")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Commercial Games Source Database 2026")
    sub = p.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="import data/games.csv into SQLite")
    init.add_argument("--csv", type=Path, default=CSV_PATH)

    search = sub.add_parser("search", help="search and rank games")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--license")
    search.add_argument("--min-rust-score", type=int)
    search.add_argument("--provenance")
    search.add_argument("--leak-status")
    search.add_argument("--content-type")
    search.add_argument("--access-status")
    search.add_argument("--redistribution-status")
    search.add_argument("--tag")
    search.add_argument("--limit", type=int, default=25)
    search.add_argument("--json", action="store_true")

    stat = sub.add_parser("stats", help="show dataset statistics")
    stat.add_argument("--json", action="store_true")

    sync = sub.add_parser("sync-github", help="refresh stars for listed GitHub repositories")
    sync.add_argument("--limit", type=int, default=500)
    sync.add_argument("--delay", type=float, default=0.15)

    export = sub.add_parser("export", help="export the database to CSV")
    export.add_argument("output", type=Path)

    srv = sub.add_parser("serve", help="run the local dashboard")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8080)

    discovery_import = sub.add_parser(
        "import-discovery",
        help="import discovery candidates, evidence, and run ledgers",
    )
    discovery_import.add_argument("--candidates", type=Path, default=DISCOVERY_CANDIDATES_PATH)
    discovery_import.add_argument("--evidence", type=Path, default=DISCOVERY_EVIDENCE_PATH)
    discovery_import.add_argument("--runs", type=Path, default=DISCOVERY_RUNS_PATH)

    discovery_stat = sub.add_parser("discovery-stats", help="show discovery/provenance statistics")
    discovery_stat.add_argument("--json", action="store_true")

    discovery = sub.add_parser("discovery-search", help="search discovery candidates")
    discovery.add_argument("query", nargs="?", default="")
    discovery.add_argument("--review-status")
    discovery.add_argument("--source")
    discovery.add_argument("--limit", type=int, default=50)
    discovery.add_argument("--json", action="store_true")

    discovery_export = sub.add_parser("export-discovery", help="export discovery ledgers")
    discovery_export.add_argument("--candidates", type=Path, default=DISCOVERY_CANDIDATES_PATH)
    discovery_export.add_argument("--evidence", type=Path, default=DISCOVERY_EVIDENCE_PATH)
    discovery_export.add_argument("--runs", type=Path, default=DISCOVERY_RUNS_PATH)

    discovery_report = sub.add_parser(
        "discovery-report",
        help="write a Markdown discovery review report",
    )
    discovery_report.add_argument("output", type=Path)


    discover = sub.add_parser(
        "discover",
        help="run high-recall web discovery collectors and write JSONL staging output",
    )
    discover.add_argument(
        "--sources",
        default="internet-archive,github,steamdb,wayback,developer-site,igdb",
    )
    discover.add_argument("--ia-query", action="append", dest="ia_queries")
    discover.add_argument("--ia-pages", type=int, default=5)
    discover.add_argument("--ia-rows", type=int, default=100)
    discover.add_argument(
        "--ia-no-cursor",
        action="store_true",
        help="use legacy Advanced Search pagination instead of the deep cursor scraper",
    )
    discover.add_argument("--ia-cursor-batches", type=int, default=10)
    discover.add_argument("--ia-cursor-count", type=int, default=1000)
    discover.add_argument("--github-query", action="append", dest="github_queries")
    discover.add_argument("--github-pages", type=int, default=3)
    discover.add_argument("--github-inspect-limit", type=int, default=200)
    discover.add_argument("--steamdb-search", action="append", dest="steamdb_searches")
    discover.add_argument("--steamdb-app", action="append", dest="steamdb_app_ids")
    discover.add_argument("--wayback-domain", action="append", dest="wayback_domains")
    discover.add_argument("--developer-url", action="append", dest="developer_urls")
    discover.add_argument("--igdb-title", action="append", dest="igdb_titles")
    discover.add_argument("--concurrency", type=int, default=8)
    discover.add_argument("--per-host-delay", type=float, default=0.35)
    discover.add_argument("--output", type=Path)
    discover.add_argument(
        "--config",
        type=Path,
        default=DISCOVERY_DIR / "collector.toml",
    )

    inbox = sub.add_parser(
        "ingest-discovery-inbox",
        help="promote one collector JSONL run into the provenance ledgers",
    )
    inbox.add_argument("path", type=Path)

    sub.add_parser("self-test", help="run local database/application checks")
    return p


def main() -> None:
    args = parser().parse_args()

    if args.command == "init":
        count = import_csv(args.csv)
        discovery = import_discovery_data()
        print(f"Imported {count} games into {DB_PATH}")
        print(json.dumps({"discovery": discovery}, indent=2))
    elif args.command == "search":
        rows = search_games(
            args.query,
            license=args.license,
            min_rust_score=args.min_rust_score,
            provenance=args.provenance,
            leak_status=args.leak_status,
            content_type=args.content_type,
            access_status=args.access_status,
            redistribution_status=args.redistribution_status,
            tag=args.tag,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return
        for row in rows:
            score = row["rust_port_candidate"] or row["rust_score_computed"]
            stars = row["github_stars_live"]
            if stars is None:
                stars = row["github_stars"]
            print(f"{row['popularity_rank']:>3}  {score:>2}/10  {str(stars or '-'):>7}  "
                  f"{row['game']} — {row['engine_architecture']}")
    elif args.command == "stats":
        payload = stats()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Games: {payload['total_games']}")
            print(f"Open source/public domain: {payload['open_source']}")
            print(f"Source available: {payload['source_available']}")
            print(f"Unclear/recovered: {payload['unclear']}")
            print(f"Found but not authorized: {payload['found_not_authorized']}")
            print(f"Rows with GitHub repos: {payload['with_github_repo']}")
            print(f"Rows with live GitHub checks: {payload['github_live_checked']}")
            print(f"Average candidate score: {payload['avg_rust_score']}")
    elif args.command == "sync-github":
        print(json.dumps(sync_github(args.limit, args.delay), indent=2))
    elif args.command == "discover":
        from cgsdb_discovery.runner import run_discovery

        output = args.output
        if output is None:
            output = DISCOVERY_DIR / "inbox" / (
                f"discovery-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
            )
        run, candidates = asyncio.run(
            run_discovery(
                sources=[x.strip() for x in args.sources.split(",") if x.strip()],
                internet_archive_queries=args.ia_queries,
                github_queries=args.github_queries,
                wayback_domains=args.wayback_domains,
                developer_urls=args.developer_urls,
                igdb_titles=args.igdb_titles,
                steamdb_searches=args.steamdb_searches,
                steamdb_app_ids=args.steamdb_app_ids,
                ia_pages=max(1, args.ia_pages),
                ia_rows=max(1, min(args.ia_rows, 10000)),
                ia_use_cursor=not args.ia_no_cursor,
                ia_cursor_batches=max(1, args.ia_cursor_batches),
                ia_cursor_count=max(100, min(args.ia_cursor_count, 10000)),
                github_pages=max(1, args.github_pages),
                github_inspect_limit=max(0, args.github_inspect_limit),
                concurrency=max(1, min(args.concurrency, 32)),
                per_host_delay=max(0.0, args.per_host_delay),
                github_token=os.getenv("GITHUB_TOKEN", ""),
                igdb_client_id=os.getenv("IGDB_CLIENT_ID", ""),
                igdb_client_secret=os.getenv("IGDB_CLIENT_SECRET", ""),
                output=output,
                config_path=args.config,
            )
        )
        print(json.dumps({
            "run": run.to_json(),
            "candidates": len(candidates),
            "output": str(output),
            "ingest_command": f"python cgsdb.py ingest-discovery-inbox {output}",
        }, ensure_ascii=False, indent=2))
    elif args.command == "ingest-discovery-inbox":
        print(json.dumps(import_discovery_jsonl(args.path), indent=2))
    elif args.command == "import-discovery":
        print(json.dumps(
            import_discovery_data(args.candidates, args.evidence, args.runs),
            indent=2,
        ))
    elif args.command == "discovery-stats":
        payload = discovery_stats()
        if args.json:
            print(json.dumps(payload, indent=2))
            return
        print(f"Candidates: {payload['candidates']}")
        print(f"Evidence: {payload['evidence']}")
        print(f"Runs: {payload['runs']}")
        print(f"Resolved to canonical: {payload['resolved_to_canonical']}")
        print("Review status:")
        for item in payload["review_status"]:
            print(f"  {item['review_status']}: {item['count']}")
        print("Discovery sources:")
        for item in payload["discovery_sources"]:
            print(f"  {item['source']}: {item['count']}")
    elif args.command == "discovery-search":
        rows = discovery_search(args.query, args.review_status, args.source, args.limit)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return
        for row in rows:
            print(
                f"{row['candidate_title']} | {row['review_status']} | "
                f"{row['authorization_status'] or 'unknown'} | "
                f"{row['source_completeness'] or 'unknown'} | "
                f"evidence={row['evidence_count']} | {row['discovery_sources']}"
            )
    elif args.command == "export-discovery":
        print(json.dumps(
            export_discovery(args.candidates, args.evidence, args.runs),
            indent=2,
        ))
    elif args.command == "discovery-report":
        print(f"Wrote {write_discovery_report(args.output)} priority candidates to {args.output}")
    elif args.command == "export":
        print(f"Exported {export_csv(args.output)} games to {args.output}")
    elif args.command == "serve":
        serve(args.host, args.port)
    elif args.command == "self-test":
        raise SystemExit(self_test())


if __name__ == "__main__":
    main()

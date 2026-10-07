"""Filename: tests/test_provenance.py"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cgsdb


class ProvenanceLayerTests(unittest.TestCase):
    def test_discovery_ledgers_import_without_mutating_canonical_count(self) -> None:
        root = Path(__file__).resolve().parents[1]
        old_data_dir = cgsdb.DATA_DIR
        old_db_path = cgsdb.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            cgsdb.DATA_DIR = temp
            cgsdb.DB_PATH = temp / "games.db"

            game_count = cgsdb.import_csv(root / "data" / "games.csv")
            imported = cgsdb.import_discovery_data(
                root / "data" / "discovery" / "candidates.csv",
                root / "data" / "discovery" / "evidence.csv",
                root / "data" / "discovery" / "runs.csv",
            )
            stats = cgsdb.discovery_stats()

            self.assertGreaterEqual(game_count, 227)
            self.assertEqual(imported["candidates"], game_count)
            self.assertGreaterEqual(imported["evidence"], 300)
            self.assertGreaterEqual(imported["runs"], 1)
            self.assertEqual(stats["candidates"], game_count)
            self.assertEqual(stats["evidence"], imported["evidence"])
            self.assertEqual(stats["runs"], imported["runs"])
            self.assertEqual(stats["resolved_to_canonical"], game_count)

            matches = cgsdb.discovery_search("DOOM", limit=10)
            self.assertTrue(any(row["candidate_title"] == "DOOM" for row in matches))

            with cgsdb.connect() as conn:
                canonical_count = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
                fingerprint_count = conn.execute(
                    "SELECT COUNT(DISTINCT evidence_fingerprint) FROM discovery_evidence"
                ).fetchone()[0]

            self.assertEqual(canonical_count, game_count)
            self.assertEqual(fingerprint_count, stats["evidence"])

        cgsdb.DATA_DIR = old_data_dir
        cgsdb.DB_PATH = old_db_path


if __name__ == "__main__":
    unittest.main()

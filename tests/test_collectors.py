"""Filename: tests/test_collectors.py"""

from __future__ import annotations

import unittest

from cgsdb_discovery.collectors import first_license, normalize_space
from cgsdb_discovery.models import CandidateRecord, EvidenceRecord, game_key
from cgsdb_discovery.runner import merge_candidates


class CollectorModelTests(unittest.TestCase):
    def test_game_key_is_stable(self) -> None:
        self.assertEqual(game_key("DOOM 3: BFG Edition"), "doom-3-bfg-edition")

    def test_license_extraction(self) -> None:
        self.assertEqual(first_license("Released under GPL-3.0 with MIT tools."), "GPL-3.0")

    def test_normalize_space(self) -> None:
        self.assertEqual(normalize_space("  source\n  code  "), "source code")

    def test_evidence_fingerprint_is_deterministic(self) -> None:
        evidence = EvidenceRecord(
            candidate_id="cand-example",
            evidence_source="github",
            evidence_url="https://github.com/example/game",
            license_claim="MIT",
        )
        self.assertEqual(evidence.fingerprint(), evidence.fingerprint())
        self.assertEqual(len(evidence.fingerprint()), 64)

    def test_candidate_json_contains_machine_ids(self) -> None:
        candidate = CandidateRecord(
            candidate_title="Example Game",
            discovery_sources=["github"],
            discovery_url="https://github.com/example/game",
        )
        candidate.evidence.append(
            EvidenceRecord(
                candidate_id=candidate.candidate_id,
                evidence_source="github",
                evidence_url="https://github.com/example/game",
            )
        )
        payload = candidate.to_json()
        self.assertTrue(payload["candidate_id"].startswith("cand-"))
        self.assertEqual(len(payload["evidence"]), 1)
        self.assertTrue(payload["evidence"][0]["evidence_id"].startswith("ev-"))
        self.assertEqual(len(payload["evidence"][0]["evidence_fingerprint"]), 64)

    def test_merge_candidates_deduplicates(self) -> None:
        left = CandidateRecord(
            candidate_title="Example Game",
            discovery_sources=["github"],
            discovery_url="https://github.com/example/game",
        )
        right = CandidateRecord(
            candidate_title="Example Game",
            discovery_sources=["internet-archive"],
            discovery_url="https://github.com/example/game",
        )
        left.evidence.append(
            EvidenceRecord(
                candidate_id=left.candidate_id,
                evidence_source="github",
                evidence_url="https://github.com/example/game",
            )
        )
        right.evidence.append(
            EvidenceRecord(
                candidate_id=right.candidate_id,
                evidence_source="github",
                evidence_url="https://github.com/example/game",
            )
        )
        merged = merge_candidates([left, right])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].discovery_sources, ["github", "internet-archive"])
        self.assertEqual(len(merged[0].evidence), 1)


if __name__ == "__main__":
    unittest.main()

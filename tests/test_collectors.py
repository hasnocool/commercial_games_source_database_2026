"""Filename: tests/test_collectors.py"""

from __future__ import annotations

import base64
import unittest

from cgsdb_discovery.collectors import (
    classify_provenance_text,
    first_license,
    normalize_space,
)
from cgsdb_discovery.models import CandidateRecord, EvidenceRecord, game_key
from cgsdb_discovery.runner import merge_candidates


class CollectorModelTests(unittest.TestCase):
    def test_game_key_is_stable(self) -> None:
        self.assertEqual(game_key("DOOM 3: BFG Edition"), "doom-3-bfg-edition")

    def test_license_extraction(self) -> None:
        self.assertEqual(first_license("Released under GPL-3.0 with MIT tools."), "GPL-3.0")

    def test_normalize_space(self) -> None:
        self.assertEqual(normalize_space("  source\n  code  "), "source code")

    def test_leak_classification_is_conservative(self) -> None:
        origin, leak_status, tags = classify_provenance_text(
            "reported leaked source code for an unreleased game"
        )
        self.assertEqual(origin, "leak")
        self.assertEqual(leak_status, "reported")
        self.assertIn("leaked-content", tags)

    def test_leaked_game_build_gets_facets(self) -> None:
        from cgsdb_discovery.collectors import candidate_from_text

        candidate = candidate_from_text(
            title="Example Unreleased Game",
            source="github",
            url="https://github.com/example/unreleased-game",
            query='"game build leak"',
            snippet="leaked internal build of the unreleased game",
        )
        self.assertEqual(candidate.provenance_class, "leak")
        self.assertEqual(candidate.leak_status, "reported")
        self.assertIn("binary", candidate.content_types)
        self.assertIn("leaked-content", candidate.classification_tags)
        self.assertEqual(candidate.authorization_status, "unauthorized-or-unresolved")
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


class FakeHttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class DeepCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_internet_archive_cursor_paginates(self) -> None:
        from cgsdb_discovery.collectors import InternetArchiveCollector

        client = FakeHttpClient([
            (
                200,
                {},
                '{"items":[{"identifier":"game-one","title":"Game One","description":"released source code","creator":"Dev","year":"2001"}],"total":2,"cursor":"NEXT"}',
            ),
            (
                200,
                {},
                '{"items":[{"identifier":"game-two","title":"Game Two","description":"open source game","creator":"Dev2","year":"2002"}],"total":1}',
            ),
        ])
        result = await InternetArchiveCollector(client).scrape_query(
            "collection:gamesourcecode",
            batches=5,
            count=100,
        )
        self.assertEqual([c.candidate_title for c in result.candidates], ["Game One", "Game Two"])
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(result.metadata["pages_seen"], 2)

    async def test_github_inspects_license_and_readme(self) -> None:
        from cgsdb_discovery.collectors import GitHubCollector

        license_body = base64.b64encode(b"MIT License").decode()
        client = FakeHttpClient([
            (
                200,
                {},
                '{"items":[{"name":"example-game","description":"old commercial game source","html_url":"https://github.com/example/example-game","owner":{"login":"example"},"license":null,"topics":[]}]}',
            ),
            (200, {}, '{"license":{"spdx_id":"MIT"},"html_url":"https://github.com/example/example-game/blob/main/LICENSE","content":"' + license_body + '"}'),
            (200, {}, "# Example Game\n\nOfficial source release for the commercial game."),
        ])
        result = await GitHubCollector(client, token="token").collect(
            ['"commercial game" source code'],
            pages=1,
            inspect_limit=10,
        )
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.exact_license, "MIT")
        self.assertEqual(candidate.license_family, "open-source")
        self.assertTrue(any(ev.evidence_source == "github-license" for ev in candidate.evidence))
        self.assertTrue(any(ev.evidence_source == "github-readme" for ev in candidate.evidence))
        self.assertTrue(any("possible-authorized-release" == ev.authorization_signal for ev in candidate.evidence))

    async def test_itchio_detects_complete_source_listing(self) -> None:
        from cgsdb_discovery.collectors import ItchioCollector

        listing_html = """
        <html><body>
          <a href="https://exampledev.itch.io/example-game">Example Game — Full Source</a>
          <a href="https://exampledev.itch.io/">Example Dev</a>
        </body></html>
        """
        game_html = """
        <html>
          <head><title>Example Game — Full Source</title></head>
          <body>
            <p>Commercial game with full source code included.</p>
            <p>Released under MIT.</p>
            <a href="https://exampledev.itch.io/">Example Dev</a>
            <a href="https://github.com/exampledev/example-game">Source repository</a>
            <a href="/downloads/example-game-source.zip">Source project ZIP</a>
            <p>Made with Godot. Price: $5.00</p>
          </body>
        </html>
        """
        client = FakeHttpClient([
            (200, {}, listing_html),
            (200, {}, game_html),
        ])
        result = await ItchioCollector(
            client,
            tags=[],
            urls=["https://itch.io/games/tag-sourcecode"],
        ).collect(
            pages=1,
            inspect_limit=10,
        )
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.candidate_title, "Example Game — Full Source")
        self.assertEqual(candidate.license_family, "open-source")
        self.assertEqual(candidate.source_completeness, "complete-source-claim")
        self.assertIn("source-code", candidate.content_types)
        self.assertIn("complete-source-claim", candidate.classification_tags)
        self.assertEqual(candidate.itch_creator_username, "exampledev")
        self.assertEqual(candidate.itch_creator_display_name, "Example Dev")
        self.assertEqual(candidate.itch_price_status, "paid")
        self.assertEqual(candidate.itch_min_price, "$5.00")
        self.assertIn("Godot", candidate.itch_engine_tags)
        self.assertEqual(candidate.itch_source_repository_url, "https://github.com/exampledev/example-game")
        self.assertEqual(candidate.itch_downloadable_project_status, "yes")
        self.assertEqual(candidate.itch_downloadable_project_confidence, "high")
        self.assertTrue(any(
            ev.evidence_source == "itchio-source-link"
            for ev in candidate.evidence
        ))

    async def test_itchio_listing_url_builder(self) -> None:
        from cgsdb_discovery.collectors import ItchioCollector

        self.assertEqual(
            ItchioCollector.tag_page_url("sourcecode", 1),
            "https://itch.io/games/tag-sourcecode",
        )
        self.assertEqual(
            ItchioCollector.tag_page_url("open source", 3),
            "https://itch.io/games/tag-open-source?page=3",
        )

    async def test_steamdb_enumerates_source_package(self) -> None:
        from cgsdb_discovery.collectors import SteamDBCollector

        subs_html = """
        <html><body>
          <a href="/sub/12345/">Game source code</a>
          <a href="/sub/54321/">Standard Game Package</a>
        </body></html>
        """
        package_html = """
        <html><head><title>Game source code · SteamDB</title></head>
        <body>The complete source code for the game is licensed under GPLv3.</body></html>
        """
        client = FakeHttpClient([
            (200, {}, subs_html),
            (200, {}, package_html),
        ])
        result = await SteamDBCollector(client).enumerate_app_packages(
            "999",
            app_title="Example Commercial Game",
        )
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.candidate_title, "Example Commercial Game")
        self.assertEqual(candidate.exact_license, "GPLv3")
        self.assertEqual(candidate.source_completeness, "complete-source-claim")
        self.assertTrue(any(ev.evidence_source == "steamdb-package" for ev in candidate.evidence))


if __name__ == "__main__":
    unittest.main()

"""Filename: cgsdb_discovery/runner.py"""

from __future__ import annotations

import argparse
import asyncio
from collections import OrderedDict
from dataclasses import asdict
import json
import os
from pathlib import Path
import secrets
from typing import Iterable

from .collectors import (
    DeveloperSiteCollector,
    GitHubCollector,
    InternetArchiveCollector,
    IGDBCollector,
    SteamDBCollector,
    ItchioCollector,
    WaybackCollector,
)
from .http import AsyncHttpClient
from .models import CandidateRecord, DiscoveryRun, json_line


DEFAULT_IA_QUERIES = [
    'collection:gamesourcecode',
    'collection:opensource AND mediatype:software AND ("game" OR "video game")',
    'title:("source code") AND mediatype:software',
    'description:("game source code") AND mediatype:software',
    'subject:("game source code")',
    '("leaked source" OR "source code leak") AND mediatype:software',
    '("unauthorized source" OR "stolen source") AND mediatype:software',
    '("pirated source" OR "source dump" OR "code dump") AND mediatype:software',
    '("internal source leak" OR "private source leak") AND mediatype:software',
]

DEFAULT_GITHUB_QUERIES = [
    '"game source code"',
    '"source code" "game" GPL',
    '"source code" "game" MIT',
    '"open source" game engine',
    '"released source" game',
    '"commercial game" source code',
    '"source release" game',
    '"leaked game source"',
    '"game source leak"',
    '"source code leak"',
    '"stolen source" game',
    '"unauthorized source" game',
    '"unreleased game source"',
    '"pirated source" game',
    '"source dump" game',
    '"code dump" game',
    '"internal source leak" game',
    '"private source leak" game',
]

DEFAULT_DEVELOPER_URLS = [
    'https://github.com/id-Software/DOOM',
    'https://github.com/Croteam-official/Serious-Engine',
    'https://github.com/WolfireGames',
]


def merge_candidates(candidates: Iterable[CandidateRecord]) -> list[CandidateRecord]:
    merged: OrderedDict[str, CandidateRecord] = OrderedDict()
    for candidate in candidates:
        candidate.normalize()
        existing = merged.get(candidate.candidate_id)
        if existing is None:
            merged[candidate.candidate_id] = candidate
            continue
        existing.discovery_sources = sorted(
            set(existing.discovery_sources) | set(candidate.discovery_sources)
        )
        if not existing.developer and candidate.developer:
            existing.developer = candidate.developer
        if not existing.exact_license and candidate.exact_license:
            existing.exact_license = candidate.exact_license
        if existing.source_completeness == "unknown" and candidate.source_completeness != "unknown":
            existing.source_completeness = candidate.source_completeness
        if existing.authorization_status == "unknown" and candidate.authorization_status != "unknown":
            existing.authorization_status = candidate.authorization_status
        if existing.provenance_class == "unknown" and candidate.provenance_class != "unknown":
            existing.provenance_class = candidate.provenance_class
        if (
            existing.leak_status in {"not-leak", "unknown"}
            and candidate.leak_status not in {"not-leak", "unknown"}
        ):
            existing.leak_status = candidate.leak_status
        if existing.access_status == "unknown" and candidate.access_status != "unknown":
            existing.access_status = candidate.access_status
        if existing.redistribution_status == "unknown" and candidate.redistribution_status != "unknown":
            existing.redistribution_status = candidate.redistribution_status
        existing.content_types = sorted(set(existing.content_types) | set(candidate.content_types))
        existing.classification_tags = sorted(
            set(existing.classification_tags) | set(candidate.classification_tags)
        )
        existing.evidence.extend(candidate.evidence)
    # Deduplicate evidence inside the merged candidate.
    for candidate in merged.values():
        dedup: OrderedDict[str, object] = OrderedDict()
        for ev in candidate.evidence:
            dedup.setdefault(ev.fingerprint(), ev)
        candidate.evidence = list(dedup.values())
    return list(merged.values())



def load_config(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    import tomllib
    with path.open("rb") as handle:
        return tomllib.load(handle)

async def run_discovery(
    *,
    sources: list[str] | None = None,
    internet_archive_queries: list[str] | None = None,
    github_queries: list[str] | None = None,
    wayback_domains: list[str] | None = None,
    developer_urls: list[str] | None = None,
    igdb_titles: list[str] | None = None,
    steamdb_searches: list[str] | None = None,
    steamdb_app_ids: list[str] | None = None,
    itch_tags: list[str] | None = None,
    itch_urls: list[str] | None = None,
    itch_game_urls: list[str] | None = None,
    itch_titles: list[str] | None = None,
    itch_pages: int = 3,
    itch_inspect_limit: int = 300,
    ia_pages: int = 5,
    ia_rows: int = 100,
    ia_use_cursor: bool = True,
    ia_cursor_batches: int = 10,
    ia_cursor_count: int = 1000,
    github_pages: int = 3,
    github_inspect_limit: int = 200,
    wayback_limit: int = 200,
    developer_max_pages: int = 50,
    developer_max_depth: int = 2,
    concurrency: int = 8,
    per_host_delay: float = 0.35,
    github_token: str = "",
    igdb_client_id: str = "",
    igdb_client_secret: str = "",
    output: Path | None = None,
    config_path: Path | None = None,
) -> tuple[DiscoveryRun, list[CandidateRecord]]:
    config = load_config(config_path)
    configured_ia = config.get("internet_archive", {})
    configured_gh = config.get("github", {})
    configured_wb = config.get("wayback", {})
    configured_dev = config.get("developer_site", {})
    configured_steam = config.get("steamdb", {})
    configured_itchio = config.get("itchio", {})
    configured_igdb = config.get("igdb", {})

    selected = set(sources or [
        "internet-archive",
        "github",
        "steamdb",
        "itchio",
        "wayback",
        "developer-site",
        "igdb",
    ])
    started = __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(timespec="seconds")
    run_id = f"run-{started.replace(':', '').replace('-', '')}-{secrets.token_hex(3)}"

    all_candidates: list[CandidateRecord] = []
    errors: list[dict[str, str]] = []
    collector_metadata: dict[str, object] = {}

    async with AsyncHttpClient(
        concurrency=concurrency,
        per_host_delay=per_host_delay,
    ) as client:
        tasks = []
        if "internet-archive" in selected:
            ia = InternetArchiveCollector(client)
            tasks.append(
                ia.collect(
                    (internet_archive_queries or configured_ia.get("queries") or DEFAULT_IA_QUERIES),
                    pages=max(1, int(configured_ia.get("pages", ia_pages))),
                    rows=max(1, min(int(configured_ia.get("rows", ia_rows)), 10000)),
                    use_cursor=bool(configured_ia.get("use_cursor", ia_use_cursor)),
                    cursor_batches=max(1, int(configured_ia.get("cursor_batches", ia_cursor_batches))),
                    cursor_count=max(100, min(int(configured_ia.get("cursor_count", ia_cursor_count)), 10000)),
                )
            )
        if "github" in selected:
            gh = GitHubCollector(client, github_token or os.getenv("GITHUB_TOKEN", ""))
            tasks.append(
                gh.collect(
                    (github_queries or configured_gh.get("queries") or DEFAULT_GITHUB_QUERIES),
                    pages=max(1, int(configured_gh.get("pages", github_pages))),
                    inspect_limit=max(0, int(configured_gh.get("inspect_limit", github_inspect_limit))),
                )
            )
        if "itchio" in selected:
            itch = ItchioCollector(
                client,
                tags=itch_tags or configured_itchio.get("tags"),
                urls=itch_urls or configured_itchio.get("urls"),
                game_urls=itch_game_urls or configured_itchio.get("game_urls"),
                title_filters=itch_titles or configured_itchio.get("title_filters"),
            )
            tasks.append(
                itch.collect(
                    pages=max(1, int(configured_itchio.get("pages", itch_pages))),
                    inspect_limit=max(0, int(
                        configured_itchio.get("inspect_limit", itch_inspect_limit)
                    )),
                )
            )

        if "steamdb" in selected:
            steam = SteamDBCollector(
                client,
                searches=steamdb_searches or configured_steam.get("searches"),
                app_ids=steamdb_app_ids or configured_steam.get("app_ids"),
            )
            tasks.append(
                steam.collect(
                    max_apps=max(0, int(configured_steam.get("max_apps", 250))),
                )
            )
        if "wayback" in selected:
            wb = WaybackCollector(client)
            for domain in (wayback_domains or configured_wb.get("domains") or []):
                tasks.append(wb.domain(domain, limit=wayback_limit))
        if "developer-site" in selected:
            dev = DeveloperSiteCollector(client)
            urls = developer_urls or configured_dev.get("urls") or []
            if urls:
                tasks.append(
                    dev.crawl(
                        urls,
                        max_pages=developer_max_pages,
                        max_depth=developer_max_depth,
                    )
                )
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                errors.append({"collector": "batch", "error": str(result)})
            else:
                all_candidates.extend(result.candidates)
                errors.extend(result.errors)
                collector_metadata[result.collector] = result.metadata

        if "igdb" in selected and (igdb_titles or all_candidates):
            if igdb_client_id and igdb_client_secret:
                igdb = IGDBCollector(client, igdb_client_id, igdb_client_secret)
                titles = igdb_titles or configured_igdb.get("titles") or [
                    candidate.candidate_title
                    for candidate in all_candidates
                    if candidate.candidate_title
                ]
                result = await igdb.resolve_titles(sorted(set(titles))[:500])
                # IGDB records are metadata evidence, not source-release candidates by themselves.
                for candidate in result.candidates:
                    candidate.review_status = "needs-verification"
                    candidate.notes = (
                        "IGDB metadata enrichment/discovery lead; do not use IGDB alone "
                        "as proof of source availability or licensing. " + candidate.notes
                    )
                all_candidates.extend(result.candidates)
                errors.extend(result.errors)
            elif "igdb" in selected:
                errors.append({
                    "collector": "igdb",
                    "error": "skipped: IGDB_CLIENT_ID and IGDB_CLIENT_SECRET are not configured",
                })

    merged = merge_candidates(all_candidates)
    completed = __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(timespec="seconds")
    run = DiscoveryRun(
        run_id=run_id,
        started_at=started,
        completed_at=completed,
        discovery_source=";".join(sorted(selected)),
        query_or_collection="configured high-recall discovery sweep",
        status="completed" if not errors or all(
            error.get("error", "").startswith("skipped:") for error in errors
        ) else "completed-with-errors",
        candidates_found=len(merged),
        candidates_added=0,
        notes=json.dumps(
            {"collector_metadata": collector_metadata, "errors": errors},
            ensure_ascii=False,
        ),
    )

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            for candidate in merged:
                handle.write(json_line(candidate) + "\n")
        output.with_suffix(output.suffix + ".run.json").write_text(
            json.dumps(run.to_json(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return run, merged


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="High-recall commercial-game source discovery collectors"
    )
    parser.add_argument(
        "--sources",
        default="internet-archive,github,steamdb,wayback,developer-site,igdb",
        help="comma-separated collector names",
    )
    parser.add_argument("--ia-query", action="append", dest="ia_queries")
    parser.add_argument("--ia-pages", type=int, default=5)
    parser.add_argument("--ia-rows", type=int, default=100)
    parser.add_argument(
        "--ia-no-cursor",
        action="store_true",
        help="use legacy Advanced Search pagination instead of the deep cursor scraper",
    )
    parser.add_argument("--ia-cursor-batches", type=int, default=10)
    parser.add_argument("--ia-cursor-count", type=int, default=1000)
    parser.add_argument("--github-query", action="append", dest="github_queries")
    parser.add_argument("--github-pages", type=int, default=3)
    parser.add_argument("--github-inspect-limit", type=int, default=200)
    parser.add_argument("--steamdb-search", action="append", dest="steamdb_searches")
    parser.add_argument("--steamdb-app", action="append", dest="steamdb_app_ids")
    parser.add_argument("--itch-tag", action="append", dest="itch_tags")
    parser.add_argument("--itch-url", action="append", dest="itch_urls")
    parser.add_argument("--itch-game-url", action="append", dest="itch_game_urls")
    parser.add_argument("--itch-title", action="append", dest="itch_titles")
    parser.add_argument("--itch-pages", type=int, default=3)
    parser.add_argument("--itch-inspect-limit", type=int, default=300)
    parser.add_argument("--wayback-domain", action="append", dest="wayback_domains")
    parser.add_argument("--developer-url", action="append", dest="developer_urls")
    parser.add_argument("--igdb-title", action="append", dest="igdb_titles")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--per-host-delay", type=float, default=0.35)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--config", type=Path, default=Path("data/discovery/collector.toml"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
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
            itch_tags=args.itch_tags,
            itch_urls=args.itch_urls,
            itch_game_urls=args.itch_game_urls,
            itch_titles=args.itch_titles,
            itch_pages=max(1, args.itch_pages),
            itch_inspect_limit=max(0, args.itch_inspect_limit),
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
            output=args.output,
            config_path=args.config,
        )
    )
    print(json.dumps({
        "run": run.to_json(),
        "candidate_count": len(candidates),
        "output": str(args.output) if args.output else None,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

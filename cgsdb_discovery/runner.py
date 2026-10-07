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
]

DEFAULT_GITHUB_QUERIES = [
    '"game source code"',
    '"source code" "game" GPL',
    '"source code" "game" MIT',
    '"open source" game engine',
    '"released source" game',
    '"commercial game" source code',
    '"source release" game',
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
        existing.evidence.extend(candidate.evidence)
    # Deduplicate evidence inside the merged candidate.
    for candidate in merged.values():
        dedup: OrderedDict[str, object] = OrderedDict()
        for ev in candidate.evidence:
            dedup.setdefault(ev.fingerprint(), ev)
        candidate.evidence = list(dedup.values())
    return list(merged.values())


async def run_discovery(
    *,
    sources: list[str] | None = None,
    internet_archive_queries: list[str] | None = None,
    github_queries: list[str] | None = None,
    wayback_domains: list[str] | None = None,
    developer_urls: list[str] | None = None,
    igdb_titles: list[str] | None = None,
    ia_pages: int = 5,
    ia_rows: int = 100,
    github_pages: int = 3,
    wayback_limit: int = 200,
    developer_max_pages: int = 50,
    developer_max_depth: int = 2,
    concurrency: int = 8,
    per_host_delay: float = 0.35,
    github_token: str = "",
    igdb_client_id: str = "",
    igdb_client_secret: str = "",
    output: Path | None = None,
) -> tuple[DiscoveryRun, list[CandidateRecord]]:
    selected = set(sources or [
        "internet-archive",
        "github",
        "steamdb",
        "wayback",
        "developer-site",
        "igdb",
    ])
    started = __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(timespec="seconds")
    run_id = f"run-{started.replace(':', '').replace('-', '')}-{secrets.token_hex(3)}"

    all_candidates: list[CandidateRecord] = []
    errors: list[dict[str, str]] = []

    async with AsyncHttpClient(
        concurrency=concurrency,
        per_host_delay=per_host_delay,
    ) as client:
        tasks = []
        if "internet-archive" in selected:
            ia = InternetArchiveCollector(client)
            tasks.append(
                ia.collect(
                    internet_archive_queries or DEFAULT_IA_QUERIES,
                    pages=ia_pages,
                    rows=ia_rows,
                )
            )
        if "github" in selected:
            gh = GitHubCollector(client, github_token or os.getenv("GITHUB_TOKEN", ""))
            tasks.append(
                gh.collect(
                    github_queries or DEFAULT_GITHUB_QUERIES,
                    pages=github_pages,
                )
            )
        if "steamdb" in selected:
            tasks.append(SteamDBCollector(client).collect())
        if "wayback" in selected:
            wb = WaybackCollector(client)
            for domain in wayback_domains or []:
                tasks.append(wb.domain(domain, limit=wayback_limit))
        if "developer-site" in selected:
            dev = DeveloperSiteCollector(client)
            if developer_urls:
                tasks.append(
                    dev.crawl(
                        developer_urls,
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

        if "igdb" in selected and (igdb_titles or all_candidates):
            if igdb_client_id and igdb_client_secret:
                igdb = IGDBCollector(client, igdb_client_id, igdb_client_secret)
                titles = igdb_titles or [
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
                    "error": "IGDB_CLIENT_ID and IGDB_CLIENT_SECRET are required",
                })

    merged = merge_candidates(all_candidates)
    completed = __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(timespec="seconds")
    run = DiscoveryRun(
        run_id=run_id,
        started_at=started,
        completed_at=completed,
        discovery_source=";".join(sorted(selected)),
        query_or_collection="configured high-recall discovery sweep",
        status="completed" if not errors else "completed-with-errors",
        candidates_found=len(merged),
        candidates_added=0,
        notes=json.dumps({"errors": errors}, ensure_ascii=False),
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
    parser.add_argument("--github-query", action="append", dest="github_queries")
    parser.add_argument("--github-pages", type=int, default=3)
    parser.add_argument("--wayback-domain", action="append", dest="wayback_domains")
    parser.add_argument("--developer-url", action="append", dest="developer_urls")
    parser.add_argument("--igdb-title", action="append", dest="igdb_titles")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--per-host-delay", type=float, default=0.35)
    parser.add_argument("--output", type=Path)
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
            ia_pages=max(1, args.ia_pages),
            ia_rows=max(1, min(args.ia_rows, 10000)),
            github_pages=max(1, args.github_pages),
            concurrency=max(1, min(args.concurrency, 32)),
            per_host_delay=max(0.0, args.per_host_delay),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            igdb_client_id=os.getenv("IGDB_CLIENT_ID", ""),
            igdb_client_secret=os.getenv("IGDB_CLIENT_SECRET", ""),
            output=args.output,
        )
    )
    print(json.dumps({
        "run": run.to_json(),
        "candidate_count": len(candidates),
        "output": str(args.output) if args.output else None,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

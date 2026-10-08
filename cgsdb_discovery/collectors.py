"""Filename: cgsdb_discovery/collectors.py"""

from __future__ import annotations

import asyncio
import base64
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
import json
import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

from .http import AsyncHttpClient
from .models import CandidateRecord, EvidenceRecord


SOURCE_KEYWORDS = (
    "source code",
    "source release",
    "open source",
    "open-source",
    "released source",
    "game source",
    "source available",
    "source-available",
    "github",
    "gitlab",
    "gpl",
    "lgpl",
    "mit license",
    "bsd license",
    "apache license",
    "public domain",
    "cc0",
)

LICENSE_RE = re.compile(
    r"(GPL(?:v[0-9.]+)?(?:-or-later)?|LGPL(?:v[0-9.]+)?|MIT|BSD(?:-[0-9]-Clause)?|"
    r"Apache(?:-2\.0)?|MPL(?:-[0-9.]+)?|zlib|CC0|Unlicense|Artistic(?:-[0-9.]+)?|"
    r"CPAL(?:-[0-9.]+)?)",
    re.IGNORECASE,
)
GITHUB_RE = re.compile(r"https?://github\.com/([^/\s#?]+)/([^/\s#?]+)", re.IGNORECASE)
STEAM_APP_RE = re.compile(r"(?:https?://steamdb\.info)?/app/(\d+)", re.IGNORECASE)
STEAM_SUB_RE = re.compile(r"(?:https?://steamdb\.info)?/sub/(\d+)", re.IGNORECASE)
STEAM_PACKAGE_KEYWORDS = (
    "source code",
    "source_code",
    "source",
    "code",
    "gpl",
    "lgpl",
    "mit",
    "open source",
    "opensource",
    "public domain",
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def normalize_space(text: str) -> str:
    return " ".join((text or "").split()).strip()


def first_license(text: str) -> str:
    match = LICENSE_RE.search(text or "")
    return normalize_space(match.group(1)) if match else ""


def classify_provenance_text(text: str) -> tuple[str, str, list[str]]:
    """Return conservative provenance/leak labels from text; never upgrades a report to confirmed."""
    haystack = normalize_space(text).casefold()
    tags: list[str] = []
    leak_phrases = (
        "source code leak",
        "leaked source",
        "leaked game",
        "game leak",
        "source leak",
        "stolen source",
        "unauthorized source",
        "unreleased source",
        "internal source",
    )
    reverse_phrases = ("reverse engineered", "reverse-engineered", "clean-room reimplementation")
    recovery_phrases = ("source recovered", "recovered source", "archival recovery", "preservation archive")
    fan_phrases = ("fan port", "fan-maintained", "community recreation", "fan-made")
    official_phrases = (
        "official source release",
        "official repository",
        "released by the developer",
        "released by id software",
        "open sourced by",
        "source released by",
    )
    if any(p in haystack for p in leak_phrases):
        tags.append("leaked-content")
        return "leak", "reported", tags
    if any(p in haystack for p in reverse_phrases):
        tags.append("reverse-engineered")
        return "reverse-engineered", "not-leak", tags
    if any(p in haystack for p in recovery_phrases):
        tags.append("archival-recovery")
        return "archival-recovery", "not-leak", tags
    if any(p in haystack for p in fan_phrases):
        tags.append("fan-maintained")
        return "fan-maintained", "not-leak", tags
    if any(p in haystack for p in official_phrases):
        tags.append("authorized-source-release")
        return "authorized-source-release", "not-leak", tags
    if "leak" in haystack or "leaked" in haystack:
        tags.append("possible-leak")
        return "unknown", "suspected", tags
    return "unknown", "not-leak", tags


def license_family(value: str) -> str:
    text = (value or "").casefold()
    if any(x in text for x in (
        "gpl", "lgpl", "mit", "apache", "bsd", "isc", "mpl", "zlib",
        "artistic", "cpal",
    )):
        return "open-source"
    if any(x in text for x in ("public domain", "cc0", "unlicense")):
        return "public-domain"
    if any(x in text for x in ("source available", "source-available", "source released")):
        return "source-available"
    if any(x in text for x in ("proprietary", "sdk")):
        return "proprietary/source-sdk"
    return "unclear"


def candidate_from_text(
    *,
    title: str,
    developer: str = "",
    source: str,
    url: str,
    query: str,
    snippet: str,
    license_hint: str = "",
    release_date: str = "",
    source_scope: str = "unknown",
    authorization: str = "unknown",
    completeness: str = "unknown",
    provenance_class: str = "unknown",
    leak_status: str = "not-leak",
    content_types: list[str] | None = None,
    access_status: str = "unknown",
    redistribution_status: str = "unknown",
    classification_tags: list[str] | None = None,
) -> CandidateRecord:
    inferred_origin, inferred_leak, inferred_tags = classify_provenance_text(
        f"{query} {snippet}"
    )
    if provenance_class == "unknown":
        provenance_class = inferred_origin
    if leak_status == "not-leak" and inferred_leak != "not-leak":
        leak_status = inferred_leak
    if provenance_class == "leak" and authorization == "unknown":
        authorization = "unauthorized-or-unresolved"
    if inferred_tags:
        classification_tags = sorted(set((classification_tags or [])) | set(inferred_tags))
    if not content_types:
        content_blob = f"{snippet} {source_scope}".casefold()
        inferred_types: list[str] = []
        if "source" in content_blob or "code" in content_blob:
            inferred_types.append("source-code")
        if any(x in content_blob for x in ("binary", "build", "executable", "game files")):
            inferred_types.append("binary")
        if any(x in content_blob for x in ("assets", "artwork", "sound", "music")):
            inferred_types.append("assets")
        content_types = inferred_types or []
    if access_status == "unknown" and source in {"github", "steamdb", "internet-archive", "developer-site", "wayback"}:
        access_status = "public"
    if redistribution_status == "unknown":
        if license_family(license_hint or first_license(snippet)) in {"open-source", "public-domain"}:
            redistribution_status = "allowed"
        elif provenance_class == "leak":
            redistribution_status = "forbidden"

    candidate = CandidateRecord(
        candidate_title=normalize_space(title),
        developer=normalize_space(developer),
        discovery_sources=[source],
        first_discovered_at=utc_now(),
        discovery_query=query,
        discovery_url=url,
        review_status="new",
        exact_license=license_hint or first_license(snippet),
        license_family=license_family(license_hint or first_license(snippet)),
        source_completeness=completeness,
        authorization_status=authorization,
        provenance_class=provenance_class,
        leak_status=leak_status,
        content_types=list(content_types or []),
        access_status=access_status,
        redistribution_status=redistribution_status,
        classification_tags=list(classification_tags or []),
        provenance_confidence="medium" if source in {"developer-site", "github"} else "low",
        evidence_confidence="medium" if source in {"developer-site", "github"} else "low",
        notes=normalize_space(snippet)[:2000],
    )
    candidate.evidence.append(
        EvidenceRecord(
            candidate_id=candidate.candidate_id,
            evidence_source=source,
            evidence_url=url,
            evidence_title=normalize_space(title),
            accessed_at=utc_now(),
            evidence_type="discovery",
            publisher_or_owner=developer,
            source_release_date=release_date,
            license_claim=candidate.exact_license,
            source_scope_claim=source_scope,
            authorization_signal=authorization,
            source_completeness_claim=completeness,
            provenance_class_claim=provenance_class,
            leak_status_claim=leak_status,
            content_type_claim=";".join(sorted(set(content_types or []))),
            access_status_claim=access_status,
            redistribution_status_claim=redistribution_status,
            classification_tags=list(classification_tags or []),
            confidence="medium" if source in {"developer-site", "github"} else "low",
            notes=normalize_space(snippet)[:3000],
        )
    )
    return candidate


class LinkTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href") or ""
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, normalize_space(" ".join(self._text))))
            self._href = ""
            self._text = []


class MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): v or "" for k, v in attrs}
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "meta":
            name = attrs_dict.get("name", "").lower()
            prop = attrs_dict.get("property", "").lower()
            content = attrs_dict.get("content", "")
            if name == "description" or prop == "og:description":
                self.description = normalize_space(content)

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
            self.title = normalize_space(" ".join(self._title_parts))


@dataclass(slots=True)
class CollectorResult:
    collector: str
    candidates: list[CandidateRecord]
    errors: list[dict[str, str]]
    metadata: dict[str, Any] = field(default_factory=dict)


class InternetArchiveCollector:
    name = "internet-archive"

    def __init__(self, client: AsyncHttpClient) -> None:
        self.client = client

    async def scrape_query(
        self,
        query: str,
        *,
        batches: int = 10,
        count: int = 1000,
        cursor: str = "",
    ) -> CollectorResult:
        """Deep-page the Internet Archive scrape API using its continuation cursor."""
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        cursor_value = cursor
        pages_seen = 0
        total_at_first: int | None = None
        resume_cursor = cursor_value
        fields = ",".join(
            [
                "identifier",
                "title",
                "creator",
                "date",
                "year",
                "description",
                "licenseurl",
                "collection",
                "mediatype",
            ]
        )
        for _ in range(max(1, batches)):
            params: list[tuple[str, str | int]] = [
                ("q", query),
                ("fields", fields),
                ("count", max(100, min(count, 10000))),
            ]
            if cursor_value:
                params.append(("cursor", cursor_value))
            try:
                status, _, body = await self.client.request(
                    "GET",
                    "https://archive.org/services/search/v1/scrape",
                    params=params,
                )
                if status != 200:
                    errors.append({"query": query, "error": f"HTTP {status}", "mode": "cursor"})
                    break
                payload = json.loads(body)
                items = payload.get("items", [])
                if total_at_first is None:
                    total_at_first = payload.get("total")
                for doc in items:
                    title = normalize_space(doc.get("title") or doc.get("identifier") or "")
                    description = normalize_space(doc.get("description") or "")
                    license_url = normalize_space(doc.get("licenseurl") or "")
                    collections = doc.get("collection") or []
                    if isinstance(collections, str):
                        collections = [collections]
                    haystack = " ".join([title, description, license_url, *collections]).casefold()
                    if not any(keyword in haystack for keyword in SOURCE_KEYWORDS):
                        continue
                    identifier = doc.get("identifier") or title
                    url = f"https://archive.org/details/{identifier}"
                    candidates.append(
                        candidate_from_text(
                            title=title,
                            developer=normalize_space(doc.get("creator") or ""),
                            source=self.name,
                            url=url,
                            query=query,
                            snippet=(
                                description
                                + (f" license_url={license_url}" if license_url else "")
                                + (f" collections={';'.join(collections)}" if collections else "")
                            ),
                            release_date=normalize_space(doc.get("date") or doc.get("year") or ""),
                            source_scope="archive-item",
                        )
                    )
                pages_seen += 1
                next_cursor = payload.get("cursor") or ""
                resume_cursor = next_cursor
                if not items or not next_cursor or next_cursor == cursor_value:
                    break
                cursor_value = next_cursor
            except (json.JSONDecodeError, asyncio.TimeoutError) as exc:
                errors.append({"query": query, "error": str(exc), "mode": "cursor"})
                break
        return CollectorResult(
            self.name,
            candidates,
            errors,
            metadata={
                "mode": "cursor",
                "query": query,
                "pages_seen": pages_seen,
                "total_at_start": total_at_first,
                "resume_cursor": resume_cursor,
            },
        )

    async def search_query(self, query: str, *, pages: int = 5, rows: int = 100) -> CollectorResult:
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        fields = [
            "identifier",
            "title",
            "creator",
            "date",
            "year",
            "description",
            "licenseurl",
            "collection",
            "mediatype",
        ]
        for page in range(1, pages + 1):
            params: list[tuple[str, str | int]] = [
                ("q", query),
                ("output", "json"),
                ("rows", rows),
                ("page", page),
            ]
            params.extend(("fl[]", field) for field in fields)
            try:
                status, _, body = await self.client.request(
                    "GET",
                    "https://archive.org/advancedsearch.php",
                    params=params,
                )
                if status != 200:
                    errors.append({"query": query, "error": f"HTTP {status}"})
                    break
                payload = json.loads(body)
                docs = payload.get("response", {}).get("docs", [])
                if not docs:
                    break
                for doc in docs:
                    title = normalize_space(doc.get("title") or doc.get("identifier") or "")
                    description = normalize_space(doc.get("description") or "")
                    license_url = normalize_space(doc.get("licenseurl") or "")
                    collections = doc.get("collection") or []
                    if isinstance(collections, str):
                        collections = [collections]
                    haystack = " ".join([title, description, license_url, *collections]).lower()
                    if not any(keyword in haystack for keyword in SOURCE_KEYWORDS):
                        continue
                    identifier = doc.get("identifier") or title
                    url = f"https://archive.org/details/{identifier}"
                    candidate = candidate_from_text(
                        title=title,
                        developer=normalize_space(doc.get("creator") or ""),
                        source=self.name,
                        url=url,
                        query=query,
                        snippet=(
                            description
                            + (f" license_url={license_url}" if license_url else "")
                            + (f" collections={';'.join(collections)}" if collections else "")
                        ),
                        release_date=normalize_space(doc.get("date") or doc.get("year") or ""),
                        source_scope="archive-item",
                        completeness="unknown",
                    )
                    candidates.append(candidate)
            except (json.JSONDecodeError, asyncio.TimeoutError) as exc:
                errors.append({"query": query, "error": str(exc)})
                break
        return CollectorResult(self.name, candidates, errors)

    async def collect(
        self,
        queries: list[str],
        *,
        pages: int = 5,
        rows: int = 100,
        use_cursor: bool = True,
        cursor_batches: int = 10,
        cursor_count: int = 1000,
    ) -> CollectorResult:
        if use_cursor:
            results = await asyncio.gather(
                *(
                    self.scrape_query(
                        query,
                        batches=cursor_batches,
                        count=cursor_count,
                    )
                    for query in queries
                ),
                return_exceptions=True,
            )
        else:
            results = await asyncio.gather(
                *(self.search_query(query, pages=pages, rows=rows) for query in queries),
                return_exceptions=True,
            )
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        metadata: dict[str, Any] = {
            "mode": "cursor" if use_cursor else "advanced-search",
            "queries": [],
        }
        for result in results:
            if isinstance(result, Exception):
                errors.append({"query": "batch", "error": str(result)})
            else:
                candidates.extend(result.candidates)
                errors.extend(result.errors)
                metadata["queries"].append(result.metadata)
        return CollectorResult(
            self.name,
            candidates,
            errors,
            metadata=metadata,
        )


class GitHubCollector:
    name = "github"

    def __init__(self, client: AsyncHttpClient, token: str = "") -> None:
        self.client = client
        self.token = token

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _repo_from_url(self, url: str) -> tuple[str, str] | None:
        match = GITHUB_RE.search(url or "")
        if not match:
            return None
        return match.group(1), match.group(2).rstrip("/")

    async def inspect_repository(self, candidate: CandidateRecord, owner: str, repo: str) -> CandidateRecord:
        """Inspect GitHub's machine-readable license endpoint and README."""
        base = f"https://api.github.com/repos/{owner}/{repo}"
        license_url = f"{base}/license"
        readme_url = f"{base}/readme"
        license_result, readme_result = await asyncio.gather(
            self.client.request(
                "GET",
                license_url,
                headers=self.headers | {"Accept": "application/vnd.github+json"},
            ),
            self.client.request(
                "GET",
                readme_url,
                headers=self.headers | {"Accept": "application/vnd.github.raw+json"},
            ),
            return_exceptions=True,
        )

        license_name = ""
        license_html_url = license_url
        license_text = ""
        readme_text = ""
        license_status = ""
        readme_status = ""

        if not isinstance(license_result, Exception):
            status, _, body = license_result
            license_status = str(status)
            if status == 200:
                try:
                    payload = json.loads(body)
                    license_name = normalize_space((payload.get("license") or {}).get("spdx_id") or "")
                    license_html_url = normalize_space(payload.get("html_url") or license_url)
                    encoded = payload.get("content") or ""
                    if encoded:
                        license_text = base64.b64decode(
                            encoded.replace("\n", "")
                        ).decode("utf-8", errors="replace")
                except (json.JSONDecodeError, ValueError, UnicodeError):
                    license_text = body

        if not isinstance(readme_result, Exception):
            status, _, body = readme_result
            readme_status = str(status)
            if status == 200:
                readme_text = normalize_space(body)

        readme_origin, readme_leak, readme_tags = classify_provenance_text(readme_text)
        if readme_origin != "unknown":
            candidate.provenance_class = readme_origin
        if readme_leak != "not-leak":
            candidate.leak_status = readme_leak
        candidate.classification_tags = sorted(
            set(candidate.classification_tags) | set(readme_tags)
        )
        if "source" in readme_text.casefold() and "source-code" not in candidate.content_types:
            candidate.content_types = sorted(set(candidate.content_types) | {"source-code"})

        readme_signals = [k for k in SOURCE_KEYWORDS if k in readme_text.casefold()]
        readme_license = first_license(readme_text)
        exact_license = license_name or readme_license or first_license(license_text)
        if exact_license:
            candidate.exact_license = exact_license
            candidate.license_family = license_family(exact_license)

        note_bits = [
            f"github_license={license_name or 'none'}",
            f"license_http={license_status or 'error'}",
            f"readme_http={readme_status or 'error'}",
        ]
        if readme_signals:
            note_bits.append("readme_signals=" + ",".join(readme_signals[:20]))
        if readme_license and readme_license != license_name:
            note_bits.append(f"readme_license={readme_license}")
        candidate.notes = normalize_space(candidate.notes + " " + " ".join(note_bits))[:2000]

        license_claim = license_name or first_license(license_text)
        if license_claim:
            candidate.evidence.append(
                EvidenceRecord(
                    candidate_id=candidate.candidate_id,
                    evidence_source="github-license",
                    evidence_url=license_html_url,
                    evidence_title=f"{owner}/{repo} LICENSE",
                    accessed_at=utc_now(),
                    evidence_type="license",
                    publisher_or_owner=owner,
                    license_claim=license_claim,
                    source_scope_claim="repository-license",
                    provenance_class_claim=candidate.provenance_class,
                    leak_status_claim=candidate.leak_status,
                    content_type_claim=";".join(candidate.content_types),
                    access_status_claim=candidate.access_status,
                    redistribution_status_claim=candidate.redistribution_status,
                    classification_tags=candidate.classification_tags,
                    confidence="high",
                    notes=normalize_space(license_text)[:3000],
                )
            )
        if readme_text:
            candidate.evidence.append(
                EvidenceRecord(
                    candidate_id=candidate.candidate_id,
                    evidence_source="github-readme",
                    evidence_url=readme_url,
                    evidence_title=f"{owner}/{repo} README",
                    accessed_at=utc_now(),
                    evidence_type="readme",
                    publisher_or_owner=owner,
                    license_claim=readme_license,
                    source_scope_claim="repository-documentation",
                    provenance_class_claim=candidate.provenance_class,
                    leak_status_claim=candidate.leak_status,
                    content_type_claim=";".join(candidate.content_types),
                    access_status_claim=candidate.access_status,
                    redistribution_status_claim=candidate.redistribution_status,
                    classification_tags=candidate.classification_tags,
                    authorization_signal=(
                        "possible-authorized-release"
                        if any(
                            phrase in readme_text.casefold()
                            for phrase in (
                                "released by",
                                "official source",
                                "official repository",
                                "source release",
                                "open sourced",
                                "open-source release",
                                "released the source",
                            )
                        )
                        else ""
                    ),
                    confidence="medium",
                    notes=readme_text[:5000],
                )
            )
        return candidate

    async def search(self, query: str, *, pages: int = 3, per_page: int = 100) -> CollectorResult:
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        for page in range(1, pages + 1):
            try:
                status, _, body = await self.client.request(
                    "GET",
                    "https://api.github.com/search/repositories",
                    headers=self.headers,
                    params={"q": query, "per_page": per_page, "page": page},
                )
                if status != 200:
                    errors.append({"query": query, "error": f"HTTP {status}"})
                    if status in {403, 429}:
                        break
                    continue
                payload = json.loads(body)
                items = payload.get("items", [])
                if not items:
                    break
                for item in items:
                    name = normalize_space(item.get("name") or "")
                    description = normalize_space(item.get("description") or "")
                    repo_url = item.get("html_url") or ""
                    topics = item.get("topics") or []
                    haystack = " ".join([query, name, description, " ".join(topics)]).casefold()
                    if not any(
                        keyword in haystack
                        for keyword in ("game", "source", "gpl", "mit", "opensource", "released")
                    ):
                        continue
                    license_name = normalize_space((item.get("license") or {}).get("spdx_id") or "")
                    owner = normalize_space((item.get("owner") or {}).get("login") or "")
                    candidate = candidate_from_text(
                        title=name,
                        developer=owner,
                        source=self.name,
                        url=repo_url,
                        query=query,
                        snippet=description or name,
                        license_hint=license_name,
                        source_scope="repository",
                    )
                    candidates.append(candidate)
            except (json.JSONDecodeError, asyncio.TimeoutError) as exc:
                errors.append({"query": query, "error": str(exc)})
                break
        return CollectorResult(self.name, candidates, errors)

    async def collect(
        self,
        queries: list[str],
        *,
        pages: int = 3,
        inspect_limit: int = 200,
    ) -> CollectorResult:
        results = await asyncio.gather(
            *(self.search(query, pages=pages) for query in queries),
            return_exceptions=True,
        )
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        for result in results:
            if isinstance(result, Exception):
                errors.append({"query": "batch", "error": str(result)})
            else:
                candidates.extend(result.candidates)
                errors.extend(result.errors)

        unique: OrderedDict[str, CandidateRecord] = OrderedDict()
        for candidate in candidates:
            unique.setdefault(candidate.discovery_url.casefold().rstrip("/"), candidate)
        inspection_targets = list(unique.values())[: max(0, inspect_limit)]

        async def inspect(candidate: CandidateRecord) -> CandidateRecord:
            repo = self._repo_from_url(candidate.discovery_url)
            if not repo:
                return candidate
            try:
                return await self.inspect_repository(candidate, *repo)
            except Exception as exc:
                errors.append({
                    "query": candidate.discovery_url,
                    "error": f"inspection: {exc}",
                })
                return candidate

        inspected = await asyncio.gather(*(inspect(c) for c in inspection_targets))
        by_url = {c.discovery_url.casefold().rstrip("/"): c for c in inspected}
        for idx, candidate in enumerate(candidates):
            replacement = by_url.get(candidate.discovery_url.casefold().rstrip("/"))
            if replacement is not None:
                candidates[idx] = replacement

        return CollectorResult(
            self.name,
            candidates,
            errors,
            metadata={
                "search_candidate_count": len(unique),
                "inspection_limit": inspect_limit,
                "inspected_repositories": len(inspected),
                "authenticated": bool(self.token),
            },
        )


class SteamDBCollector:
    name = "steamdb"

    def __init__(
        self,
        client: AsyncHttpClient,
        searches: list[str] | None = None,
        app_ids: list[str] | None = None,
    ) -> None:
        self.client = client
        self.searches = searches or ["source code", "source_code", "open source", "GPL", "MIT"]
        self.app_ids = [str(x) for x in (app_ids or [])]

    @staticmethod
    def _package_is_interesting(name: str, snippet: str = "") -> bool:
        haystack = f"{name} {snippet}".casefold()
        return any(keyword in haystack for keyword in STEAM_PACKAGE_KEYWORDS)

    async def inspect_package(
        self,
        app_id: str,
        sub_id: str,
        package_name: str,
        *,
        app_title: str = "",
    ) -> CollectorResult:
        url = f"https://steamdb.info/sub/{sub_id}/"
        try:
            status, _, body = await self.client.request("GET", url)
            if status != 200:
                return CollectorResult(self.name, [], [{"url": url, "error": f"HTTP {status}"}])
            meta = MetaParser()
            meta.feed(body)
            plain = normalize_space(re.sub(r"<[^>]+>", " ", body))
            license_hint = first_license(plain)
            title = app_title or meta.title or f"Steam app {app_id}"
            complete_claim = any(
                phrase in plain.casefold()
                for phrase in ("complete source", "full source", "source code", "game source")
            )
            candidate = candidate_from_text(
                title=title,
                source=self.name,
                url=url,
                query=f"SteamDB package enumeration app:{app_id}",
                snippet=f"Steam app {app_id}; package {sub_id} {package_name}; {plain[:3500]}",
                license_hint=license_hint,
                source_scope="source-package",
                completeness="complete-source-claim" if complete_claim else "unknown",
            )
            candidate.evidence.append(
                EvidenceRecord(
                    candidate_id=candidate.candidate_id,
                    evidence_source="steamdb-package",
                    evidence_url=url,
                    evidence_title=package_name or f"Steam Sub {sub_id}",
                    accessed_at=utc_now(),
                    evidence_type="package",
                    source_scope_claim="steam-source-package",
                    authorization_signal="steam-store-package",
                    source_completeness_claim="complete-source-claim" if complete_claim else "",
                    confidence="medium",
                    notes=plain[:5000],
                )
            )
            return CollectorResult(self.name, [candidate], [])
        except (asyncio.TimeoutError, UnicodeError) as exc:
            return CollectorResult(self.name, [], [{"url": url, "error": str(exc)}])

    async def enumerate_app_packages(
        self,
        app_id: str,
        *,
        app_title: str = "",
    ) -> CollectorResult:
        """Enumerate every source-like Steam package attached to an app."""
        url = f"https://steamdb.info/app/{app_id}/subs/"
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        try:
            status, _, body = await self.client.request("GET", url)
            if status != 200:
                return CollectorResult(self.name, [], [{"url": url, "error": f"HTTP {status}"}])
            meta = MetaParser()
            meta.feed(body)
            resolved_title = app_title or meta.title or f"Steam app {app_id}"
            resolved_title = re.sub(
                r"\s*[·|-]\s*SteamDB.*$",
                "",
                resolved_title,
                flags=re.IGNORECASE,
            ).strip()
            resolved_title = re.sub(
                r"\s+Packages?$",
                "",
                resolved_title,
                flags=re.IGNORECASE,
            ).strip() or f"Steam app {app_id}"

            parser = LinkTextParser()
            parser.feed(body)
            packages: dict[str, str] = {}
            for href, link_text in parser.links:
                absolute = urljoin(url, href)
                match = STEAM_SUB_RE.search(absolute)
                if not match:
                    continue
                name = normalize_space(link_text)
                if name:
                    packages[match.group(1)] = name
            for sub_id in set(STEAM_SUB_RE.findall(body)):
                packages.setdefault(sub_id, f"Steam Sub {sub_id}")

            source_packages = {
                sub_id: name
                for sub_id, name in packages.items()
                if self._package_is_interesting(name)
            }
            results = await asyncio.gather(
                *(
                    self.inspect_package(app_id, sub_id, name, app_title=resolved_title)
                    for sub_id, name in source_packages.items()
                ),
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, Exception):
                    errors.append({"url": url, "error": f"package: {result}"})
                else:
                    candidates.extend(result.candidates)
                    errors.extend(result.errors)
            return CollectorResult(
                self.name,
                candidates,
                errors,
                metadata={
                    "app_id": app_id,
                    "packages_seen": len(packages),
                    "source_packages": len(source_packages),
                },
            )
        except Exception as exc:
            errors.append({"url": url, "error": str(exc)})
        return CollectorResult(self.name, candidates, errors)

    async def fetch_search(self, url: str) -> CollectorResult:
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        try:
            status, _, body = await self.client.request("GET", url)
            if status != 200:
                return CollectorResult(self.name, [], [{"url": url, "error": f"HTTP {status}"}])
            parser = LinkTextParser()
            parser.feed(body)
            for href, link_text in parser.links:
                absolute = urljoin(url, href)
                match = STEAM_APP_RE.search(absolute)
                if not match:
                    continue
                app_id = match.group(1)
                title = normalize_space(link_text) or f"Steam app {app_id}"
                candidate = candidate_from_text(
                    title=title,
                    source=self.name,
                    url=f"https://steamdb.info/app/{app_id}/",
                    query=url,
                    snippet=f"{link_text} steam_app_id={app_id}",
                    source_scope="steam-app-search",
                )
                candidates.append(candidate)
        except (asyncio.TimeoutError, UnicodeError) as exc:
            errors.append({"url": url, "error": str(exc)})
        return CollectorResult(self.name, candidates, errors)

    async def collect(
        self,
        *,
        searches: list[str] | None = None,
        app_ids: list[str] | None = None,
        max_apps: int = 250,
    ) -> CollectorResult:
        search_terms = searches or self.searches
        search_urls = [
            f"https://steamdb.info/search/?a=app&q={quote_plus(term)}"
            for term in search_terms
        ]
        results = await asyncio.gather(
            *(self.fetch_search(url) for url in search_urls),
            return_exceptions=True,
        )
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        for result in results:
            if isinstance(result, Exception):
                errors.append({"query": "steamdb", "error": str(result)})
            else:
                candidates.extend(result.candidates)
                errors.extend(result.errors)

        app_map: OrderedDict[str, str] = OrderedDict()
        for candidate in candidates:
            match = re.search(r"steam_app_id=(\d+)", candidate.notes)
            if match:
                app_map.setdefault(match.group(1), candidate.candidate_title)
        for app_id in app_ids or self.app_ids:
            app_map.setdefault(str(app_id), f"Steam app {app_id}")

        app_targets = list(app_map.items())[: max(0, max_apps)]
        package_results = await asyncio.gather(
            *(
                self.enumerate_app_packages(app_id, app_title=title)
                for app_id, title in app_targets
            ),
            return_exceptions=True,
        )
        package_candidates: list[CandidateRecord] = []
        for result in package_results:
            if isinstance(result, Exception):
                errors.append({"query": "steamdb", "error": f"enumeration: {result}"})
            else:
                package_candidates.extend(result.candidates)
                errors.extend(result.errors)

        return CollectorResult(
            self.name,
            candidates + package_candidates,
            errors,
            metadata={
                "search_terms": len(search_terms),
                "apps_discovered": len(app_map),
                "apps_enumerated": len(app_targets),
                "package_candidates": len(package_candidates),
            },
        )


class WaybackCollector:
    name = "wayback"

    def __init__(self, client: AsyncHttpClient) -> None:
        self.client = client

    async def domain(self, target: str, *, limit: int = 200) -> CollectorResult:
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        pattern = target if target.endswith("/*") else target.rstrip("/") + "/*"
        params = [
            ("url", pattern),
            ("output", "json"),
            ("filter", "statuscode:200"),
            ("filter", "mimetype:text/html"),
            ("collapse", "urlkey"),
            ("limit", str(limit)),
        ]
        try:
            status, _, body = await self.client.request(
                "GET",
                "https://web.archive.org/cdx/search/cdx",
                params=params,
            )
            if status != 200:
                return CollectorResult(self.name, [], [{"url": target, "error": f"HTTP {status}"}])
            rows = json.loads(body)
            if not rows:
                return CollectorResult(self.name, [], [])
            header = rows[0]
            for row in rows[1:]:
                if not row:
                    continue
                data = dict(zip(header, row))
                original = data.get("original") or ""
                timestamp = data.get("timestamp") or ""
                if not original:
                    continue
                # Fetch only pages whose URL itself strongly suggests source-release content.
                if not any(k.replace(" ", "") in original.casefold() for k in (
                    "source", "code", "download", "release", "opensource",
                )):
                    continue
                snapshot = f"https://web.archive.org/web/{timestamp}/{original}"
                candidates.append(
                    candidate_from_text(
                        title=original.rsplit("/", 1)[-1] or original,
                        source=self.name,
                        url=snapshot,
                        query=target,
                        snippet=f"Wayback capture {timestamp} of {original}",
                        source_scope="historical-page",
                    )
                )
        except (json.JSONDecodeError, asyncio.TimeoutError) as exc:
            errors.append({"url": target, "error": str(exc)})
        return CollectorResult(self.name, candidates, errors)


class DeveloperSiteCollector:
    name = "developer-site"

    def __init__(self, client: AsyncHttpClient) -> None:
        self.client = client

    async def crawl(
        self,
        seeds: list[str],
        *,
        max_pages: int = 50,
        max_depth: int = 2,
    ) -> CollectorResult:
        queue: deque[tuple[str, int]] = deque((url, 0) for url in seeds)
        seen: set[str] = set()
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        allowed_hosts = {urlparse(url).netloc.casefold() for url in seeds}

        while queue and len(seen) < max_pages:
            url, depth = queue.popleft()
            normalized = url.split("#", 1)[0]
            if normalized in seen or urlparse(normalized).netloc.casefold() not in allowed_hosts:
                continue
            seen.add(normalized)
            try:
                status, headers, body = await self.client.request("GET", normalized)
                if status != 200:
                    continue
                content_type = headers.get("content-type", "")
                if "text/html" not in content_type and not normalized.endswith((".html", ".htm", "/")):
                    continue

                meta = MetaParser()
                meta.feed(body)
                text_blob = normalize_space(re.sub(r"<[^>]+>", " ", body))
                keyword_hits = [k for k in SOURCE_KEYWORDS if k in text_blob.casefold()]
                if keyword_hits:
                    candidate = candidate_from_text(
                        title=meta.title or normalized,
                        source=self.name,
                        url=normalized,
                        query="developer-site crawl",
                        snippet=text_blob[:4000],
                        license_hint=first_license(text_blob),
                        source_scope="developer-page",
                        authorization="likely-authorized",
                    )
                    candidates.append(candidate)

                if depth < max_depth:
                    parser = LinkTextParser()
                    parser.feed(body)
                    for href, _ in parser.links:
                        child = urljoin(normalized, href).split("#", 1)[0]
                        parsed = urlparse(child)
                        if (
                            parsed.scheme in {"http", "https"}
                            and parsed.netloc.casefold() in allowed_hosts
                            and child not in seen
                        ):
                            queue.append((child, depth + 1))
            except (asyncio.TimeoutError, UnicodeError) as exc:
                errors.append({"url": normalized, "error": str(exc)})
        return CollectorResult(self.name, candidates, errors)


class IGDBCollector:
    name = "igdb"

    def __init__(self, client: AsyncHttpClient, client_id: str, client_secret: str) -> None:
        self.client = client
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = ""

    async def authenticate(self) -> str:
        status, _, body = await self.client.request(
            "POST",
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
        )
        if status != 200:
            raise RuntimeError(f"IGDB OAuth HTTP {status}")
        payload = json.loads(body)
        self._token = payload["access_token"]
        return self._token

    async def resolve_titles(self, titles: list[str]) -> CollectorResult:
        if not titles:
            return CollectorResult(self.name, [], [])
        if not self._token:
            await self.authenticate()
        # IGDB is used for identity/release metadata enrichment, not license proof.
        body = "fields id,name,first_release_date,involved_companies.company.name,platforms.name; limit 500; where category = 0;"
        # Exact-title lookups are more precise than broad search and reduce API load.
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "text/plain",
        }
        for title in titles:
            query_body = f'search "{title.replace(chr(34), "")}"; {body}'
            try:
                status, _, response = await self.client.request(
                    "POST",
                    "https://api.igdb.com/v4/games",
                    headers=headers,
                    data=query_body,
                )
                if status != 200:
                    errors.append({"title": title, "error": f"HTTP {status}"})
                    continue
                games = json.loads(response)
                for game in games[:5]:
                    companies = [
                        item.get("company", {}).get("name", "")
                        for item in game.get("involved_companies", [])
                        if item.get("company")
                    ]
                    release = game.get("first_release_date")
                    release_date = ""
                    if release:
                        release_date = datetime.fromtimestamp(int(release), UTC).date().isoformat()
                    snippet = (
                        f"IGDB ID {game.get('id')}; release {release_date}; "
                        f"companies: {', '.join(filter(None, companies))}; "
                        f"platforms: {', '.join(p.get('name', '') for p in game.get('platforms', []))}"
                    )
                    candidates.append(
                        candidate_from_text(
                            title=game.get("name") or title,
                            developer=", ".join(filter(None, companies)),
                            source=self.name,
                            url=f"https://www.igdb.com/games/{quote_plus(game.get('name') or title).replace('+', '-')}",
                            query=f"IGDB title resolve: {title}",
                            snippet=snippet,
                            release_date=release_date,
                            source_scope="commercial-metadata",
                        )
                    )
            except (json.JSONDecodeError, asyncio.TimeoutError) as exc:
                errors.append({"title": title, "error": str(exc)})
        return CollectorResult(self.name, candidates, errors)

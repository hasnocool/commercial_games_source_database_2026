"""Filename: cgsdb_discovery/collectors.py"""

from __future__ import annotations

import asyncio
import base64
from difflib import SequenceMatcher
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
    "source code leak",
    "leaked source",
    "leaked game",
    "game leak",
    "stolen source",
    "unauthorized source",
    "unreleased source",
    "pirated source",
    "pirated source code",
    "pirated game",
    "stolen source code",
    "stolen game source",
    "internal source leak",
    "internal game leak",
    "private source leak",
    "source dump",
    "code dump",
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

ITCH_ENGINE_NAMES = (
    "Unity", "Unreal Engine", "Godot", "GameMaker", "GameMaker Studio",
    "Construct", "Defold", "Ren'Py", "RPG Maker", "Twine", "Bevy",
    "MonoGame", "XNA", "LÖVE", "Love2D", "PICO-8", "GDevelop",
    "Clickteam Fusion", "Adventure Game Studio", "AGS", "Solar2D",
    "Cocos2d", "Cocos Creator", "HaxeFlixel", "libGDX", "Phaser",
    "Three.js", "Babylon.js", "OpenFL", "Kha", "Godot Engine",
)

ITCH_SOURCE_FILE_HINTS = (
    ".zip", ".7z", ".tar", ".tar.gz", ".tgz", ".rar",
    ".unitypackage", ".uproject", ".uasset", ".godot",
    ".blend", ".love", ".gproj", ".yyp", ".yyz", ".rpgproject",
    ".gdevelop", ".p8", ".tres", ".tscn",
)

ITCH_SOURCE_NAME_HINTS = (
    "source", "src", "sourcecode", "source-code", "project",
    "game-project", "full-project", "complete-project", "development",
)

def title_match_confidence(expected: str, observed: str) -> float:
    expected = normalize_space(expected).casefold()
    observed = normalize_space(observed).casefold()
    if not expected or not observed:
        return 0.0
    if expected == observed:
        return 1.0
    ratio = SequenceMatcher(None, expected, observed).ratio()
    expected_tokens = set(re.findall(r"[a-z0-9]+", expected))
    observed_tokens = set(re.findall(r"[a-z0-9]+", observed))
    if expected_tokens and observed_tokens:
        overlap = len(expected_tokens & observed_tokens) / max(len(expected_tokens), len(observed_tokens))
        ratio = max(ratio, overlap)
    return round(min(1.0, ratio), 3)

def detect_itch_engines(text: str) -> list[str]:
    haystack = normalize_space(text).casefold()
    found = []
    for name in ITCH_ENGINE_NAMES:
        if name.casefold() in haystack:
            found.append(name)
    return sorted(set(found))

def classify_itch_price(text: str) -> tuple[str, str]:
    haystack = normalize_space(text).casefold()
    if any(x in haystack for x in (
        "no thanks, just take me to the downloads",
        "download for free",
        "free download",
        "free to download",
        "no payments",
    )):
        return "free", "0"
    if "pay what you want" in haystack or "pay any amount" in haystack:
        return "pay-what-you-want", "0"
    price = re.search(r"(?:minimum price|price|pay)\\s*[:\\-]?\\s*(\\$\\s?\\d+(?:[.,]\\d{2})?)", haystack)
    if price:
        return "paid", normalize_space(price.group(1))
    if re.search(r"\\$\\d+(?:[.,]\\d{2})?", haystack):
        return "paid", normalize_space(re.search(r"\\$\\d+(?:[.,]\\d{2})?", haystack).group(0))
    return "unknown", ""

def inspect_itch_downloads(url: str, body: str) -> tuple[str, str, list[str]]:
    parser = LinkTextParser()
    parser.feed(body)
    files = []
    for href, link_text in parser.links:
        absolute = urljoin(url, href)
        haystack = f"{link_text} {absolute}".casefold()
        if any(ext in haystack for ext in ITCH_SOURCE_FILE_HINTS) or any(
            hint in haystack for hint in ITCH_SOURCE_NAME_HINTS
        ):
            label = normalize_space(link_text) or absolute.rsplit("/", 1)[-1]
            if label and label not in files:
                files.append(label[:300])
    page = normalize_space(re.sub(r"<[^>]+>", " ", body)).casefold()
    has_source_claim = any(
        phrase in page for phrase in (
            "source code included", "full source code", "complete source code",
            "full project", "complete project", "project files included",
            "source files included",
        )
    )
    if files and has_source_claim:
        return "yes", "high", files[:50]
    if files:
        return "likely", "medium", files[:50]
    return "unknown", "low", []

def extract_itch_creator(url: str, body: str) -> tuple[str, str]:
    parsed = urlparse(url)
    username = parsed.netloc.split(".", 1)[0] if parsed.netloc else ""
    display = ""
    parser = LinkTextParser()
    parser.feed(body)
    for href, link_text in parser.links:
        p = urlparse(urljoin(url, href))
        host = p.netloc.casefold().split(":", 1)[0]
        if host == f"{username}.itch.io" and p.path in {"", "/"}:
            text_value = normalize_space(link_text)
            if text_value:
                display = text_value
                break
    return username, display


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
        "game build leak",
        "beta leak",
        "prototype leak",
        "internal build",
        "unreleased build",
        "pirated source",
        "pirated source code",
        "pirated game",
        "stolen source code",
        "stolen game source",
        "internal source leak",
        "internal game leak",
        "private source leak",
        "source dump",
        "code dump",
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
        if any(x in content_blob for x in ("full game", "complete game", "retail game", "game dump")):
            inferred_types.append("full-game")
        if any(x in content_blob for x in ("beta", "prototype", "alpha", "internal build")):
            inferred_types.append("prototype-or-beta")
        if any(x in content_blob for x in ("sdk", "development kit")):
            inferred_types.append("sdk")
        if any(x in content_blob for x in ("server", "dedicated server", "backend")):
            inferred_types.append("server")
        if any(x in content_blob for x in ("documentation", "docs", "manual")):
            inferred_types.append("documentation")
        if any(x in content_blob for x in ("assets", "artwork", "sound", "music")):
            inferred_types.append("assets")
        content_types = inferred_types or []
    if access_status == "unknown" and source in {"github", "steamdb", "internet-archive", "itchio", "developer-site", "wayback"}:
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
        provenance_confidence="medium" if source in {"developer-site", "github", "itchio"} else "low",
        evidence_confidence="medium" if source in {"developer-site", "github", "itchio"} else "low",
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
            confidence="medium" if source in {"developer-site", "github", "itchio"} else "low",
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



class ItchioCollector:
    """Discover source-code availability on public itch.io listing/game pages.

    The authenticated itch.io server-side API is intentionally not required.
    This collector reads public HTML only and never downloads game builds,
    source archives, or other binaries.
    """

    name = "itchio"

    DEFAULT_TAGS = (
        "sourcecode",
        "source-code",
        "game-source-code",
        "open-source",
        "opensource",
    )

    SOURCE_CLAIM_PHRASES = (
        "source code available",
        "source code included",
        "source code is included",
        "source included",
        "source files included",
        "includes source",
        "includes the source",
        "full source code",
        "complete source code",
        "entire source code",
        "full source",
        "complete source",
        "full project",
        "complete project",
        "project files included",
        "source repository",
        "source repo",
        "open source",
        "open-source",
        "published source",
        "source released",
        "released source",
        "game source",
    )

    COMPLETE_SOURCE_PHRASES = (
        "full source code",
        "complete source code",
        "entire source code",
        "full source",
        "complete source",
        "full project",
        "complete project",
        "project files included",
        "complete game project",
        "entire game project",
    )

    SOURCE_LINK_HOSTS = {
        "github.com",
        "gitlab.com",
        "codeberg.org",
        "sourcehut.org",
        "sr.ht",
    }

    def __init__(
        self,
        client: AsyncHttpClient,
        tags: list[str] | None = None,
        urls: list[str] | None = None,
        game_urls: list[str] | None = None,
        title_filters: list[str] | None = None,
    ) -> None:
        self.client = client
        self.tags = [
            str(tag).strip()
            for tag in (tags or self.DEFAULT_TAGS)
            if str(tag).strip()
        ]
        self.urls = [str(url).strip() for url in (urls or []) if str(url).strip()]
        self.game_urls = [
            str(url).strip() for url in (game_urls or []) if str(url).strip()
        ]
        self.title_filters = [
            normalize_space(title).casefold()
            for title in (title_filters or [])
            if normalize_space(title)
        ]

    @staticmethod
    def tag_page_url(tag: str, page: int = 1) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", tag.casefold()).strip("-")
        base = f"https://itch.io/games/tag-{slug}"
        return base if page <= 1 else f"{base}?page={page}"

    @classmethod
    def is_game_url(cls, url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.netloc.casefold().split(":", 1)[0]
        if parsed.scheme not in {"http", "https"} or not host.endswith(".itch.io"):
            return False
        parts = [part for part in parsed.path.split("/") if part]
        return len(parts) == 1 and parts[0].casefold() not in {
            "about",
            "community",
            "devlogs",
            "games",
            "jams",
            "login",
            "notifications",
            "press",
            "search",
            "settings",
            "stats",
        }

    @classmethod
    def _source_links(cls, url: str, body: str) -> list[tuple[str, str]]:
        parser = LinkTextParser()
        parser.feed(body)
        found: OrderedDict[str, str] = OrderedDict()
        for href, link_text in parser.links:
            absolute = urljoin(url, href)
            parsed = urlparse(absolute)
            host = parsed.netloc.casefold().split(":", 1)[0]
            if host in cls.SOURCE_LINK_HOSTS or any(
                token in link_text.casefold()
                for token in ("source", "repository", "repo", "github", "gitlab")
            ):
                found[absolute.rstrip("/")] = normalize_space(link_text)
        return list(found.items())

    def _title_matches(self, title: str) -> bool:
        if not self.title_filters:
            return True
        haystack = normalize_space(title).casefold()
        return any(
            wanted == haystack
            or wanted in haystack
            or haystack in wanted
            for wanted in self.title_filters
        )

    async def fetch_listing(
        self,
        url: str,
    ) -> tuple[list[tuple[str, str]], list[dict[str, str]]]:
        errors: list[dict[str, str]] = []
        try:
            status, _, body = await self.client.request("GET", url)
            if status != 200:
                return [], [{"url": url, "error": f"HTTP {status}"}]

            parser = LinkTextParser()
            parser.feed(body)
            links: OrderedDict[str, str] = OrderedDict()
            for href, link_text in parser.links:
                absolute = urljoin(url, href).split("#", 1)[0]
                if not self.is_game_url(absolute):
                    continue
                title = normalize_space(link_text)
                if not title or not self._title_matches(title):
                    continue
                links.setdefault(absolute, title)
            return list(links.items()), errors
        except (asyncio.TimeoutError, UnicodeError) as exc:
            return [], [{"url": url, "error": str(exc)}]

    async def inspect_game(
        self,
        url: str,
        *,
        listing_title: str = "",
        listing_url: str = "",
    ) -> CandidateRecord | None:
        status, _, body = await self.client.request("GET", url)
        if status != 200:
            return None

        meta = MetaParser()
        meta.feed(body)
        plain = normalize_space(re.sub(r"<[^>]+>", " ", body))
        haystack = plain.casefold()

        source_hits = [
            phrase for phrase in self.SOURCE_CLAIM_PHRASES if phrase in haystack
        ]
        source_links = self._source_links(url, body)

        if not source_hits and not source_links:
            return None

        origin, leak_status, leak_tags = classify_provenance_text(f"{plain} {url}")
        exact_license = first_license(plain)
        complete = any(phrase in haystack for phrase in self.COMPLETE_SOURCE_PHRASES)

        parsed = urlparse(url)
        creator_username, creator_display = extract_itch_creator(url, body)
        creator = creator_display or creator_username or (parsed.netloc.split(".", 1)[0] if parsed.netloc else "")
        title = normalize_space(meta.title or listing_title) or url

        expected_title = listing_title
        if self.title_filters:
            expected_title = min(
                self.title_filters,
                key=lambda candidate: abs(len(candidate) - len(title.casefold())),
            )
        title_confidence = title_match_confidence(expected_title, title) if expected_title else None

        engines = detect_itch_engines(plain)
        price_status, min_price = classify_itch_price(plain)
        download_status, download_confidence, downloadable_files = inspect_itch_downloads(url, body)
        source_repo = source_links[0][0] if source_links else ""

        if complete and "full game" in haystack:
            content_types = ["source-code", "full-game"]
        else:
            content_types = ["source-code"]

        tags = set(leak_tags) | {"itchio", "source-code-listing"}
        if complete:
            tags.add("complete-source-claim")
        if source_links:
            tags.add("external-source-repository")
        if price_status == "paid":
            tags.add("paid-source-code")
        if price_status == "free":
            tags.add("free-source-code")
        if engines:
            tags.update(f"engine:{engine.casefold().replace(' ', '-')}" for engine in engines)
        if download_status in {"yes", "likely"}:
            tags.add("downloadable-project-evidence")

        candidate = candidate_from_text(
            title=title,
            developer=creator,
            source=self.name,
            url=url,
            query=listing_url or "itch.io source-code scan",
            snippet=plain[:5000],
            license_hint=exact_license,
            source_scope="itchio-game-page",
            authorization=(
                "unauthorized-or-unresolved" if origin == "leak" else "seller-published"
            ),
            completeness="complete-source-claim" if complete else "source-code-claim",
            provenance_class=origin,
            leak_status=leak_status,
            content_types=content_types,
            access_status="public",
            redistribution_status=(
                "forbidden" if origin == "leak" else (
                    "allowed" if license_family(exact_license)
                    in {"open-source", "public-domain"} else "unknown"
                )
            ),
            classification_tags=sorted(tags),
        )
        candidate.review_status = "needs-verification"
        candidate.title_match_confidence = title_confidence
        candidate.itch_creator_username = creator_username
        candidate.itch_creator_display_name = creator_display
        candidate.itch_price_status = price_status
        candidate.itch_min_price = min_price
        candidate.itch_engine_tags = engines
        candidate.itch_source_repository_url = source_repo
        candidate.itch_downloadable_project_status = download_status
        candidate.itch_downloadable_project_confidence = download_confidence
        candidate.itch_downloadable_files = downloadable_files

        enrichment = (
            f"itch.io creator={creator_username or 'unknown'}; "
            f"title_match_confidence={title_confidence if title_confidence is not None else 'n/a'}; "
            f"price_status={price_status}; min_price={min_price or 'n/a'}; "
            f"engines={','.join(engines) or 'none-detected'}; "
            f"source_repository={source_repo or 'none'}; "
            f"downloadable_project={download_status}/{download_confidence}; "
            f"downloadable_files={','.join(downloadable_files[:10]) or 'none-visible'}"
        )
        candidate.notes = f"{candidate.notes} {enrichment}".strip()

        if listing_url:
            candidate.evidence.append(
                EvidenceRecord(
                    candidate_id=candidate.candidate_id,
                    evidence_source="itchio-listing",
                    evidence_url=listing_url,
                    evidence_title=listing_title or title,
                    accessed_at=utc_now(),
                    evidence_type="listing",
                    publisher_or_owner=creator,
                    source_scope_claim="itchio-public-listing",
                    authorization_signal="platform-listing",
                    source_completeness_claim="",
                    provenance_class_claim=origin,
                    leak_status_claim=leak_status,
                    content_type_claim="source-code",
                    access_status_claim="public",
                    redistribution_status_claim=candidate.redistribution_status,
                    classification_tags=["itchio", "source-code-listing"],
                    confidence="medium",
                    notes=f"Discovered from itch.io listing: {listing_url}",
                )
            )

        candidate.evidence.append(
            EvidenceRecord(
                candidate_id=candidate.candidate_id,
                evidence_source="itchio-page-enrichment",
                evidence_url=url,
                evidence_title=title,
                accessed_at=utc_now(),
                evidence_type="metadata-enrichment",
                publisher_or_owner=creator,
                source_scope_claim="itchio-public-game-page",
                authorization_signal="seller-published",
                source_completeness_claim=(
                    f"complete-source-claim;downloadable-project={download_status}"
                ),
                provenance_class_claim=origin,
                leak_status_claim=leak_status,
                content_type_claim=";".join(content_types),
                access_status_claim="public",
                redistribution_status_claim=candidate.redistribution_status,
                classification_tags=sorted({
                    "itchio",
                    "title-match-enrichment",
                    "creator-enrichment",
                    "price-enrichment",
                    "engine-enrichment",
                    "downloadable-project-enrichment",
                }),
                confidence=(
                    "high" if download_confidence == "high" and title_confidence and title_confidence >= 0.9
                    else "medium"
                ),
                notes=enrichment,
            )
        )

        for source_url, link_text in source_links:
            candidate.evidence.append(
                EvidenceRecord(
                    candidate_id=candidate.candidate_id,
                    evidence_source="itchio-source-link",
                    evidence_url=source_url,
                    evidence_title=link_text or source_url,
                    accessed_at=utc_now(),
                    evidence_type="source-link",
                    publisher_or_owner=creator,
                    source_scope_claim="external-source-repository-link",
                    authorization_signal="seller-published-link",
                    source_completeness_claim="complete-source-claim" if complete else "",
                    provenance_class_claim=origin,
                    leak_status_claim=leak_status,
                    content_type_claim="source-code",
                    access_status_claim="public",
                    redistribution_status_claim=candidate.redistribution_status,
                    classification_tags=["itchio", "external-source-repository"],
                    confidence="medium",
                    notes=link_text,
                )
            )

        return candidate

    async def collect(
        self,
        *,
        pages: int = 3,
        inspect_limit: int = 300,
    ) -> CollectorResult:
        listing_urls: OrderedDict[str, str] = OrderedDict()

        for url in self.urls:
            listing_urls.setdefault(url.rstrip("/"), url.rstrip("/"))

        for tag in self.tags:
            for page in range(1, max(1, pages) + 1):
                url = self.tag_page_url(tag, page)
                listing_urls.setdefault(url, url)

        # Title filters also become direct public itch.io searches. This lets
        # the caller cross-check known commercial titles even when they are not
        # tagged as source-code listings.
        for title in self.title_filters:
            query_url = (
                "https://itch.io/search?classification=game&type=games&q="
                + quote_plus(title)
            )
            listing_urls.setdefault(query_url, query_url)

        all_games: OrderedDict[str, tuple[str, str]] = OrderedDict()
        errors: list[dict[str, str]] = []

        listing_results = await asyncio.gather(
            *(self.fetch_listing(url) for url in listing_urls.values()),
            return_exceptions=True,
        )

        for listing_url, result in zip(listing_urls.values(), listing_results):
            if isinstance(result, Exception):
                errors.append({"url": listing_url, "error": str(result)})
                continue

            game_links, listing_errors = result
            errors.extend(listing_errors)

            for game_url, title in game_links:
                all_games.setdefault(game_url, (title, listing_url))

        for game_url in self.game_urls:
            if self.is_game_url(game_url):
                all_games.setdefault(game_url, ("", "direct-game-url"))

        targets = list(all_games.items())[:max(0, inspect_limit)]

        async def inspect_one(
            item: tuple[str, tuple[str, str]],
        ) -> CandidateRecord | None:
            game_url, (title, listing_url) = item
            try:
                return await self.inspect_game(
                    game_url,
                    listing_title=title,
                    listing_url=listing_url,
                )
            except (asyncio.TimeoutError, UnicodeError) as exc:
                errors.append({"url": game_url, "error": str(exc)})
                return None

        inspected = await asyncio.gather(
            *(inspect_one(item) for item in targets),
            return_exceptions=True,
        )

        candidates: list[CandidateRecord] = []
        for item in inspected:
            if isinstance(item, Exception):
                errors.append({"url": "itch.io", "error": str(item)})
            elif item is not None:
                candidates.append(item)

        return CollectorResult(
            self.name,
            candidates,
            errors,
            metadata={
                "listing_pages": len(listing_urls),
                "listing_game_urls": len(all_games),
                "inspect_limit": inspect_limit,
                "inspected_games": len(targets),
                "source_candidate_count": len(candidates),
                "tags": self.tags,
                "direct_urls": self.urls,
                "direct_game_urls": self.game_urls,
                "title_filters": self.title_filters,
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

"""Filename: cgsdb_discovery/collectors.py"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
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
STEAM_APP_RE = re.compile(r"https?://steamdb\.info/app/(\d+)", re.IGNORECASE)
STEAM_SUB_RE = re.compile(r"https?://steamdb\.info/sub/(\d+)", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def normalize_space(text: str) -> str:
    return " ".join((text or "").split()).strip()


def first_license(text: str) -> str:
    match = LICENSE_RE.search(text or "")
    return normalize_space(match.group(1)) if match else ""


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
) -> CandidateRecord:
    candidate = CandidateRecord(
        candidate_title=normalize_space(title),
        developer=normalize_space(developer),
        discovery_sources=[source],
        first_discovered_at=utc_now(),
        discovery_query=query,
        discovery_url=url,
        review_status="new",
        exact_license=license_hint or first_license(snippet),
        source_completeness=completeness,
        authorization_status=authorization,
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


class InternetArchiveCollector:
    name = "internet-archive"

    def __init__(self, client: AsyncHttpClient) -> None:
        self.client = client

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
                        license_hint=license_url,
                        release_date=normalize_space(doc.get("date") or doc.get("year") or ""),
                        source_scope="archive-item",
                        completeness="unknown",
                    )
                    candidates.append(candidate)
            except (json.JSONDecodeError, asyncio.TimeoutError) as exc:
                errors.append({"query": query, "error": str(exc)})
                break
        return CollectorResult(self.name, candidates, errors)

    async def collect(self, queries: list[str], *, pages: int = 5, rows: int = 100) -> CollectorResult:
        results = await asyncio.gather(
            *(self.search_query(query, pages=pages, rows=rows) for query in queries),
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
        return CollectorResult(self.name, candidates, errors)


class GitHubCollector:
    name = "github"

    def __init__(self, client: AsyncHttpClient, token: str = "") -> None:
        self.client = client
        self.token = token

    async def search(self, query: str, *, pages: int = 3, per_page: int = 100) -> CollectorResult:
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for page in range(1, pages + 1):
            try:
                status, _, body = await self.client.request(
                    "GET",
                    "https://api.github.com/search/repositories",
                    headers=headers,
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
                    haystack = " ".join([name, description, " ".join(item.get("topics") or [])]).lower()
                    if not any(keyword in haystack for keyword in ("source", "game", "gpl", "mit", "open")):
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
                        authorization="unknown",
                    )
                    candidates.append(candidate)
            except (json.JSONDecodeError, asyncio.TimeoutError) as exc:
                errors.append({"query": query, "error": str(exc)})
                break
        return CollectorResult(self.name, candidates, errors)

    async def collect(self, queries: list[str], *, pages: int = 3) -> CollectorResult:
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
        return CollectorResult(self.name, candidates, errors)


class SteamDBCollector:
    name = "steamdb"

    SEARCH_URLS = (
        "https://steamdb.info/search/?a=app&q=source+code",
        "https://steamdb.info/search/?a=app&q=source_code",
        "https://steamdb.info/search/?a=app&q=open+source",
        "https://steamdb.info/search/?a=app&q=GPL",
        "https://steamdb.info/search/?a=app&q=MIT",
    )

    def __init__(
        self,
        client: AsyncHttpClient,
        searches: list[str] | None = None,
    ) -> None:
        self.client = client
        self.searches = searches or [
            "source code",
            "source_code",
            "open source",
            "GPL",
            "MIT",
        ]
    async def fetch_search(self, url: str) -> CollectorResult:
        candidates: list[CandidateRecord] = []
        errors: list[dict[str, str]] = []
        try:
            status, _, body = await self.client.request("GET", url)
            if status != 200:
                return CollectorResult(self.name, [], [{"url": url, "error": f"HTTP {status}"}])
            parser = LinkTextParser()
            parser.feed(body)
            for href, text in parser.links:
                absolute = urljoin(url, href)
                match = STEAM_APP_RE.search(absolute)
                if not match:
                    continue
                app_id = match.group(1)
                title = normalize_space(text) or f"Steam app {app_id}"
                if not any(k in f"{title} {text}".lower() for k in ("source", "code", "gpl", "mit", "open")):
                    continue
                app_url = f"https://steamdb.info/app/{app_id}/"
                candidate = candidate_from_text(
                    title=title,
                    source=self.name,
                    url=app_url,
                    query=url,
                    snippet=text,
                    source_scope="steam-app-or-package",
                )
                candidates.append(candidate)

            # Search results can be sparse; discover package/source-code URLs embedded in page text.
            for match in STEAM_SUB_RE.findall(body):
                sub_url = f"https://steamdb.info/sub/{match}/"
                if any(c.discovery_url == sub_url for c in candidates):
                    continue
                snippet_match = re.search(
                    rf".{{0,220}}{re.escape(match)}.{{0,500}}",
                    body,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                snippet = normalize_space(re.sub(r"<[^>]+>", " ", snippet_match.group(0))) if snippet_match else ""
                if "source" not in snippet.lower():
                    continue
                candidate = candidate_from_text(
                    title=f"Steam package {match} source code",
                    source=self.name,
                    url=sub_url,
                    query=url,
                    snippet=snippet,
                    source_scope="source-package",
                )
                candidates.append(candidate)
        except (asyncio.TimeoutError, UnicodeError) as exc:
            errors.append({"url": url, "error": str(exc)})
        return CollectorResult(self.name, candidates, errors)

    async def collect(self) -> CollectorResult:
        search_urls = [
            f"https://steamdb.info/search/?a=app&q={quote_plus(term)}"
            for term in self.searches
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
        return CollectorResult(self.name, candidates, errors)


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

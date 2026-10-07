# Discovery collectors

The collector framework is designed for **high recall first, verification second**.

## Collectors

### Internet Archive

Uses the public Advanced Search API and searches several complementary queries. Internet Archive also exposes a cursor-based scraping API for deeper searches; the first implementation uses paged Advanced Search because it is easier to bound and resume deterministically. Internet Archive documents a 10,000-result limit for sorted Advanced Search pagination and a separate scraping API for deeper paging.

### GitHub

Uses the GitHub REST repository search API. Authentication is optional for public data, but a `GITHUB_TOKEN` is strongly recommended for repeated sweeps. GitHub's current documentation lists 60 requests/hour unauthenticated and 5,000 requests/hour authenticated for the primary REST limit, with stricter search/secondary limits. The collector therefore bounds concurrency and honors retry/backoff signals.

### SteamDB

Uses public SteamDB search/package HTML as a discovery surface. This is especially useful for source-code packages that are represented as apps/DLC/packages rather than ordinary game repositories. SteamDB can expose dedicated source-code packages and package metadata, but the collector treats its results as discovery evidence until the source/license is independently verified.

### Wayback

Queries the Wayback CDX endpoint for domains or URL prefixes. The CDX API can return JSON capture indexes and supports collapsing/paging. This collector is intended to recover dead source-release pages, developer announcements, old repository links, and source-download pages.

### Developer site

Crawls explicitly supplied public developer/rightsholder domains. It stays inside the supplied hosts, limits page count/depth, and only produces candidates for pages containing source/license/release signals.

Add domains rather than crawling the entire web.

### IGDB

Uses the official IGDB API only for commercial-game identity enrichment: title, developer/company, first release date, platforms, etc. IGDB requires Twitch developer credentials and explicitly describes the API as free for non-commercial use. IGDB results **must not** be treated as source-license or authorization evidence by themselves.

## Output

Each run writes JSON Lines when `--output` is supplied:

```text
data/discovery/inbox/<run-id>.jsonl
data/discovery/inbox/<run-id>.jsonl.run.json
```

The JSONL is intentionally raw-ish staging data. It can be inspected, filtered, deduplicated, and then promoted into the durable CSV/SQLite provenance ledgers.

## Examples

```bash
# Everything configured by the collector defaults.
python -m cgsdb_discovery.runner \
  --output data/discovery/inbox/latest.jsonl

# Internet Archive only.
python -m cgsdb_discovery.runner \
  --sources internet-archive \
  --ia-pages 10 \
  --ia-rows 100 \
  --output data/discovery/inbox/internet-archive.jsonl

# GitHub with authentication.
GITHUB_TOKEN=... python -m cgsdb_discovery.runner \
  --sources github \
  --github-pages 10 \
  --output data/discovery/inbox/github.jsonl

# Search known developer/rightsholder domains through the Wayback Machine.
python -m cgsdb_discovery.runner \
  --sources wayback \
  --wayback-domain https://example.com \
  --output data/discovery/inbox/wayback-example.jsonl

# Crawl known developer pages.
python -m cgsdb_discovery.runner \
  --sources developer-site \
  --developer-url https://example.com/ \
  --developer-url https://example.com/releases \
  --output data/discovery/inbox/developer.jsonl

# IGDB identity enrichment.
IGDB_CLIENT_ID=... IGDB_CLIENT_SECRET=... \
python -m cgsdb_discovery.runner \
  --sources igdb \
  --igdb-title "Star Ruler 2" \
  --igdb-title "Myst Online: Uru Live" \
  --output data/discovery/inbox/igdb.jsonl
```

## Safety and provenance

The collector never promotes a record directly into `data/games.csv`.

A source archive, search result, SteamDB package, IGDB record, GitHub repository, or Wayback capture is an **evidence/discovery lead**. Exact license, source completeness, authorization, and asset scope must be established separately before a candidate is promoted to canonical status.

For automated repeated sweeps, keep the raw JSONL outputs and the run metadata. This makes discovery auditable and enables regression comparisons between runs.

# Discovery collectors

The collector framework is designed for **high recall first, verification second**.

## Collectors

### Internet Archive

Uses the cursor-based Scraping API by default, so a query can continue past Advanced Search's 10,000-result paging ceiling. Each query follows the returned continuation cursor for a bounded number of batches and records the observed cursor/depth in run metadata. The legacy Advanced Search path remains available with `--ia-no-cursor` for compatibility/reproduction.

### GitHub

Uses the GitHub REST repository search API and then automatically inspects up to a configurable number of unique repositories. Inspection calls GitHub's `/license` endpoint and `/readme` endpoint, decodes the license file when available, extracts README source-release/license signals, and records separate license/README evidence. Authentication is optional for public data, but a `GITHUB_TOKEN` is strongly recommended for repeated sweeps. GitHub's current documentation lists 60 requests/hour unauthenticated and 5,000 requests/hour authenticated for the primary REST limit, with stricter search/secondary limits, so `--github-inspect-limit` keeps the deep phase bounded.

### SteamDB

Uses public SteamDB search HTML as the first-pass app enumerator, then expands each discovered app through its `/app/<id>/subs/` package page. Source-like package names are selected and their individual `/sub/<id>/` pages are fetched for package metadata, license text and source-completeness language. This catches dedicated source-code packages that ordinary game searches miss. Package discoveries remain evidence leads until the source/license is independently verified.

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

# Deeper IA cursor sweep plus larger GitHub/SteamDB expansion.
python -m cgsdb_discovery.runner \
  --sources internet-archive,github,steamdb \
  --ia-cursor-batches 25 \
  --ia-cursor-count 1000 \
  --github-pages 5 \
  --github-inspect-limit 300 \
  --output data/discovery/inbox/deep.jsonl

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


## Operational recommendations

Run collectors independently when possible so a failure or rate limit in one service does not discard results from the others.

For example:

```bash
mkdir -p data/discovery/inbox

python cgsdb.py discover \
  --sources internet-archive,github,steamdb \
  --ia-pages 10 \
  --github-pages 5

python cgsdb.py discover \
  --sources wayback,developer-site \
  --wayback-domain https://www.idsoftware.com \
  --developer-url https://github.com/id-Software/

python cgsdb.py ingest-discovery-inbox data/discovery/inbox/discovery-20261007T160000Z.jsonl

python cgsdb.py discovery-stats
```

### GitHub pacing

The collector intentionally uses bounded concurrency instead of firing one request per repository simultaneously. GitHub documents both primary and secondary rate limits, including a 5,000-request/hour authenticated primary limit and concurrency/endpoint restrictions on secondary limits. The collector's semaphore, per-host pacing, and retry-after/exponential-backoff handling are designed around those constraints. urlGitHub REST API rate-limit documentationhttps://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api

### Internet Archive depth

The default Advanced Search pages are bounded. For very deep archive mining, extend the query/page budget or add a dedicated cursor-based scraper adapter. Internet Archive documents a 10,000-result limit for sorted Advanced Search pagination and a separate scraping API for deeper result traversal. urlInternet Archive item search API documentationhttps://doc-tools.readthedocs.io/en/ia-test-gsod/item-search-apis.html

### Wayback

Wayback CDX is well suited to recovering removed source-release announcements, download pages and repository links. It supports JSON output, filtering, collapsing and pagination/resumption. urlWayback CDX documentationhttps://github.com/internetarchive/wayback/tree/master/wayback-cdx-server

### IGDB

IGDB requires a Twitch developer application and OAuth client-credentials flow. The collector therefore makes IGDB optional: missing credentials produce a recorded collector error rather than stopping the whole sweep. IGDB is used for title/developer/release/platform enrichment, never as a license decision. urlIGDB API documentationhttps://api-docs.igdb.com/

### SteamDB

SteamDB does not expose the same general public REST API surface as GitHub/IGDB for this use case, so the collector uses public HTML. The package enumerator expands app package pages and follows source-like `/sub/<id>/` records. This is particularly valuable for dedicated source-code packages; SteamDB's Crongdor listing, for example, explicitly describes a complete C++ source package and its GPLv3 terms. urlCrongdor source-code package on SteamDBhttps://steamdb.info/app/488190/subs/

### Raw versus promoted data

Never commit massive raw collector output by default. The recommended pattern is:

```text
collector → inbox JSONL → review / dedup → provenance CSV + SQLite → canonical games.csv
```

The JSONL inbox is the reproducible raw discovery artifact. The provenance ledgers are the durable, reviewable representation.

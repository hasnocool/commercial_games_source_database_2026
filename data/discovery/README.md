# Discovery / Provenance Layer

This directory is the high-recall research layer that sits beside the canonical `data/games.csv`.

It is intentionally **not** the canonical game database. A discovery result can be incomplete, duplicated, incorrectly attributed, leaked, or licensed more narrowly than its public availability suggests. Candidates move into the canonical table only after review.

## Files

### `candidates.csv`

One row per discovered game/source candidate.

Important fields:

- `candidate_id`: stable identifier for the discovery record.
- `game_key`: canonical game key when the candidate has been resolved to a game record.
- `discovery_sources`: semicolon-separated discovery surfaces such as `internet-archive`, `steamdb`, `igdb`, `github`, `wayback`, `primary-or-other`, or `secondary-research`.
- `discovery_query` / `discovery_url`: what produced the candidate.
- `review_status`: workflow state.
- `exact_license`: literal license claim captured by the current evidence; it is **not automatically an SPDX-normalized or legally verified identifier**.
- `source_completeness`: how much source was actually released.
- `authorization_status`: whether there is evidence of a developer/rightsholder-authorized release.
- `provenance_confidence` / `evidence_confidence`: confidence levels for provenance and evidence quality.

Recommended review states:

`new` → `needs-verification` → `accepted-canonical` or `rejected`.

Use `accepted-canonical-inherited-unreviewed` only for records bootstrapped from the existing canonical table.

### `evidence.csv`

One row per independent piece of evidence supporting a candidate.

Examples:

- developer/rightsholder announcement
- official source repository
- license file
- SteamDB package/depot record
- Internet Archive item
- IGDB game metadata
- Wayback capture
- preservation catalogue
- secondary research list

The importer computes an SHA-256 `evidence_fingerprint` from the candidate, source, URL, release date, license, scope, authorization signal, and completeness claim. Re-importing the same evidence therefore avoids uncontrolled duplication.

### `runs.csv`

One row per discovery sweep. Record:

- when the sweep ran
- which discovery source(s) were searched
- query or collection name
- candidates found
- candidates promoted into the canonical dataset
- notes about failures, rate limits, or scope

This makes repeated sweeps comparable over time.

## Discovery policy

The project uses a high-recall, evidence-first workflow:

1. Search discovery surfaces broadly.
2. Create a candidate even when the license is unresolved if the source is historically valuable.
3. Attach every meaningful evidence item independently.
4. Verify exact license text and source scope from the strongest available evidence.
5. Establish whether the source release was authorized.
6. Resolve accepted candidates into `data/games.csv`.
7. Keep rejected, leaked, accidental, and unresolved material visible in the discovery layer rather than silently deleting it.

A public archive URL is **discovery evidence**, not automatic permission to redistribute the source.

## CLI

```bash
python cgsdb.py init
python cgsdb.py discovery-stats
python cgsdb.py discovery-search --source internet-archive
python cgsdb.py discovery-search --review-status new
python cgsdb.py discovery-search doom --json
python cgsdb.py import-discovery
python cgsdb.py export-discovery
python cgsdb.py discovery-report reports/discovery-review.md
```

# Discovery data

The discovery layer is a high-recall staging and provenance system. It intentionally keeps candidate records separate from the canonical game table.

## Candidate classification

In addition to license, authorization and source-completeness fields, candidates track:

- `provenance_class`: how the material appears to have become available.
- `leak_status`: whether a leak is absent, reported, suspected or historically/explicitly confirmed.
- `content_types`: source code, binary, assets, full game, SDK, server, tools, documentation, and other facets.
- `access_status`: public, restricted, removed, private, dead-link or unknown.
- `redistribution_status`: allowed, restricted, forbidden or unknown.
- `classification_tags`: extensible labels for future filters.

Evidence records contain matching `*_claim` fields so classifications remain attributable to individual sources.

Leak records are valid research candidates even when unauthorized. They are never treated as open-source merely because the source exists, and the collector does not redistribute leaked code or assets.

## Useful queries

```bash
python cgsdb.py discovery-search --leak-status reported
python cgsdb.py discovery-search --provenance leak
python cgsdb.py discovery-search --content-type source-code --redistribution-status forbidden
python cgsdb.py discovery-search --tag leaked-content
```

The filters combine with AND semantics.

# Commercial Games Source Database 2026

A local-first database and browser for commercially released games whose source code was later made available.

The project keeps the supplied research CSV as the canonical seed dataset and builds a queryable SQLite database around it. It is intended for preservation research, source-port discovery, engine archaeology, modding research, and prioritising candidates for new Rust ports or rewrites.

## Current dataset

- **110 game records**
- Popularity ranking from the supplied 2026 research
- Original year and developer
- Source-release year/status
- License/source-availability classification
- Source scope and asset/data caveats
- Primary and modern source-port links
- Engine/architecture notes
- Modding potential
- Supplied Rust Port Candidate score
- Historical GitHub stars, where already recorded
- Optional live GitHub star refresh

The dataset deliberately distinguishes **open source**, **source available**, **proprietary SDK/source**, and **unclear/recovered** cases. It does not redistribute proprietary game source code or commercial assets.

## Run without installing anything

Python 3.12+ and the standard library are enough:

```bash
python cgsdb.py init
python cgsdb.py stats
python cgsdb.py search doom
python cgsdb.py search --license open-source --min-rust-score 9
python cgsdb.py self-test
python cgsdb.py serve --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080/`.

## Optional package installation

```bash
python -m pip install -e .
cgsdb init
cgsdb serve
```

The runtime has no third-party Python dependencies.

## GitHub metadata refresh

Only repositories already recorded in the dataset are queried. The public GitHub REST API applies its normal unauthenticated rate limit. A token can be supplied through `GITHUB_TOKEN`.

```bash
python cgsdb.py sync-github
GITHUB_TOKEN=... python cgsdb.py sync-github
```

Live stars are stored separately in SQLite, so the original research values remain intact.

## Architecture

```text
data/games.csv
       │
       ▼
   cgsdb.py ─────► SQLite (data/games.db)
       │
       ├──── CLI: search / stats / export / sync-github
       │
       └──── Threaded local HTTP server
                     │
                     ▼
              web/index.html
```

Each HTTP request opens its own short-lived SQLite connection. The dashboard is read-only; data mutation happens through explicit CLI commands.

## Database fields added by the application

- `game_key`: stable slug-style key.
- `github_owner` / `github_repo`: parsed GitHub identity.
- `github_stars_live`: latest fetched star count.
- `github_checked_at`: UTC refresh timestamp.
- `license_family`: normalized license grouping.
- `source_status`: coarse research status.
- `rust_score_computed`: supplementary deterministic heuristic; the supplied research `Rust Port Candidate (1-10)` value is never overwritten.

## Safety / provenance rules

1. The CSV remains the canonical research record.
2. Derived metadata is kept separate from the original values.
3. A source being reachable does not mean its license permits redistribution.
4. Recovered or accidental source is explicitly flagged instead of being treated as an authorized open-source release.
5. The application catalogs links and metadata; it does not package proprietary game source or commercial assets.

## Roadmap

- Normalize one-to-many source-port relationships.
- Add repository/license verification history.
- Add source-release evidence records with independent primary sources.
- Add engine-family clustering and architecture facets.
- Add importers for new research CSVs without destroying historical snapshots.
- Add candidate scoring profiles for Rust, Zig, Bevy, SDL3, and WebAssembly.
- Add a static export suitable for GitHub Pages.

## License

Application code: MIT.

The linked game source code, assets, trademarks, and individual research records retain their own licensing and provenance conditions.

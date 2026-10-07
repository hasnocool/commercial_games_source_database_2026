# Commercial Games Source Database 2026

A local-first database and browser for commercially released games whose source code was later made available.

The project keeps the supplied research CSV as the canonical seed dataset and builds a queryable SQLite database around it. It is intended for preservation research, source-port discovery, engine archaeology, modding research, and prioritising candidates for new Rust ports or rewrites.

## Current dataset

- **227 game records**
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

### 2026-10-07 research expansion

This update adds **22 additional commercial games with documented public source releases or source-availability arrangements**, including Little Big Adventure 1/2, Amnesia: A Machine for Pigs, the Blendo Games releases, Pyrodactyl's games, Urban Chaos, Vangers, Perimeter, Toki Tori 2+, Skin Deep, Machines: Wired for War, Towns, Unturned, Barotrauma, Monster RPG 2, and A Dark Room.

The catalog intentionally includes restrictive source releases when they are useful for study/modding, but marks them separately: **Unturned** and **Barotrauma are source-available, not OSI open source**. Their licenses restrict redistribution and/or use to game-specific non-commercial modding. Likewise, engine-only releases such as **Little Big Adventure 1/2** and **Toki Tori 2+** are labeled by source scope rather than being presented as complete asset-free game releases.

New records are appended as ranks **111-132** so the established research ranking remains stable; these are insertion-order ranks, not a claim that the new titles have been globally popularity re-ranked.

Run `python cgsdb.py sync-github` to populate live GitHub star counts for the newly added repositories.


### 2026-10-07 research expansion — discovery sweep

The database now contains **191 records**. This sweep expands beyond GitHub-centric discovery by using three complementary discovery surfaces:

- **Internet Archive:** the historical Game Source Code Collection is a high-recall preservation index, but its contents mix licenses and provenance. Archive hits are therefore discovery leads, not automatic proof of open-source licensing.
- **SteamDB:** useful for identifying commercial Steam releases and hidden/free source-code packages. For example, SteamDB exposes a dedicated **Crongdor the Barbarian source-code package** marked GPLv3 and free on demand. urlSteamDB source package evidencehttps://steamdb.info/app/488190/
- **IGDB:** useful for cross-checking commercial release dates/developers and surfacing games that may not appear in GitHub searches. It is treated as metadata/discovery evidence rather than a substitute for license verification.

This pass adds older and less-obvious source releases including **NoGravity, Planet Blupi, Principia, Soldat, Sopwith, Ares/Antares, Avara, Allegiance, Meridian 59, Star Ruler 2, Starshatter, Tribal Trouble, Catacomb/Catacomb 3D, The Colony, C&C Generals Zero Hour, C&C Renegade, Cortex Command, Delver, Quake 4, Spacebase DF-9, Revenge of the Titans, Crongdor the Barbarian,** and a **DROD series** engine-source record.

Two important classification rules remain in force: leaked/accidental/found source is **not** treated as an authorized open-source release, and restrictive source releases such as **Unturned** and **Barotrauma** stay marked source-available rather than OSI open source.

The new records are appended after the established ranking. Their rank numbers are **catalog insertion ranks**, not a new global popularity ordering.


### Deeper discovery sweep — Internet Archive, SteamDB and IGDB

This revision pushes the catalog beyond the well-known GitHub-hosted releases. **Internet Archive** is used as a preservation/discovery index for historical source archives; **SteamDB** is especially useful for finding hidden/free source-code packages (for example the Crongdor source package is explicitly GPLv3 and free-on-demand); and **IGDB** is used as a commercial-game metadata cross-check. These services are discovery evidence, not automatic proof of an open-source license.

The new records include platform-specific source releases (3DO, SNES, Jaguar, Apple II, PlayStation), obscure developer releases, and newer 2024–2026 source drops. Records with unresolved or restrictive licensing are intentionally included but marked **source-available / license unclear**, **source-available / non-commercial**, or **proprietary** rather than being counted as OSI open source.

The catalog now contains **227 records**. This is deliberately a high-recall preservation database: a public source archive is valuable even when its license is not yet resolved, provided the provenance and limitations are explicit.

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

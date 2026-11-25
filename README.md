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

### High-recall discovery collectors

The repository now includes asynchronous discovery collectors for **Internet Archive, GitHub, SteamDB, Wayback, developer/rightsholder sites, and IGDB**. The deep-discovery path now uses the Internet Archive cursor scraper, enumerates SteamDB source-like packages attached to discovered apps, and automatically inspects GitHub LICENSE and README content for stronger provenance signals.

The discovery/provenance layer also tracks **leaked, unauthorized, recovered, reverse-engineered, fan-maintained, and authorized source availability separately**. Leak records are research metadata rather than open-source approvals. Classification is faceted so users can filter by provenance, leak status, content type, access state, redistribution rights, authorization, and custom tags.


### 2026-11-25 PC C/C++ source and dependency audit

The PC source research now has a dedicated [PC C/C++ source dependency audit](docs/PC_CPP_SOURCE_DEPENDENCY_AUDIT.md). It separates original authorized source releases (Quake, DOOM, POSTAL, ROTT, Shadow Warrior, Serious Sam, and others), restricted releases (Descent, Descent II, FreeSpace 2, Jagged Alliance 2), source ports/reconstructions (Dethrace, Devilution, NBlood, ForsakenX), and archival/leaked material (Blood & Magic demo source; Blood Alpha).

The audit records legacy compiler and build requirements, proprietary SDK/library blockers, excluded game data, component-level licensing, and buildability gates. Examples include POSTAL's Visual C++ 6.0/RSPiX/SmartHeap stack, FreeSpace Open's current CMake 3.21+ and mandatory libRocket submodule, and Descent II's explicitly incomplete source package. The discovery ledgers currently contain **327 candidate records and 525 evidence records**; these are discovery/provenance entries, not the 227 canonical game records above.

No proprietary game assets, disc images, leaked source archives, or demo binaries were added to this repository.


Install the optional collector dependency:

```bash
python -m pip install -e .
```

Run a broad discovery sweep into the local inbox:

```bash
python cgsdb.py discover
```

Target individual sources:

```bash
python cgsdb.py discover --sources internet-archive --ia-cursor-batches 25 --ia-cursor-count 1000
GITHUB_TOKEN=... python cgsdb.py discover --sources github --github-pages 10 --github-inspect-limit 300
python cgsdb.py discover --sources steamdb
python cgsdb.py discover --sources steamdb --steamdb-app 488190
python cgsdb.py discover --sources wayback --wayback-domain https://example.com
python cgsdb.py discover --sources developer-site --developer-url https://example.com/
IGDB_CLIENT_ID=... IGDB_CLIENT_SECRET=... python cgsdb.py discover --sources igdb --igdb-title "Star Ruler 2"
```

The default configuration lives in `data/discovery/collector.toml`. Raw JSONL discovery output is ignored by Git by default so large sweeps do not accidentally inflate the repository.

Promote a completed raw run into the machine-readable provenance ledgers:

```bash
python cgsdb.py ingest-discovery-inbox data/discovery/inbox/discovery-YYYYMMDDTHHMMSSZ.jsonl
python cgsdb.py discovery-stats
python cgsdb.py discovery-search --review-status new
```

The flow is:

```text
Internet Archive / SteamDB / IGDB / GitHub / Wayback / developer sites
                              │
                              ▼
                       async collectors
                              │
                              ▼
                         JSONL inbox
                              │
                       dedup + review
                              │
                              ▼
                 provenance CSV + SQLite
                              │
                       manual verification
                              │
                              ▼
                     canonical games.csv
```

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


## Discovery / provenance layer

The canonical `data/games.csv` remains separate from the high-recall research layer under `data/discovery/`.

The discovery layer contains:

- `candidates.csv` — one record per discovered candidate, including discovery source, query/URL, review state, literal license claim, source completeness, authorization state, and confidence fields.
- `evidence.csv` — independent evidence records for each candidate. The importer computes a stable SHA-256 evidence fingerprint to prevent duplicate evidence from accumulating across repeated sweeps.
- `runs.csv` — timestamped discovery sweeps with source sets, queries/collections, candidate counts, and notes.
- `sources.csv` — the discovery-source registry describing the intended role of Internet Archive, SteamDB, IGDB, GitHub, Wayback, developer/rightsholder sites, and secondary research.
- `schema.json` — the machine-readable field contract and review-state vocabulary.
- `README.md` — workflow and provenance policy.

The current bootstrap contains **227 candidate records and 318 evidence records** inherited from the 227 canonical games. These are explicitly marked `accepted-canonical-inherited-unreviewed`; they are not claims that every historical source/license has been freshly re-verified.

### Discovery workflow

Use discovery data as a staging layer:

```bash
python cgsdb.py discovery-search --source internet-archive
python cgsdb.py discovery-search --review-status new
python cgsdb.py discovery-stats --json
python cgsdb.py discovery-report reports/discovery-review.md
python cgsdb.py import-discovery
```

A candidate should normally move through:

`new` → `needs-verification` → `accepted-canonical`

or to `duplicate`, `rejected`, or `unauthorized`.

Discovery services are deliberately separated by role. Internet Archive and preservation archives maximize historical recall; SteamDB and IGDB help identify commercial releases; GitHub and developer/rightsholder pages are stronger for repository/license/authorization verification; Wayback is used to recover historical announcements and removed links.

A public archive copy is not automatically an authorized open-source release. The canonical dataset should only claim an open-source status when the evidence supports the license and provenance.

### Expanded source registry — 2026-11-25

The discovery registry in `data/discovery/sources.csv` now includes dedicated entries for the official id Software GitHub organization, Internet Archive's Game Source Code collection, its Advanced Search and item-metadata interfaces, a DOOM SNES archival example, Video Game Preservation and Historical Source repositories, Quake engine/source-port indexes, and broader commercial-game/arcade source research indexes.

These entries broaden the places researchers can search; they do **not** imply that every index is an implemented automated collector. The existing collector CLI only runs source adapters that are actually implemented. Treat indexes and archive collections as candidate discovery surfaces, then capture item-level evidence and verify the exact source scope, authorization, license, and asset rights.

Examples found during this research:

- Official DOOM source release: https://github.com/id-Software/DOOM
- Official Quake GPL source release: https://github.com/id-Software/Quake
- Internet Archive DOOM SNES source preservation item: https://archive.org/details/jeffs-doom-snes-disk-images
- Quake engine/source-port discovery index: https://quakeengines.github.io/
- Video-game source-code preservation research: https://mrcook.uk/arcade-game-source-code/

The original DOOM and Quake engine source releases are not equivalent to permission to redistribute the original commercial game data. The DOOM SNES Archive item is recorded as historical preservation evidence, not as an independently verified open-source license grant.

### Popular PC source-catalogue expansion — 2026-11-25

A new discovery sweep used the [Commercial Game Sources GitHub catalogue](https://github.com/commercial-game-sources), which explicitly distinguishes original source archives from reconstructions, reimplementations, remakes and convenience ports.

This pass added **25 new PC-game candidates** to `data/discovery/candidates.csv` and **25 catalogue evidence records** to `data/discovery/evidence.csv`. Four titles from the discovery list were already present in the canonical games table and were not duplicated. The newly staged candidates include Rogue, Digger, Willy the Worm, Leisure Suit Larry, Double Dragon II, Eye of the Beholder II, Stunts, Another World, Dune II, Ken's Labyrinth, Flashback, Duke Nukem II, Beneath a Steel Sky, Jazz Jackrabbit, Pinball Fantasies, Witchaven, Tyrian, In Pursuit of Greed, Diablo, Blood, Dungeon Keeper, Carmageddon, Forsaken, Jazz Jackrabbit 2, and S.T.A.L.K.E.R.: Call of Pripyat. Commander Keen in Keen Dreams, Penumbra: Overture, Amnesia: The Dark Descent, and Thirty Flights of Loving were already in the canonical table and were not duplicated.

These are **discovery candidates, not newly verified canonical game records**. Their review status is `needs-verification`; license, authorization, source completeness, and redistribution are left unresolved until upstream repositories and source archives are inspected. Reimplementations, remakes and reverse-engineered projects are tagged so they cannot be mistaken for original authorized source releases.

The discovery source registry now includes `commercial-game-sources`. See the source index at https://github.com/commercial-game-sources and its explanation of original archives versus derived projects. A source listing is a lead, not proof of rights.


### PC source-code discovery expansion — 2026-11-25 (second pass)

A second research pass added **27 additional PC-game source-availability candidates** and **27 corresponding evidence records**. It used the [commercial-game source-code index](https://en.wikipedia.org/wiki/List_of_commercial_video_games_with_available_source_code) and registered the [DOS Games Archive source-code catalogue](https://www.dosgamesarchive.com/license/source-code), which currently reports 96 DOS source-code game listings. The DOS Games Archive [source-link directory](https://www.dosgamesarchive.com/links) is also registered as a discovery reference for locating upstream repositories and historical releases.

New candidate leads include **Actua Soccer 96, Age of Pirates: Captain Blood, Age of Pirates 2: City of Abandoned Ships, Aliens versus Predator 2, Army Men, The Black Cauldron, Blood & Magic, Crysis, Crysis 2, Crysis 3, Dark Reign 2, Donald Duck's Playground, Duke Nukem Forever (2001 alpha), EVE Online, Fate, Far Cry, The F.A. Premier League Stars, FIFA 97, Falcon 4.0, Half-Life 2 (2003 alpha), Harry Potter and the Chamber of Secrets, King's Quest III, three additional Leisure Suit Larry titles, Lineage II, GunZ: The Duel, Gears of War, Grand Theft Auto V,** and **Cyberpunk 2077**. The candidates already present in the database were skipped.

This is a **high-recall source-availability research layer**, not a list of approved open-source projects. The source-code index explicitly includes leaks, accidental disclosures, recovered archives, and material with unclear legal status. Candidates are tagged accordingly; no leaked or accidentally exposed code is promoted as authorized, and no license or redistribution permission is inferred from a catalogue listing. Primary archives, developer/rightsholder statements, source completeness, exact versions, and asset/data rights still require item-level verification.

After this pass, the discovery ledgers contain **279 candidate records, 370 evidence records, and 25 registered discovery sources**. The canonical data/games.csv was not changed; candidate records remain in needs-verification until independently reviewed.


### Modern PC games: original release years 2020–2026 (research pass, 2026-11-25)

This pass separates the **original game release year** from the **source availability/release date** recorded in the evidence ledger. The requested 2027 year is reserved for future releases because it has not occurred yet.

New candidate records in this date range:
- **Friday Night Funkin'** (2020): official source code under Apache-2.0; assets have a separate license.
- **Fall Guys: Ultimate Knockout** (2020): reported accidental intermediate IL2CPP source inclusion in a 2021 update; unauthorized/unclear, not an open-source release.
- **FIFA 21** (2020): reported source-code leak in 2021; unauthorized.
- **Guilty Gear -Strive-** (2021): reported source archive leak in 2025; unauthorized.
- **Roboden** (2023): commercial Windows RTS; public MIT source repository.
- **Celeste 64: Fragments of the Mountain** (2024): source repository from the original developers; source folder is MIT, while game IP/content has separate restrictions.
- **Space Race** (2024): Windows game with source code identified as MIT in its credits; third-party asset rights need separate review.
- **Worlds Upon The Wind** (2026): developer released the game source and assets as CC0 in September 2026, excluding third-party audio.

The existing **Skin Deep** (2025) canonical candidate was refreshed with its official 2025-06-26 developer source-release announcement. Its C++ game/engine source is GPL; art, models, textures, audio, and levels are excluded from the source license and are not redistributable. The existing candidate was updated rather than duplicated.

The MobyGames officially released source-code group was added as a discovery source. Its stated criteria exclude unofficial leaks and SDK-only entries; use it to discover developer/publisher releases, then verify each primary source. Other secondary indexes are used for leak leads only. No leaked source is treated as licensed or authorized.

After this pass, the discovery ledgers contain **287 candidate records, 381 evidence records, and 26 registered discovery sources**; the canonical data/games.csv remains at **227 records**. These are discovery-layer records and require item-level validation before canonical promotion.


### 2026 source-release discoveries: older PC games and engine frameworks (2026-11-25)

This pass extends the independent view of **older games whose source became available during 2026**, without changing their original release years.

- **Arma: Cold War Assault / Operation Flashpoint: Cold War Crisis** (original 2001; source released 2026-06-22): Bohemia Interactive published the Poseidon engine and game source under GPL-3.0-or-later with additional Section 7 terms. Game assets are separately licensed under APL-SA; trademarks are not granted.
- **Unturned** (original full release 2017; source released 2026-07-07): official Unity project under the custom U3 SDK License Agreement. Free, non-commercial PC mods only; not OSI open source. Core asset bundle and certain third-party/anti-cheat code are excluded.
- **EVE Online / Carbon engine framework** (original game 2003; engine source transition completed 2026-07-01): Carbon is the framework behind EVE Online/EVE Frontier, not the full EVE game/client/server source. Module licenses vary (reported MIT, Apache-2.0 and PSF); inspect each module.
- **s&box engine and editor** (2026): separate engine/framework record, not a conventional standalone game's complete source. C# engine/editor source is MIT, while native Source 2 binaries and third-party components have separate terms.
- **Tails Adventure (2026 remake)**: a community remake/reimplementation of Sega's 1995 game, not original Sega source. Its C++ source is GPL-3.0; Sega IP, trademarks and assets are not granted by that code license.

The existing canonical Unturned candidate was refreshed rather than duplicated. These records are classified by source scope and rights restrictions so engine-only source, custom non-commercial licenses, and community remakes are not counted as unrestricted open-source game releases.

After this pass, the discovery ledgers contain **291 candidate records, 394 evidence records, and 26 registered discovery sources**. The canonical games table remains unchanged.


### 2020–2025 source-release chronology expansion (2026-11-25)

The discovery candidate schema now includes a dedicated **source_release_year** column, separate from **original_year**. The evidence ledger continues to hold the precise release date or date precision available. This allows older games with recent source releases to be filtered without misdating the original game.

Primary-source evidence and metadata were refreshed for:
- **Command & Conquer: Tiberian Dawn**, **Red Alert**, **Renegade**, and **Generals / Zero Hour** — EA's authorized GPL source release on 2025-02-27. The 2020 Remastered Collection DLL source is a separate, incomplete release; the 2025 repositories are the later fully recovered original source. Build dependencies, missing legacy libraries, third-party SDKs, assets and trademarks remain distinct considerations.
- **VVVVVV** — developer release 2020-01-10 under a custom, non-OSI license; personal compilation is permitted, while broader distribution is restricted.
- **Unrest**, **Will Fight for Food: SAS: GOTH**, and **Good Robot** — Pyrodactyl developer source releases 2020-08-03 under MIT; game assets still require the commercial installation.
- **Perimeter** — GPLv3 game source; purchased game resources/assets remain required.
- **Toki Tori 2+** — Two Tribes in-house engine source released 2021-12-17 under GPL-2.0-only; engine-only, not a complete game asset/source release.
- **The Colony** — original creator's PC/Mac/Amiga source published 2023-06-06 under Apache-2.0.
- **Descent 3** — source released 2024-04-16 with copyright-holder authorization, GPL-3.0-or-later.
- **Rogue Legacy** — source published 2024-10-08 under a custom license; proprietary art/audio excluded and commercial distribution restricted.
- **Star Fighter (3DO)** — 3DO source and assets published 2024-04-25 with contributor permission; no explicit open-source license identified, so redistribution rights are not inferred.
- **Brány Skeldalu / Gates of Skeldal** — 2025 MIT C++ source port, not the original game's source; original DOS/Windows assets remain proprietary.

New candidate records:
- **Anodyne 2: Return to Dust** (original 2019; source published August 2024): complete source/assets repository under a custom license that is explicitly not OSI open source; asset access is restricted to paid owners.
- **King under the Mountain** (original 2022; source release January 2024): developer's Java/LibGDX project under MIT.
- **Mountaincore** (original 2023; source release 2025-04-22): developer's Java/LibGDX game source under MIT.

Added two chronological discovery indexes: GamingOnLinux's Source Code Release category and the commercial later-source-code index. They remain secondary discovery sources, not proof of licensing. All refreshed records remain in the discovery layer pending full item-level QA and canonical promotion.

After this pass, the discovery ledgers contain **294 candidate records, 416 evidence records, and 28 registered discovery sources**. The canonical `data/games.csv` remains at **227 records**. No leaked source was promoted or treated as authorized. Engine-only releases, source ports, custom licenses, incomplete builds, and archival releases with no license are explicitly distinguished.


### Additional 2020–2022 Windows source releases (2026-11-25 follow-up)

A focused RPG/engine-source search also refreshed these inherited candidates with primary developer/repository evidence and populated their `source_release_year` values:

- **Amnesia: The Dark Descent** and **Amnesia: A Machine for Pigs** (original 2010 / 2013; source release 2020-09-23): Frictional Games released full game and editor code under GPL-3.0. The commercial game content/assets remain proprietary; the old FBX SDK dependency may prevent a straightforward build.
- **Age of Pirates 2: City of Abandoned Ships** (2009; Storm Engine source release 2021-03-25): the GPL-3.0 Storm Engine is engine-only; game assets are not included.
- **Age of Pirates: Captain Blood** (2010; source release reported 2022-11-28): the Storm Devs repository publishes the game's engine source under GPL-3.0, not the commercial game assets.

The Storm Engine repository and documentation are now registered as a primary discovery source. These are not additional candidate rows because all four titles already existed in the discovery ledger; six dated evidence records were added. The candidate ledger remains at **294 records**, evidence now contains **422 records**, and registered sources now total **29**. Canonical `data/games.csv` remains at **227 records**.


### DOS / Windows adventure and RPG archive sweep (2026-11-25)

This pass prioritized older DOS/Windows games whose source became publicly available or was recovered during 2020–2026. It updated five existing candidate rows and added nine evidence records; no duplicate game candidates were created.

- **Prince of Persia (1989, Apple II)** — original 6502 assembly source recovered from disks and published by author Jordan Mechner in 2022. This is a historical author release, not an OSI-licensed project. The author permits studying, modifying and attempting to run the source, but expressly grants no rights in the Prince of Persia franchise; Ubisoft controls game distribution.
- **God of Thunder (1993, DOS)** — creator Ron Davis published the main source into the public domain on 2020-03-27; a separate archive with sound/music/utilities followed 2020-07-19. The main source is incomplete and does not compile as-is; licensed audio dependencies are missing, and graphics remain proprietary.
- **Little Big Adventure (1994) and Little Big Adventure 2 (1997)** — current rights holder 2.21 released historic engine source on 2021-10-27 under GPL-2.0-only. These are engine-only source releases; proprietary art, models, textures, audio and excluded third-party libraries are not included in the grant.
- **Machines: Wired for War (1999)** — Nightdive-authorized source release in 2020 under GPL-3.0. The source repository identifies Nightdive as the rights holder and the release as authorized; assets are separate.

The DOS Games Archive source-code index is now registered as a secondary discovery source. It lists 96 DOS games with source downloads, but a listing is not proof of source release date, license, authorization, completeness or asset rights. Its candidates will be checked individually against original authors, rights holders and archive readmes.

**ScummVM preservation distinction:** ScummVM credits acknowledge original source donations for titles including The Journeyman Project: Pegasus Prime, The Journeyman Project 2, the two Lost Files of Sherlock Holmes games, Hyperspace Delivery Boy and Mission Supernova. These credits establish that source was provided to the preservation project, not that the source is publicly redistributable. They are therefore leads for further rights research, not public-source candidates by default.

The current discovery ledger contains **294 candidate records, 431 evidence records, and 30 registered discovery sources**. The canonical `data/games.csv` remains at **227 records**. No ScummVM-only source donations were misclassified as public source releases.


### DOS reconstruction / source-port and simulation milestone sweep (2026-11-25)

This pass adds a distinct reconstruction layer rather than treating every source-derived project as original game source:

- **Duke Nukem II (1993)** — the `Duke2Reconstructed` project began 2022-06-17 and recreates C/assembly source from disassembly of the original executable. It aims for a byte-identical DOS binary. No license file or explicit redistribution grant was identified; retain as a public reconstruction lead, not an open-source-licensed original source release.
- **Cosmo's Cosmic Adventure (1992)** — **Cosmore** began 2020-11-08 and reconstructs the v1.20 DOS source using the original compiler/toolchain. The reconstruction code is MIT-licensed; the original game IP and assets are not thereby relicensed. The project reports 96.30% binary matching, not 100%.
- **Raptor: Call of the Shadows (1994)** — the DOS repository published in 2023 contains a community reverse-engineered source port/reconstruction under GPL-2.0-or-later, including APODMX in place of a proprietary audio library. It is not verified as a rightsholder-authorized original-source release; original game data remains separate.
- **Chris Sawyer's Locomotion (2004)** — **OpenLoco** is a community MIT reimplementation, not original source. The project began in 2018; the developers announced on 2025-09-30 that all original game functions had been implemented. Original Locomotion data files are still required to play it.

These entries are separately tagged as community reconstruction, source port or reimplementation. Their repository licenses apply to the new project code only; they do not automatically grant rights to original game data, assets or trademarks. OpenLoco's 2025 milestone is recorded as a completion event, not falsely represented as its initial source-release year.

The DOS decompilation/source-port index is now registered as a secondary discovery source. **Dungeons of Noudar** was not added as a commercial game candidate because it is an original DOS homebrew project, not a commercial-game source release. ScummVM source donations remain excluded from the public-source set unless public redistribution rights can be established.

The discovery ledger now contains **296 candidate records, 436 evidence records, and 31 registered discovery sources**. The canonical `data/games.csv` remains at **227 records**.


### DOS Games Archive RPG / adventure / strategy audit — first verified tranche (2026-11-25)

The DOS Games Archive source-code index currently reports 96 DOS games. Its list is treated as a discovery index, not proof that each entry is a commercial title, original source release, authorized publication, or OSI-licensed project. The audit reviewed the six listing pages and selected RPG, adventure and strategy records for deeper provenance checks.

**Existing candidates enriched:**

- **Beneath a Steel Sky (1994)** — Revolution Software supplied the original assembly source to ScummVM with its blessing and support; ScummVM announced this on 2003-08-02. DOS Games Archive lists a 405 kB C++/assembly source ZIP. The game's freeware license governs; this is not an OSI source license. The archive ZIP is a mirror, not the authoritative release.
- **Amulets & Armor (1997)** — original developer United Software Artists released the game as freeware and source under GPL-3.0-only in 2013. The official repository contains C source, DOS and Windows build projects, utilities, artwork/icons and packaged data. Asset/data and third-party library licensing still requires file-level review.
- **Gladiator (1995)** — Forgotten Sages Development Team announced in the OpenGlad repository that the original game was open-sourced under GPL on 2002-07-01. The modern OpenGlad project is a continued port with additional campaigns, multiplayer and modding features; do not conflate its later code with the original DOS release.
- **Strife (1996)** — DOS Games Archive explicitly labels `strife-master.zip` as reconstructed sources. It is not the original Rogue Entertainment source release; reconstruction license and redistribution rights need separate review.

**New discovery candidate:**

- **Anacreon: Reconstruction 4021 (1987)** — originally commercial DOS 4X strategy game. Author George Moromisato later released DOS v2.0 as freeware with source; DOS Games Archive lists `DOSAnacreonSource20.zip`. Secondary chronology places source availability around 2004, but the exact release date and source license remain unverified. It is recorded as author-released source with no explicit license identified, not as OSI open source.

**Other audit leads:** Lords of Midnight PC / Doomdark's Revenge PC, Gladiator, Grange Murders, Linley's Dungeon Crawl, and the source entries for other archive titles are being checked individually. Entries such as modern freeware/homebrew, engines, editors, ports and reconstructions are not automatically included as commercial original-source releases. ScummVM donations are treated as evidence of authorized preservation access, not automatically public source redistribution rights.

The DOS Games Archive's current source index is registered as a secondary discovery source. This tranche added one candidate and six evidence records, enriched four existing candidates, and did not change canonical `data/games.csv`. The discovery ledger then contained **297 candidate records, 442 evidence records, and 31 registered discovery sources**.

### Cross-platform console and PC source discovery — first tranche (2026-11-25)

This tranche begins the expansion beyond PC/DOS to console source archives. Console and PC candidates are classified independently as original authorized releases, source found/unverified, decompilation/reconstruction, or port/reimplementation. Language, completeness, authorization and buildability are not inferred from an index label.

**Four new discovery candidates:**

- **WipEout (1995, PS1 + Windows)** — Forest of Illusion published source archives supplied by March42 on 2022-03-27. The releasers explicitly said it was not an official release, restricted the purpose to preservation/education, and did not know whether it built. Classified as source found/unverified, not an authorized release; license and archive completeness remain unknown.
- **Turok: Dinosaur Hunter (1997, N64)** — original source reportedly surfaced in 2018 from an unknown patron, possibly originating from an SGI workstation sold after Acclaim's bankruptcy. Technical analysis reports predominantly C with a small number of assembly files. Origin, authorization, license, completeness and buildability remain unverified.
- **B.O.B. (1993, SNES)** — SNES source reportedly found on a hard drive purchased on eBay in 2008. A later public repository has Source, Maps and Sound directories and describes completeness as “probably complete”; this is not independently verified and no authorization/license is established.
- **DOOM (1995, SNES / DOOM FX)** — original port programmer Randy Linden released source in 2020. Contemporary discussion describes an initial phase-one release with copyrighted assets removed and the original toolchain/compiler utilities not included at that stage. This is an original-programmer release, but partial source, license and buildability require further inspection. The code is primarily 65816/Super FX assembly, not C/C++.

**Existing candidates enriched:**

- **California Watersports (PS1)** — RetroReversing reports a 2020 source release with developer Mark Theyer's permission and points to Internet Archive item `cws-src`. Authorization is recorded as developer-permitted; exact license, archive inventory, language, completeness and buildability remain unverified.
- **Penumbra: Overture (2007, PC)** — official Frictional Games repository confirms GPL-3.0-or-later code, C++ source, and Xcode, Visual Studio 2003 and CMake project files. Build files are present but a successful build was not performed.
- **Return to Castle Wolfenstein (2001, PC)** — id Software's official multiplayer source repository and 2010 release announcement establish authorized GPL-3.0 source with additional terms. The release includes C/C++ code and Windows/Linux build instructions; game data remains under the original EULA. Buildability was not independently tested.
- **Amnesia: The Dark Descent** remains an official GPL-3 source release; the repository README identifies a legacy FBX SDK 2012 dependency that prevents a straightforward current build.

This tranche added **four candidates and seven evidence records**, enriched three existing candidates, and did not promote any of the new console candidates into canonical `data/games.csv`. It also confirms that the existing `Forsaken` community repository is a substantial port/toolchain migration, not a direct claim that the public ForsakenX repository is an untouched original source drop.

**Current discovery ledger after this tranche:** 301 candidate records, 449 evidence records, 31 registered discovery sources. Canonical `data/games.csv` remains at 227 records.

### Nintendo N64 / GBA and PlayStation source discovery — second console tranche (2026-11-25)

This pass expands the console ledger while keeping unauthorized disclosures and retail-disc recoveries separate from authorized releases. The RetroReversing console index is a discovery aid, not proof of licensing or permission.

**Nintendo 64 — Gigaleak 2 source inventory (10 candidates):**

- 1080 Snowboarding
- Animal Crossing (Animal Forest)
- Dr. Mario 64
- F-Zero X
- Mario Kart 64
- NBA Courtside
- NBA Courtside 2: Featuring Kobe Bryant
- Star Fox 64
- Yoshi's Story
- Wave Race 64

These are recorded as **found/leaked**, not authorized source releases. RetroReversing's inventory identifies individual N64 source directories in the July 2020 CVS archive, which reportedly originated from Nintendo-to-iQue/Routefree localization repositories. The database does not host or redistribute the leaked files. Language, exact source completeness, build files and dependencies remain unaudited.

**Game Boy Advance — Gigaleak 2 source inventory (2 candidates):**

- Super Mario Advance
- Wario Land 4

Both are recorded as unauthorized leak discoveries. Their directory presence does not establish complete game source, C language composition, buildability or redistribution rights.

**PlayStation 1 — retail-disc and repository discoveries (7 candidates):**

- **360: Three Sixty** — source reportedly left on the retail disc.
- **Battle Konchuuden** — source reportedly found on the retail CD-ROM.
- **Beatmania APPEND 5th MIX** — Psy-Q source reportedly found on the retail disc.
- **Chill** — an earlier source snapshot reportedly embedded in the retail disc's `cdfiller.dat` archive.
- **Jimmy Johnson's VR Football '98** — historical source archive dated 1997-05-01; provenance and archive contents still require inspection.
- **SpongeBob SquarePants: SuperSponge** — public repository claims full VSS history, complete source and build scripts; identifies C++ and a Windows 98-era Slink requirement. Its README contains a copy/paste title mismatch in the release-information section, so build/completeness claims remain unverified.
- **Ultimate Mortal Kombat 3** — repository explicitly labels the PS1 source incomplete and not buildable.

Retail-disc discovery does not mean the original developer authorized public redistribution. These candidates remain source-found with license/authorization unresolved unless independent rights evidence is found.

**PC source lineage correction:**

- **Eye of the Beholder II** — the source mirror README points to the original Internet Archive source archive and says the repository contains its unpacked contents. The mirror tree includes AESOP interpreter/runtime, documentation and sound directories. Exact license, C/C++ inventory, completeness and buildability remain to be audited.
- **Forsaken** — the ForsakenX repository is a substantial community port from the original Windows/DirectX 6/MSVC environment to GCC/SDL and cross-platform libraries. The separate ForsakenW fork says it aims to stay closer to the original source. This is now classified as a port/source-lineage record, not a pristine original source archive.

**Existing source record refinement:** DOOM FX's public repository contains a GPL-3.0 license, source and make directories, conversion tools, documentation, binaries and a SNES makefile. Its 65816/Super FX assembly source should not be counted as C/C++.

This tranche added **19 candidates and 21 evidence records**, enriched existing Eye of the Beholder II, Forsaken and DOOM FX records, and did not promote any newly discovered console title into canonical `data/games.csv`. The N64/GBA leak records remain excluded from authorized-source counts.

**Current discovery ledger:** 320 candidate records, 470 evidence records, 31 registered discovery sources. Canonical `data/games.csv` remains at 227 records.

### PC C/C++ source verification — parallel index audit (2026-11-25)

- **Serious Sam Classic (The First Encounter / The Second Encounter)** — Croteam officially released Serious Engine v1.10 on 2016-03-11 under GPL-2.0. The official repository README lists engine, entity logic, game logic, main executable, editors and tools, and documents Visual Studio 2013/2015 builds. This is more than an engine-only SDK: game logic is included. Original game GRO resources are still required for original levels, and some optional features are disabled for copyright reasons. Build instructions are documented but were not independently executed.
- **S.T.A.L.K.E.R.: Call of Pripyat** — the archived X-Ray Engine 1.6.02 source snapshot is C++-oriented and has an original README and custom License.txt. The README explicitly says the project is not sanctioned by GSC Game World. The license describes the code as proprietary GSC source and prohibits commercial use while permitting redistribution under stated conditions. It is source-available under restrictive custom terms, not OSI open source and not an authorized rightsholder release.
- **Eye of the Beholder II** — the public mirror points to an Internet Archive original-source archive; directory inventory shows AESOP interpreter/runtime and related components. The exact source language, license, completeness and reproducible build still need archive-level audit.
- **Forsaken** — classification corrected to community port/source lineage. ForsakenX migrated the original Windows/DirectX 6/MSVC code to GCC/SDL and cross-platform libraries; a separate fork states its aim is to remain closer to original code. Do not count this port as a pristine original source archive.

This PC audit enriched Serious Sam Classic and added one S.T.A.L.K.E.R. candidate. The database distinguishes engine + game logic from engine-only releases and records build instructions separately from a verified successful build.

- **Doom 3: BFG Edition** — official id Software C++ source repository; GPL-3.0 with additional terms and excluded third-party code. The README documents a Visual Studio 2010 solution and DirectX SDK June 2010 requirement. Game data remains under the original EULA; Steam integration, Bink playback and depth-fail stencil shadows are omitted.
- **Amnesia: A Machine for Pigs** — official Frictional Games C++ source under GPL-3.0 with Visual Studio 2010 and CMake project files. The README identifies Autodesk FBX SDK 2012 as an unavailable dependency that prevents compilation; build metadata exists but successful buildability is not established.

**Current discovery ledger:** 321 candidate records, 474 evidence records, 31 registered discovery sources. Canonical `data/games.csv` remains at 227 records.

### Source archive inventory audit — third tranche (2026-11-25)

This tranche inspected repository trees rather than relying only on catalogue descriptions.

**PlayStation findings:**

- **Battle Konchuuden:** recursive GitHub tree contains 19,686 files, including 67 C files, 65 headers, 108 makefiles, 45 object files, 25 libraries, a top-level `MAKE.BAT`, and extensive game-specific model, map, animation, texture and audio data. This is a substantial PS1 development tree. No license or original rights-holder authorization was located; a successful build and complete final-game coverage have not been verified.
- **Chill:** Hidden Palace identifies the September 30, 1997 prototype inside the European retail release at `BAGS/CDFILLER.DAT`. Its `EXECUTE` folder contains the prototype build and `CTI` contains assets needed to generate a CD image. This is a prototype/source snapshot, not proof of complete final-game source.
- **Beatmania:** source attributed to Beatmania 5th Mix was reportedly mistakenly included on the 2000 Beatmania Best Hits disc. The source was not on the 5th Mix disc itself. Its source package and license still need direct inspection.
- **SpongeBob SquarePants: SuperSponge:** recursive repository inventory shows 19,844 files, including 490 C++ files, 111 C files, 542 headers, 20 Visual Studio project files, 6 solution files, numerous makefiles, extensive graphics/audio assets and utility projects. This materially supports the repository's claim of a broad VSS project archive, but does not prove a successful modern build or rights to redistribute all assets. The README's game-title copy/paste error remains noted.
- **Ultimate Mortal Kombat 3:** recursive inventory contains 77 C files and 68 headers, but no build files were identified; the repository explicitly calls it incomplete and not buildable.

**SNES and N64 corrections:**

- **B.O.B.:** recursive tree contains 430 files: 102 assembly files, 4 headers, 164 `.asp`, 38 `.a`, 82 maps, 12 `.sne` and 3 makefiles, with Source/Maps/Sound directories. This is a substantial assembly-heavy source/data tree, not a C/C++ release. RetroReversing describes it as developer-team released, but a primary release announcement and license were not found in this pass.
- **1080 Snowboarding:** detailed Gigaleak 2 notes say the main game tree lacks uncompiled C/header sources and contains precompiled ELF object files. It remains a leaked-source/artifact discovery but must not count toward confirmed C/C++ source totals.
- **Magician (NES):** added from original programmer Chris Shrigley's December 2012 archive. Shrigley identifies himself as designer/programmer and says the archive is educational-use only with commercial use prohibited. The project is 6502 assembly, not C/C++.

### Local source audit utility

Added `cgsdb_discovery/source_audit.py` and tests in `tests/test_source_audit.py`, plus the `cgsdb-audit` CLI entry point. It performs a read-only local tree inventory of file extensions/languages, build metadata, asset/data directories, dependency manifests and unresolved quoted local C/C++ includes. Reports are JSON and output files are written atomically. It deliberately labels buildability and completeness as **not tested / not assessed**; it does not infer licensing, authorization or full-game coverage. Tests were added but have not been executed in this connector-only update.

Example after cloning a candidate repository:

```bash
python -m cgsdb_discovery.source_audit ./candidate-checkout --output ./source-audit.json
# or, after installing the project:
cgsdb-audit ./candidate-checkout --output ./source-audit.json
```

This tranche added **one candidate (Magician) and five evidence records**, enriched five existing candidates, and registered four discovery sources. No canonical game records were added. The 1080, Chill and Beatmania descriptions were narrowed to reflect what the evidence actually establishes.

**Current discovery ledger:** 325 candidate records, 498 evidence records, 37 registered discovery sources. Canonical `data/games.csv` remains at 227 records.

### Source tree static inventory — PS1 / GBA / N64 tranche (2026-11-25)

This pass inspected source files, build scripts and published file-tree inventories. It did **not** download or mirror leaked Nintendo source files. The public `bowsersbigbeanburrito/N` repository contains metadata indexes (directory trees, CSV file inventories and checksums), not the underlying leaked game source archives.

**PS1 — retail-disc archives**

- **Battle Konchuuden:** direct source inspection confirms GNU C for PlayStation R3000. `P00/MAINSYS.C`, `P01/BATTLE.C` and `P08/AKMCRD.C` show system, battle and memory-card game logic. `MAK/P01.MAK` calls Psy-Q `ccpsx`, `psylib` and `psymake`; `MAKE.BAT` invokes `psymake`. The repository tree has 19,686 files: 67 C, 65 headers, 108 .mak, 45 .obj and 25 .lib, plus extensive game assets. README says “probably complete.” Proprietary SDK headers/libraries remain dependencies; no current build or authorization is established.
- **Beatmania APPEND 5th MIX:** KCEJ Wiki identifies the exact location: `cdrom0:\\DUMMY` on Beatmania Best Hits (SLPM-86596), an LZH archive of `C:\\5thMix\\Work.5th`. Its file inventory lists `MAIN/BM.C`, gameplay code under `TAN` (including `GM_GAME.C`, `GM_NOTE.C`, `JUDGE.C`, `SCENE.C`), game/menu code under `LIBBM`, filesystem, memory-card, display, sound, debug tools, headers, makefiles, linker files, objects and libraries. The wiki says Psy-Q SDK can compile it. Some libraries were shared with Konami's Metal Gear Solid production department. Archive extraction and actual build still outstanding; license and permission unknown.
- **Chill:** still only a prototype snapshot identified in the retail-disc padding file; Hidden Palace currently reports its download file missing. The prototype has not been acquired or extracted; it is not promoted to a complete final-game source claim.

**GBA — leaked CVS metadata inventory**

- **Super Mario Advance / marioAGB:** 3,521 files. The `src` tree has 283 C files, 99 headers and 7 assembly files. Separate `sound_data` contains 591 assembly files, 603 objects, 288 AIFF and 501 MIDI files. There are 14 Makefile/map-related build entries including root and subproject makefiles, and seven .map files; no .ld linker script was identified.
- **Wario Land 4 / wario4land_gba_ique:** 6,388 files. The `src` tree has 2,449 C files, 85 headers and 3 assembly files. `sound/src` contains another 1,068 assembly files. There are 1,182 objects, 51 make/build files, one .map and one .elf. The game is divided into many subsystem makefiles (enemy, game, gmap, mini, pause, select, shop, title and tmsc). No .ld linker script was identified.
- These are file-tree counts from metadata indexes, not an extraction of the leaked archives. The source appears game-specific, and sound middleware is separable, but exact SDK/compiler dependencies, localization deltas, completeness and buildability still need local extraction. Both remain unauthorized leak records; do not redistribute source.

**N64 — game-source versus SDK separation**

The metadata index provides useful counts for several additional source trees. Counts below are indexed files, not verified unique final-game source files:

| Game | Files | C | C++ | Headers | Objects | Build files |
|---|---:|---:|---:|---:|---:|---:|
| Animal Crossing / Forest | 37,602 | 9,818 | 0 | 1,934 | 9,757 | 1 .mk |
| Dr. Mario 64 | 6,252 | 138 | 0 | 92 | 1 | 8 .mak |
| F-Zero X | 4,166 | 263 | 0 | 132 | 207 | none identified by suffix |
| Mario Kart 64 | 3,243 | 2,384 | 0 | 151 | 153 | none identified by suffix |
| NBA Courtside | 12,971 | 291 | 62 | 251 | 0 | 13 makefiles |
| NBA Courtside 2 | 12,978 | 291 | 62 | 251 | 1 | 13 makefiles |
| Star Fox 64 | 18,204 | 1,903 | 1,260 | 206 | 3,196 | 2 .mk |
| Wave Race 64 | 8,691 | 869 | 0 | 249 | 91 | none identified by suffix |
| Yoshi's Story | 1,988 | 83 | 0 | 29 | 947 | 11 .mk |
| Super Mario 64 | 3,055 | 479 | 0 | 246 | 67 | none identified by suffix |
| Ocarina of Time | 26,462 | 1,030 | 0 | 1,229 | 16,840 | 2 .mk |
| Majora's Mask | 4,472 | 11 | 0 | 159 | 1,975 | 3 .mk |

Animal Crossing's inventory contains a nested `forest_patch030603.tar` subtree, so file counts may include a duplicate/patch snapshot. Majora's Mask has only 11 C files against 1,975 objects and should be treated as a likely partial source snapshot, not complete source. Ocarina of Time has a much larger source inventory but is still unverified. The `z_ocarina2` Master Quest directory is a source branch/prototype lineage, not a separate original N64 commercial release, so it has not been added as a separate game candidate. The 1080 tree contains 329 files but no C/C++ source: 167 objects, 124 binary files and one header; its `libgdl_u64.a` is precompiled. It is not counted as a confirmed C/C++ source release.

The Gigaleak root's `devkit`, `devsys`, `os20l` and `ostrees` directories are SDK/toolchain material and are kept separate from individual game directories. All Nintendo source-tree candidates remain unauthorized leaks with no redistribution permission or license established.

### Static audit execution status

The source-audit utility's quoted-include regular expressions and path normalization were corrected after reviewing the implementation. However, there is no local checkout of the candidate repositories mounted in this session, and the metadata-only GitHub index is not the original source archive. Therefore the audit CLI and its unit tests have **not** been executed against a real local checkout in this pass. No build was run and no reproducible build result is claimed. The next execution gate is to obtain authorized/local source trees, run the utility and tests, then build only where the original SDK and rights allow.

This tranche adds **three N64 candidates** (Super Mario 64, Ocarina of Time and Majora's Mask), **17 new evidence records**, updates the existing PS1/GBA/N64 assessments, and registers two sources. Canonical `data/games.csv` is unchanged.

### PC C/C++ original-release audit — third tranche (2026-11-25)

This tranche inspected official source repositories, their README/COPYING files, project files and dependency manifests. It enriches existing candidates; no new canonical game rows were added.

| Game | Source inventory | Build/dependency findings | Rights and scope |
|---|---|---|---|
| Quake II | 187 C, 77 headers, 13 assembly, 9 ASM; 371 files | Complete-source claim for v3.19; Visual C++ 6.0 project; Linux build explicitly untested for original release | Official John Carmack README says GPL-2.0; original game data remains under original terms |
| Quake III Arena | 445 C, 129 C++, 337 headers; 1,409 files | 35 build/project files; VC7/Visual C++ 2003; Linux GCC 2.95, G++ 2.95, NASM and X11 headers; Mac project | Official GPL-2.0 release; third-party zlib, RSA MD4, Berkeley, CWI ADPCM and IJG JPEG notices; game data separate |
| Return to Castle Wolfenstein SP | 315 C, 12 C++, 212 headers; 620 files | Visual C++ 2008; legacy Perl `cons`; run `extractfuncs.bat` to generate `g_save.c` | GPL-3.0 with additional terms and excluded third-party code; game data under original EULA |
| Return to Castle Wolfenstein MP | 285 C, 8 C++, 149 headers; 520 files | Visual C++ 2008; legacy `cons` build; latest retail patch/game data required | Separate multiplayer source release; GPL-3.0 with additional terms/exclusions; data separate |
| Penumbra: Overture | 59 C++, 64 headers; 133 files | CMake, Visual Studio and Xcode; requires separate HPL1Engine and OALWrapper repos plus external Newton, AngelScript, FLTK, OpenGL/Cg, Ogg/Vorbis, OpenAL and SDL dependencies | Game code GPL-3.0; HPL1 engine GPL-3.0; OALWrapper has its own permissive notice license; assets/data separate |
| Amnesia: The Dark Descent | 734 C++, 780 headers; 1,631 files | 55 build/project files; CMake and VS2010; HPL2 engine/editor code included; Autodesk FBX SDK 2012 unavailable and explicitly blocks compile | Official GPL-3.0 source; commercial game assets/data remain proprietary |

**Important source completeness distinctions:** Quake II is the clearest full source release in this tranche because its official README explicitly says “complete source code” and names the exact version. Quake III includes engine/game code and major tools but its original release was not extensively tested across platforms. RTCW single-player and multiplayer are distinct source repositories and must be counted as separate code scopes, not one interchangeable source tree. Penumbra's game repository is not self-contained: CMake explicitly references sibling engine/wrapper repositories and a separate dependency directory. Amnesia has broad game and engine/editor code, but its documented FBX SDK blocker prevents claiming a successful build.

The discovery ledger now contains **325 candidates, 506 evidence records and 39 registered sources**; canonical `data/games.csv` remains at 227 records. No builds were executed in this pass.

The source-audit utility was extended in this tranche to extract CMake `find_package` and `target_link_libraries` dependencies, identify linker-script files (`.ld`, `.lds`, `.lnk`, `.rsp`), and record compiler/SDK/toolchain mentions from build files. Unit tests now cover CMake dependencies, linker scripts, compiler detection, quoted include resolution and symlink-safe traversal. **The tests and CLI have not been executed**: no local source checkout was mounted, and the environment could not resolve GitHub for a local clone. The PC/N64/GBA figures in this README are static inventories derived from the repositories' published file trees and build manifests, not results emitted by the local audit CLI.


### 2026-11-25 reproducible build milestone — POSTAL

The first pinned-revision build dossier is available at [docs/builds/POSTAL_REPRODUCIBLE_BUILD.md](docs/builds/POSTAL_REPRODUCIBLE_BUILD.md), with a machine-readable manifest at [data/builds/postal1.json](data/builds/postal1.json). Static inspection identifies the current POSTAL_2015 Linux Makefile path, GCC/G++, SDL2, the VS2017-era Windows project files, and the separate game-data requirement. **No successful build is claimed yet:** the execution environment could not resolve github.com, so checkout stopped before compiler invocation. Build and runtime gates remain open.

# Source Archive Acquisition and Static Audit Queue

**Updated:** 2026-11-25  
**Scope:** local, reproducible examination of already-obtained source-bearing game media and source trees. This document records research leads; it does not authorize downloading, redistribution, or publication of copyrighted game data.

## Operating rules

- Keep disc images, extracted game assets, leaked material, and proprietary SDKs outside this repository.
- Do not commit disc images, extracted source archives, proprietary SDK files, or copyrighted assets.
- Preserve acquisition provenance, original filenames, media serial/revision, archive hashes, extraction tool/version, and timestamps in a local-only manifest.
- A public listing or a file embedded on retail media is not a license. Keep authorization, redistribution, completeness, and buildability as separate fields.
- Do not execute unknown build scripts. Inspect them first; use an isolated, offline build environment.
- Never label a source tree complete or buildable from extension counts alone.

## Priority A — PlayStation retail-media source

### Battle Konchuuden (SLPS-01779)

- A public source repository exists: <https://github.com/RetailGameSourceCode/BattleKonchuuden>.
- The preservation catalogue describes the code as source found on the retail CD-ROM: <https://github.com/RetroReversing/retroReversing/blob/master/pages/SourceCode/RetailConsoleSourceCode.md>.
- Prior inventory notes recorded 67 C files, 65 headers, and 108 makefiles, with Psy-Q tool references including `ccpsx` and `psymake`. Treat these counts as provisional until the exact source snapshot is re-audited.
- Next: inspect the public repository tree and compare it with a locally held, independently dumped disc. Record whether the repository is a full mirror, partial extraction, or modified derivative. Do not overwrite the public snapshot with disc contents.
- Audit: source files, makefiles, include paths, compiler/linker commands, library references, asset/data directories, and unresolved includes. Build only if the original licensed toolchain is available.

### Beatmania APPEND 5th MIX source found on Beatmania Best Hits

- The source lead is the retail disc **Beatmania Best Hits**, not the separately named 5th MIX disc. RetroReversing links the PSXDEV discussion: <https://www.psxdev.net/forum/viewtopic.php?f=41&t=470>.
- The research notes identify an LZH archive under a dummy-data path, with an internal work path referencing `C:\5thMix\Work.5th`. These path strings are leads, not proof of archive completeness.
- Relevant disc identifiers: Beatmania Best Hits is listed as SLPM-86596; the source project is identified as Beatmania APPEND 5th MIX.
- Next: with a lawfully held disc image, inspect the filesystem and dummy-data region, extract the LZH into a private working directory, hash the original archive and extracted files, and run the source audit. Preserve the original archive unchanged.
- Record whether the archive contains game source, generated files, SDK headers/libraries, tools, assets, or a mixture.

### Chill (Europe)

- A retail-disc source snapshot is listed as an earlier Silicon Dreams build: <https://www.retroreversing.com/sourcecode> (retail console source index).
- The index links a PAL disc image entry and describes source files among the disc contents. This is a research lead, not an independently confirmed complete source release.
- Next: inspect a lawfully held image's filesystem and CDFILLER/dummy-data areas; determine whether C files are actual text source or merely filenames/metadata. Hash all extracted files and audit the resulting tree.

## Priority B — Game Boy Advance source trees

Previously recorded candidate inventories:
- Super Mario Advance: 283 C files.
- Wario Land 4: 2,449 C files.
- No `.ld` linker scripts were observed in the prior sweep.

Re-audit each tree and classify:
1. Game-specific C/C++ and assembly.
2. Nintendo SDK headers, libraries, examples, and startup code.
3. Shared middleware and third-party code.
4. Localization, build-generation, asset-conversion, and developer tools.
5. Generated/decompiled output and duplicate variants.

Inspect `.mak`, makefiles, response files, linker scripts, startup assembly, ROM header setup, compiler version flags, and library references. A missing `.ld` file is not conclusive: GBA projects may use proprietary compiler/linker command files or makefile-embedded linker options. Report exact evidence.

## Priority C — Nintendo 64 source trees

Separate game-specific translation units from:
- Nintendo SDK / libultra and sample code;
- audio, graphics, and other middleware;
- localization and text conversion utilities;
- build tools, asset pipelines, and generated files.

Capture linker scripts, makefiles, compiler flags, target memory maps, microcode references, and unresolved external symbols. Do not count SDK-only trees as game source.

The broad retail-source index records N64 candidates including 1080 Snowboarding, Animal Crossing / Animal Forest, Dr. Mario 64, F-Zero X, Mario Kart 64, NBA Courtside 1 & 2, Star Fox 64, Yoshi's Story, Wave Race 64, and Super Mario 64. These are mixed-provenance research leads, not all authorized releases; leaked material remains explicitly classified as leaked/unauthorized.

## Priority D — PC C/C++ projects

For each candidate, distinguish the actual shipped game version from prototypes, engine-only releases, ports, source ports, and reverse-engineered recreations. Capture compiler/project files, third-party dependencies, proprietary SDKs, platform-specific code, asset availability, and build instructions. Keep leaked/unauthorized code separate from authorized source releases.

## Audit command

Run the repository's static inventory tool against each extracted source tree:

```bash
python -m cgsdb_discovery.source_audit /path/to/private/source-tree \
  --output /path/to/private/reports/<candidate>-source-audit.json
```

The tool reports language counts, build files, dependency manifests, linker files, toolchain mentions, asset-directory hints, and unresolved local includes. It intentionally leaves buildability and completeness as `not-tested` / `not-assessed`.

## Required per-candidate evidence record

Record at minimum:

- game, platform, region, disc/product serial, revision, and source snapshot identity;
- acquisition source and acquisition date;
- original image/archive SHA-256 (plus known Redump hashes where applicable);
- extracted archive path/name, format, extraction tool and version;
- extracted file count, total bytes, and source/build-system counts;
- game-code versus SDK/middleware/tools classification;
- missing assets, generated files, unresolved includes, and external dependencies;
- source completeness assessment with rationale;
- authorization, exact license, access, and redistribution status;
- build attempt command, toolchain version, exit status, and resulting artifact hash (or explicit reason no build was attempted).

## Completion gates

1. **Acquired:** original image/archive identity and hashes recorded.
2. **Extracted:** extraction reproducible; original archive preserved.
3. **Inventoried:** static audit JSON generated and reviewed.
4. **Classified:** game code separated from SDK, middleware, tools, and generated content.
5. **Dependency-mapped:** required compiler, linker, libraries, and assets identified.
6. **Build-tested:** isolated build attempted only where permitted and technically possible.
7. **Provenance-reviewed:** authorization/license and redistribution status independently assessed.

No gate should be inferred from a prior file count or a third-party index entry.

# PC C/C++ Source Acquisition and Dependency Analysis

**Updated:** 2026-11-25  
**Scope:** PC commercial games with original source releases, source-derived ports, archival source snapshots, and reverse-engineered reconstructions. This is a research and buildability ledger, not a redistribution grant.

## Classification rules

Keep these categories separate:

1. **Original authorized source release:** source code published or authorized by the original developer/rightsholder.
2. **Authorized but restricted source release:** original source is available under terms such as non-commercial-only or educational-only.
3. **Engine-only release:** engine and/or game logic is released, but game data, assets, tools, or proprietary libraries are excluded.
4. **Source port:** an adaptation of released source to modern platforms; not necessarily a pristine copy of the original source.
5. **Reverse-engineered reconstruction/decompilation:** source recreated from binaries, symbols, disassembly, or behavior; not original source code.
6. **Archival recovery:** a recovered source archive with unclear or unverified authorization.
7. **Leak:** unauthorized release; record as provenance evidence only and never promote to an authorized/open-source record.

A GitHub repository's public visibility, a permissive-looking README, or an OSI license badge does not automatically cover original game data or every third-party component.

## Priority 1 — original authorized source releases

### Quake (1996) — id Software

- Official repository: https://github.com/id-Software/Quake
- Release scope: README calls the source complete for WinQuake, GLQuake, QuakeWorld, and GLQuakeWorld.
- License: GPL. John Carmack's release README explicitly allows commercial exploitation if GPL conditions are met.
- Build evidence: tested with Visual C++ 6.0; MASM required for assembly files. A C-only build can be selected by changing a define, with a performance penalty for software rendering. The original DOS build is described as probably buildable but was not tested by the release authors.
- Data: original Quake data files remain under their original copyright/license; do not redistribute them based on the source release.
- Audit next: inventory WinQuake/, QW/, qw-qc/, assembly, gas2masm, makefiles/projects, and exact license text. Record whether QuakeC scripts and tools are included separately from the engine.
- Status: original source release confirmed; reproducible build not tested in this project.

### Quake II (1997) — id Software

- Official repository: https://github.com/id-Software/Quake-2
- The inherited database record already contains a primary README/tree audit: the release calls v3.19 source complete, says Visual C++ 6.0 can build it, and identifies Linux makefiles as not release-tested.
- Source is GPL-2.0; original game data remains proprietary and separately licensed.
- Audit next: refresh the exact repository branch/tree and count, inspect Visual Studio DSP/DSW/MAK and Unix makefiles, check platform-specific assembly, and test a clean build in a pinned legacy toolchain container/VM.
- Status: strong source-release evidence; build not independently tested here.

### Quake III Arena (1999) — id Software

- Official repository: https://github.com/id-Software/Quake-III-Arena
- Broad source release: game/rendering code, OS layer, bot library, LCC, Q3ASM, Q3Map, Q3Radiant and related tools.
- License: GPL-2.0 for covered code, with separate third-party notices/licenses. The original game data remains proprietary.
- Prior tree audit recorded 445 C files, 129 C++ files, 337 headers and 35 build/project files.
- Build notes in the release README: Visual C++ 2003/VC7 on Windows; GCC/G++ 2.95, NASM and X11 extension headers on Linux; Mac project included. Release authors say platform builds were checked but not extensively tested.
- Audit next: identify every third-party subtree and its license; build engine/game separately from tools; do not assume all files inherit GPL-2.0.

### Duke Nukem 3D (1996) — 3D Realms / Apogee

- Official historical release: source archive duke3dsource.zip, version 1.5 / Atomic Edition, released 2003-04-01. A preservation mirror and archive comparison are documented at https://frameadvance.net/sources/3drealms-duke3d-source/ and https://github.com/commercial-game-sources/duke_nukem_3d.
- Game code: GPL-2.0-or-later according to source headers and the included GNU license.
- Build notes: Open Watcom 1.0 or Watcom 11.0c, DOS 32-bit target. The code was originally written for Watcom 10.0 and updated for the freely available compiler.
- Important component boundary: the archive also includes Build Engine material and audio-library material. The Build Engine source has a separate license in its own source archive; the historical preservation analysis notes a non-commercial restriction in Ken Silverman's separate Build source license. Do not infer that the entire bundled archive is uniformly GPL merely because the Duke game source is GPL.
- Data: original game data remains copyrighted and is not covered by the code release.
- Audit next: compare the canonical archive hash and file tree; inspect GNU.TXT, Build Engine license, Jim Dose audio-library notices, object files and testdata/*.CON; record per-component licensing.

### Shadow Warrior (1997) — 3D Realms / Apogee

- Rightsholder announcement: https://www.frag-net.com/past/www.3drealms.com/news/2005/04/shadow_warrior_12.html
- Official release: version 1.2 CD source, 2005-04-01; 3D Realms states it is complete source and GPL-licensed.
- Build notes: Open Watcom 1.3 for Windows, DOS 32-bit target. The README warns the IDE is the known build path; the included extras makefile was not tested by the release author.
- Data: game data files remain copyrighted and cannot be redistributed under the source release.
- Component review: source package includes audiolib, kenbuild, source, and extras; inspect Ken Silverman and Jim Dose components and their separate notices rather than assuming all bundled material has identical licensing.
- Status: authorized original source release confirmed; build not independently tested.

### Abuse (1995) — Crack dot Com

- Original source was released into the public domain in 1997. The registered-level data was not released, and sound effects/music by Bobby Prince were excluded or separately rights-restricted.
- Source/community project: https://github.com/Xenoveritas/abuse
- The Xenoveritas repository is a later SDL2/CMake port, not the pristine original release. Its README identifies SDL2 >= 2.0.3 and SDL_mixer >= 2.0.0 as requirements and explains that sound/music and some content are omitted because distribution rights were unclear.
- Build next: inspect the original source archive separately from the SDL2 port; pin CMake, SDL2 and SDL_mixer versions; verify whether the original public-domain grant covers each file and keep third-party ports/assets separately licensed.
- Status: original source public-domain claim supported by historical release reporting; current port has its own dependency/license surface.

### Little Big Adventure 2 (1997) — Adeline Software / 2.21

- Official source repository: https://github.com/2point21/lba2-classic
- The historic source is an engine source release under GPL-2.0-only; it contains assembly and excludes proprietary libraries. Art, models, textures and audio remain proprietary and are not redistributable.
- The modern community project https://github.com/LBALab/lba2-classic-community is a maintained port; it is not the original historical tree.
- Build next: separate historic LIB386 and SOURCES from the maintained port, inspect excluded libraries and the current community project's exact build dependencies, and verify game-data directory/version requirements.
- Status: official engine source release confirmed; not a complete redistributable game.

### Serious Sam Classic (2001) — Croteam

- Official source: https://github.com/Croteam-official/Serious-Engine
- Croteam released Serious Engine v1.10 under GPL-2.0. Repository includes engine, EntitiesMP and GameMP logic, SeriousSam, editor/modeler/tools, dedicated server and utilities.
- Build notes: Visual Studio 2013 or 2015; DirectX 8 SDK is optional for DirectX support. MP3 playback requires amp11lib.dll from an older commercial game distribution. Original .GRO game resources are needed for original levels.
- License exceptions: zlib, libogg/libvorbis and NewTek LightWave SDK are separately licensed; some features are disabled due to copyright restrictions.
- Audit next: parse .sln and .vcxproj/.vcproj, enumerate prebuilt DLLs and optional SDK dependencies, map every third-party license, and test the documented VS toolchain in an isolated Windows environment.
- Status: official engine/game-logic source release confirmed; complete commercial data not included.

## Priority 2 — authorized but commercially restricted source

### FreeSpace 2 (1999) — Volition

- Source project: https://github.com/scp-fs2open/fs2open.github.com
- Volition released source in 2002; contemporary reporting confirms public release in May 2006. The Volition source license is not an OSI open-source license: it prohibits selling or otherwise commercially exploiting the source or derivative works.
- Source-license text: https://wiki.hard-light.net/index.php/FreeSpace_2_EULA
- The modern FreeSpace Source Code Project has evolved far beyond the original release; it must be recorded as a maintained source-port lineage, not a byte-identical original snapshot.
- Runtime data: a legitimate FreeSpace 2 installation is required for the game assets; the source release did not place all original game content under the source license.
- Dependency audit next: inspect current CMake/preset files, vendored libraries, OpenGL/Vulkan, SDL, audio/video, wxWidgets/Qt editor dependencies, platform packages and submodules from the actual checked-out revision. Do not freeze a package list from an old wiki.
- Database status: authorized-restricted-or-unknown, redistribution_status=restricted; commercial use is prohibited by the source license.

### Jagged Alliance 2 (1999) — Sir-Tech Canada / Strategy First

- Source archive: https://github.com/dariusk/ja2 (historical copy of source provided on the JA2: Wildfire CD, with build-enabling files).
- The included Strategy First Source Code License Agreement permits non-commercial purposes only, including education, research, public demos and experimentation. Commercial use/distribution and commercial derivatives are prohibited. Derivatives distributed non-commercially must include the license and change notices; the agreement also grants Strategy First rights in distributed modifications.
- Build notes: Microsoft Visual C++ 6.0 workspace; build ja2/Build/JA2.dsw; the included Standard Gaming Platform directory is required as include/library path and runtime bootstrap.
- The README calls the source complete as supplied on the Wildfire CD, but the public repository has only one commit and includes extra build-enabling files. Treat the completeness statement as a source-author claim pending comparison with the original Wildfire CD.
- Runtime data: original game data is governed by the commercial game's EULA and is not automatically licensed by the source agreement.
- Audit next: inspect SFI Source Code license agreement.txt, inventory ja2/Build versus Standard Gaming Platform, identify missing prebuilt libraries/DLLs, and build only for non-commercial research after preserving exact license text.

## Priority 3 — reverse-engineered source, source ports and reconstructions

These are valuable technical records but are not original source releases. Do not place them in the same provenance class as developer-published source.

### Carmageddon (1997) — Dethrace

- Project: https://github.com/dethrace-labs/dethrace
- Method: reverse engineering/reconstruction from the shipped executable, aided by Watcom symbols found on the Splat Pack CD. Not original source.
- Current repository license file is GPL-3.0; do not rely on older mirrors/forks that show different terms.
- Build: CMake, SDL2, Git submodules; git submodule update --init --recursive; cmake ..; then build. README lists libsdl2-dev and cmake for Debian/Ubuntu.
- Data: project ships no game content; requires a legitimate original game data directory or supported freeware demo. GOG CD-audio convention can use user-supplied OGG tracks.
- Status: strong active reconstruction candidate; original game assets remain separate.

### Diablo (1996) — Devilution / DevilutionX

- Project family: https://github.com/diasurgical/devilution and https://github.com/diasurgical/devilutionX
- Method: reverse-engineered reconstruction guided by symbol data and debug information; not an original Blizzard source release.
- Do not infer a license for the original game or assets from the existence of the reconstruction. Inspect the exact repository license and third-party notices separately.
- Data: user-supplied legitimate Diablo installation is required.
- Status: reconstruction; license and completeness must be evaluated per repository/revision.

### Blood (1997) — NBlood / Blood-RE

- Projects: https://github.com/NBlood/NBlood and https://github.com/NBlood/Blood-RE
- NBlood is a reverse-engineered port based on EDuke32 technology; Blood-RE is explicitly a source reconstruction. Neither is the original Monolith source release.
- Data: NBlood README requires original Blood 1.21 files such as BLOOD.RFF, TILES*.ART, SOUNDS.RFF, SURFACE.DAT and related content.
- Status: source-derived/reverse-engineered; inspect exact licensing in the repository/package before recording reuse rights.

### Forsaken (1998) — ForsakenX lineage

- Project: https://github.com/ForsakenW/forsaken
- The README says it forks the first ForsakenX commit. It explicitly distinguishes the original Windows/DirectX 6/MSVC project from ForsakenX's substantial GCC/SDL cross-platform port.
- Do not call the modern tree a pristine original source snapshot. The fork aims to keep closer to original source while modernizing Windows builds.
- Status: source-lineage/port candidate; license and rightsholder authorization require direct inspection.

## Dependency-analysis template

For every source candidate, capture:

| Layer | Required evidence |
|---|---|
| Compiler | Compiler family, exact version, target architecture, language mode, ABI assumptions |
| Assembler | MASM/NASM/Watcom assembler, syntax, object format, generated assembly |
| Build system | IDE/workspace, make, CMake, Autotools, custom scripts; exact entrypoint |
| Platform SDK | Win32, DirectX, X11, DOS extender, console SDK, libc/runtime |
| Third-party libraries | Name, version, static/dynamic linkage, source/binary presence, license |
| Proprietary components | Excluded SDKs, audio/video codecs, fonts, middleware, editor plug-ins |
| Game data | Required archive names, expected version/region, hashes where lawful, separate data license |
| Generated assets | Resource compilers, shader compilers, map/texture conversion tools |
| Runtime | DLL/shared-library requirements, config files, registry/environment assumptions |
| Reproducibility | Container/VM image, exact commands, environment variables, build log, artifact hash |

### Buildability levels

- **B0 — source sighted:** source listing or archive exists.
- **B1 — statically inventoried:** full file tree and build metadata inspected.
- **B2 — dependencies mapped:** required compiler, SDK, libraries and assets identified.
- **B3 — compiles:** clean build succeeds in a pinned environment.
- **B4 — launches:** binary starts with legally obtained required data.
- **B5 — functionally verified:** representative gameplay, input, audio, save/load and platform-specific behavior tested.

Do not mark a title B3 or above from README claims alone. Record the exact source commit/archive hash and toolchain used.

## Next execution order

1. **Duke Nukem 3D:** component-level license review, especially Build Engine and audio code; hash and compare the canonical 2003 archive.
2. **Shadow Warrior:** inspect the official 1.2 source tree, audiolib, kenbuild, and Open Watcom build instructions.
3. **Quake / Quake II:** inventory the original release trees and build with isolated legacy compilers.
4. **Jagged Alliance 2:** verify Wildfire CD provenance and preserve the non-commercial license; inspect SGP dependency.
5. **FreeSpace 2:** map current maintained project dependencies from its active build files, retaining non-commercial restriction.
6. **Abuse:** compare original public-domain source with the SDL2/CMake port and isolate disputed sound/data.
7. **Serious Sam / Marathon / LBA2:** build dependency maps and game-data separation checks.
8. **Dethrace / Devilution / NBlood / Forsaken:** maintain a separate reconstruction/port track.

## Non-goals

- No downloading or committing commercial game data, ROMs, disc images, proprietary SDKs or unauthorized source dumps.
- No treating abandonware status, public GitHub access, or a successful compile as a redistribution license.
- No claiming reproducibility until a clean build log and artifact hash are retained.

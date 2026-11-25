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

### DOOM (1993) — id Software

- Official source: https://github.com/id-Software/DOOM
- Release README is dated 1997-12-23 and says the released tree only compiles/runs on Linux; DOS source was not released because it depended on a copyrighted sound library, and the Windows port was not included.
- License nuance requiring conservative treatment: the repository's LICENSE.TXT identifies GPL-2.0, while README.TXT describes the source as released for "non-profit use." Record this wording conflict and inspect the full release package/legal history before assigning unrestricted commercial-use status. Do not silently choose the more permissive interpretation.
- Data: the source requires real DOOM game data; original assets are not included or relicensed by the code release.
- Audit next: inventory linuxdoom-1.10, sersrc, sndserv and ipx separately; inspect Linux makefiles, sound-server dependencies and platform assumptions; compare source LICENSE.TXT and README.TXT in the same release archive.
- Status: original source release confirmed; source scope is Linux-only and the release README conflicts with the GPL file on permitted use.

### Rise of the Triad (1994) — Apogee / 3D Realms

- Historical official release: https://github.com/dos-games/vanilla-rott (source archive mirror with the original release README).
- Release: v1.3 CD source, 2002-12-20. The README states that the game itself remains commercial software and is not released with the source.
- Build: Watcom C 10.0b; Borland Turbo Assembler (TASM) for a full assembly rebuild; precompiled object files are included for several assembly modules. Build command is wmake all; audio library has a separate wmake.bat build.
- License: package includes gpl.txt; verify the exact GPL text and every bundled audio/assembler/object component independently before promoting broad reuse rights.
- Audit next: compare original archive to mirror; classify rott, rottcom, rtsmaker, audiolib, and precompiled .obj files; determine which parts can be rebuilt without TASM and which depend on binary-only objects.
- Status: official source-release evidence; legacy compiler/toolchain and separate game data are significant barriers.

### Descent (1995) — Parallax Software

- Source archive mirror: https://github.com/videogamepreservation/descent
- The source README includes almost all Descent 1 v1.5 source but explicitly says low-level sound and modem code were removed because Parallax did not own that code.
- License correction: although some 1998 announcement coverage used "public domain" language, the source README itself grants a perpetual license only for non-commercial, royalty/revenue-free purposes and expressly forbids revenue-bearing use. Treat it as a custom non-commercial license, not public domain or OSI open source.
- Build: Watcom C/C++ 10.6, Microsoft Macro Assembler 6.11, GNU-compatible make; run maked1.bat. The README says the resulting executable runs without sound and serial-port functionality. The editor requires editdata.zip and a special build define.
- Data: original commercial game data is required and remains separately copyrighted.
- Status: near-complete original source snapshot with known code removals and non-commercial-only rights.

### Descent II (1996) — Parallax / Outrage / Volition

- Source archive mirror: https://github.com/videogamepreservation/descent2
- The included message from Matt Toschlog and Mike Kulas identifies this as Descent II v1.2 and says almost all source is included, but low-level sound, modem and movie code were removed.
- License: custom non-commercial, royalty/revenue-free license; not public domain or OSI open source.
- Critical buildability issue: the original README explicitly states the packaged source does not compile because files were removed to release it.
- Build toolchain named by the archive: Watcom C/C++ 9.5, Microsoft Macro Assembler 6.1x, Opus Make 6.01. Reconstructing a build requires identifying the missing source/modules and any platform libraries without pretending the published snapshot is complete.
- Data: original game data is not included and remains separately licensed.
- Status: partial original source snapshot; known non-buildable as packaged.

### Return to Castle Wolfenstein (2001) — Gray Matter / id Software

- Separate official repositories: https://github.com/id-Software/RTCW-SP and https://github.com/id-Software/RTCW-MP
- Both single-player and multiplayer source releases were published in August 2010 under GPL-3.0 with additional terms and expressly excluded third-party code. Do not assume every file in either tree is covered by GPL-3.0.
- Build: Visual C++ 2008 solution (Express-compatible). Linux uses the legacy Perl-based cons script. Single-player additionally runs src/extractfuncs/extractfuncs.bat to generate src/game/g_save.c.
- Data: neither source release includes game data; a patched retail installation is required. The original EULA continues to govern the data.
- Audit next: keep SP and MP as separate source components; compare COPYING.txt and README.txt, enumerate excluded code (zlib, RSA MD4, JPEG and other notices), and verify the generated-file step.
- Status: authorized original source release; game data and excluded third-party components remain separate.

### Wolfenstein: Enemy Territory (2003) — Splash Damage / id Software

- Official repository: https://github.com/id-Software/Enemy-Territory
- Source released 2010-08-12 under GPL-3.0 with additional terms and an explicit excluded-code list. The original game was made available free of charge, but the source release still excludes game data and leaves it under the original EULA.
- Build: Visual C++ 2008 Express-compatible solution on Windows; SCons from the src/ directory on GNU/Linux x86.
- Audit next: inventory src/, identify excluded-code sections in README.txt and COPYING.txt, inspect SCons scripts and all bundled third-party notices, and test a clean build independently.
- Status: official source release; separate game data is freely obtainable from the original distribution channel but is not automatically GPL-licensed.

### POSTAL (1997) — Running With Scissors

- Official rightsholder repository: https://github.com/RWS-Studios/POSTAL-SourceCode
- Running With Scissors announced the source release on 2016-12-29 under GPL-2.0. The official GitHub organization describes the repository as the original POSTAL source code.
- Current tree inspection: 1,419 tracked files, including 210 .cpp, 241 .c, 627 .h, 12 .cc, 15 .vcproj, 9 .vcxproj, one .sln and one .mak. It contains the RSPiX engine/library source as well as game code and multiple product configurations.
- Historical build notes in Postal Overview.txt (updated 2000-12-22): Windows used Visual C++ 6.0 and Postal.dsw; Mac used Metrowerks CodeWarrior (exact version unknown). Product builds are selected by TARGET, LOCALE and SPAWN preprocessor definitions. The workspace contains RSPiX projects (BLiT, BLiT3D, Blue Audio, Blue, Blue Video, Cyan, Green, Orange, WishPiX), Postal Common, and product-specific targets.
- Dependency constraints: RSPiX includes platform-specific Blue and Cyan layers for Windows and Mac; porting to a new platform requires rewriting the Blue layer and potentially parts of Cyan. SmartHeap by Microquill was used on Windows and Mac but can be disabled with NOSHMALLOC. The source tree also contains binary libraries and dynamic libraries; identify which are proprietary, redistributable, obsolete or replaceable before attempting a clean build.
- The historical overview says only Postal and Special Delivery were compiled for Mac; current project settings target Japan Add On, Japan Super Postal, Postal Plus and Postal Plus MP. It does not claim all earlier editions were rebuilt from the current tree.
- Data: the source release licenses code under GPL-2.0; do not infer that game content, music, video, fonts or any bundled third-party files are also GPL-covered.
- Status: excellent official C/C++ source candidate with substantial engine source and multiple build targets; old toolchain and SmartHeap/binary-library dependencies need mapping.

## Priority 4 — archival source snapshots with unresolved rights

These records can be valuable for historical research, but no source redistribution permission should be inferred from public access. Keep the source archive and any copyrighted demo/game data outside this repository.

### Blood & Magic (1996) — Tachyon Studios / Interplay

- Public archive lead: https://github.com/mhjlam/BAM
- Repository inspection found a demo distribution tree with CODE/SRC and CODE/TIGRE source directories alongside BAM.EXE, DOS4GW.EXE, installer binaries, map/data files, sound banks, Smacker videos, and other demo content. This is not evidence of a rightsholder-authorized source release.
- Static tree inventory: 1,311 files; 131 .cpp, 138 .hpp, 59 .h, 4 .asm, 15 .mak and 7 .lib files, plus extensive animation, audio, font, palette, video, executable and game-data files. Treat counts as the currently inspected Git tree, not a complete commercial game's source count.
- The README identifies the archive as the Blood & Magic interactive demo and asserts copyright 1996 Tachyon Studios; it also identifies Smacker video technology as third-party technology.
- Build evidence from CODE/SRC/BAM.MAK and related makefiles: Watcom 386 compiler/linker/assembler tools (wcl386, wlink, wasm); libraries include tigre.lib, sosdw1cr, sosmw1cr, netnowr.lib, cpfr32.lib and smack.lib. The makefile assumes a hard-coded C:\BAM\TIGRE path.
- CODE/TIGRE includes Greenleaf Comm++ code headers marked copyright 1989–1995 Greenleaf Software, plus proprietary/binary library dependencies. Additional HMI, networking, DOS extender and Smacker components require independent rights/dependency review.
- Rights: README contains standard all-rights-reserved copyright statements and no source-code license grant was identified in the inspected repository. Classify as archival recovery / authorization unresolved, not open source; do not redistribute or commercially reuse the code or assets based on the public repository.
- Next: locate the original demo media/announcement and compare its source directory to this public tree; inspect per-file headers, binary library provenance, and whether the source was intentionally included in the distributed demo. Do not execute or build the archive until it has been safely isolated and licensing is clarified.

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

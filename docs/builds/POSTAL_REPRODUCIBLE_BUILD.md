# POSTAL reproducible build record

**Status:** source and build-system inspection complete; clean build not yet executed  
**Target:** Linux x86-64, non-Steam build first  
**Upstream:** https://github.com/RWS-Studios/POSTAL-SourceCode  
**Inspected upstream revision:** `adb5a30c10dcdfe7758883938f706cb9b53cf496` (main, 2025-05-26)  
**License:** GPL-2.0 for covered source; game data and third-party components must be evaluated separately

## 1. Important scope correction

This repository is not a pristine source snapshot of the exact 1997 retail executable. `CompileOptions.h` explicitly says the current branch cannot rebuild the original POSTAL or Special Delivery exactly: it branched from the original source and accumulated later changes. Its supported targets include `POSTAL_2015`, Japan Add On, Super Postal and Postal Plus. The upstream Linux makefile hard-codes `TARGET=POSTAL_2015` and `LOCALE=US`.

Therefore, the first reproducible artifact is the **POSTAL 2015 source branch's Linux x86-64 executable**, not a bit-identical 1997 build.

## 2. Build-system inventory

| Item | Inspected value | Evidence |
|---|---|---|
| Primary Linux build | GNU Make, root `makefile` | upstream blob `8cddcf6f92d02ad0ecb9ae858f73b18e786c4c01` |
| Linux build helper | `makeit.sh` | upstream blob `40641a8c42e759526c5a673bdf1cc829a68cc0b3` |
| Default architecture | Linux x86-64 | makefile target selection |
| Default output | `./bin/postal1-x86_64` | `CLIENTEXE` |
| Compiler | `gcc` / `g++` | makefile |
| Multimedia | SDL2 | makefile links `-lSDL2` for x86-64 |
| Bundled SDL headers | SDL 2.0.5 | `SDL2/include/SDL_version.h` |
| 32-bit SDL runtime | `SDL2/libs/linux-x86/libSDL2-2.0.so.0` | repository tree |
| Steam integration | optional | enabled only with `WITH_STEAMWORKS=1` |
| Product defines | `TARGET=POSTAL_2015`, `LOCALE=US` | makefile |
| Optional Python binding | SWIG + Python 2 tooling | separate `swig` target; not required for game executable |

The Windows solution `Postal.sln` is a Visual Studio 2017-era solution (Visual Studio version 15). Project files declare Windows SDK 8.1 and toolsets v141, v141_xp and v120_xp in different configurations. The main Postal Plus project also retains older configurations and legacy project imports. This is a separate Windows validation track; do not equate the historical Visual C++ 6.0 note in `Postal Overview.txt` with the current solution's actual toolset.

## 3. Linux x86-64 dependency baseline

### Required / strongly indicated by the upstream makefile

- GNU Make
- GCC and G++
- SDL2 development headers and link library for the host architecture (`libsdl2-dev` on Debian-family systems)
- Standard C/C++ runtime and Linux system development environment

The upstream x86-64 makefile selects `-lSDL2`, so it expects a host-provided SDL2 development package. The repository's bundled Linux SDL2 shared object is under `SDL2/libs/linux-x86` and is for the 32-bit path; do not assume it satisfies x86-64 linking.

### Optional

- Steamworks SDK/runtime only when `WITH_STEAMWORKS=1`; omit for the first baseline build.
- SWIG and Python 2 development/configuration tools only for the optional `swig` / `_RSPiX.so` binding target.
- 32-bit multilib compiler/runtime packages only for the `linux_x86=1` target.

### Not yet confirmed

The exact minimum GCC/G++ version, SDL2 ABI compatibility range, transitive runtime libraries, and any distribution-specific packages must be established by a real clean build and runtime inspection. The makefile suppresses compiler warnings with `-w`; the first diagnostic pass should override this in a local test invocation or patch without changing the canonical source.

## 4. Initial Linux build procedure

Run from a clean checkout of the exact upstream revision:

```bash
git clone https://github.com/RWS-Studios/POSTAL-SourceCode.git
cd POSTAL-SourceCode
git checkout adb5a30c10dcdfe7758883938f706cb9b53cf496

git rev-parse HEAD
sha256sum makefile makeit.sh Postal.sln LICENSE

# Confirm host tools and SDL2 development package.
make --version
gcc --version
g++ --version
pkg-config --modversion sdl2
pkg-config --cflags --libs sdl2

# Inspect the generated commands without compiling.
make -n -j2

# Clean release build; capture the complete log.
set -o pipefail
make clean
make -j"$(nproc)" 2>&1 | tee postal-build-linux-x86_64.log

# Inspect the output and dynamic dependencies.
file ./bin/postal1-x86_64
ldd ./bin/postal1-x86_64
```

Do not call the build successful unless the executable exists, is the expected architecture, and the build exits with status zero. Record the exact distro/container image, kernel, compiler, Make, SDL2 version, command, exit code and output hashes.

The upstream helper `makeit.sh` uses `make -e` and environment overrides to choose output directories. Prefer the direct make invocation above for the first controlled baseline; validate helper behavior separately.

## 5. Runtime data and launch constraints

The source tree is not a complete runnable game distribution. The historical source overview describes the game's SAK archive format and explains that the game searches configured paths for SAK files or individual unpacked assets via `NoSakDir`. The source repository contains configuration examples and compiled-in resources, but does not establish that the retail game data is included.

Use a lawfully obtained compatible POSTAL data installation. Do not copy proprietary assets into this research repository. Record the data edition/version and a local-only manifest of filenames and hashes. Do not publish the asset files themselves.

Runtime validation must record:

1. SDL2 dynamic library resolution.
2. Required game-data paths and SAK availability.
3. Configuration file selected and path values.
4. Successful startup to the title/menu screen.
5. New-game/level load, input, graphics and audio smoke tests.
6. Clean shutdown and logs.
7. Whether the tested data version matches the `POSTAL_2015` code target.

The committed `postal_plus.ini` and `DefaultPostal.ini` contain legacy Windows-oriented video/audio settings. They must not be assumed to be a valid Linux runtime configuration without checking the platform-specific code and actual launch behavior.

## 6. Licensing and third-party dependency gates

- The official rightsholder announced the source release under GPL-2 on 2016-12-28. The repository contains a GPL-2 license file and source headers with GPL notices.
- The GPL applies to covered source; it does not automatically relicense game data, soundtrack, videos, fonts, Steamworks SDK files or other third-party material.
- The first build must disable Steamworks integration. A Steam-enabled build is a distinct configuration with a separate SDK/runtime and redistribution review.
- The source overview identifies SmartHeap as a historical commercial allocator/debugging dependency and documents `NOSHMALLOC` as the switch to disable it on platforms without SmartHeap. Confirm whether any current Linux build path still references it before declaring it eliminated.
- The Windows project files contain legacy DirectX/WinG/HeapAgent include paths in some configurations. Resolve only the dependencies actually selected by the chosen configuration.

## 7. Independent downstream packaging evidence

Debian's `postal1` source package is versioned `2015.git20250526+ds-2` and lists `debhelper-compat (= 13)`, CMake and `libsdl2-dev` as build dependencies. Debian identifies the package as the POSTAL 1 port and places it in `contrib`; its source page links back to the official upstream repository.

This is useful independent packaging evidence, but it is **not** proof that this exact upstream Makefile build was run in this environment, nor proof of bit-for-bit reproducibility. Debian packaging metadata must be inspected before treating CMake as an upstream dependency: the upstream tree inspected here exposes a Makefile and no root CMakeLists.txt.

References:
- https://packages.debian.org/source/sid/arm64/postal1
- https://salsa.debian.org/games-team/postal1
- https://github.com/RWS-Studios/POSTAL-SourceCode

## 8. Execution status and blocker

A local checkout/build was attempted in the available execution container. The attempt stopped before checkout because outbound DNS/network access to `github.com` was unavailable (`Could not resolve host: github.com`). Consequently:

- No compiler invocation occurred.
- No dependency installation was performed.
- No executable was produced.
- No runtime test was performed.
- No build log or artifact hash exists.

This is an environment acquisition blocker, not a source build failure. The source inspection is complete enough to define the first controlled build, but the milestone remains **NOT BUILT / NOT RUNTIME VERIFIED**.

## 9. Acceptance gates

| Gate | Required evidence | Current status |
|---|---|---|
| G0 Source identity | exact commit + source archive hash | commit identified; archive hash pending |
| G1 Toolchain | compiler/Make/SDL2 versions | pending |
| G2 Dependency closure | resolved headers, link libs and runtime libs | partial static inventory |
| G3 Clean compile | zero exit code + full log | blocked: source checkout unavailable |
| G4 Artifact | executable path, architecture and SHA-256 | pending |
| G5 Runtime launch | launch log + data edition + SDL2 resolution | pending |
| G6 Functional smoke test | title, level, input, graphics, audio, shutdown | pending |
| G7 Reproducibility | second clean build and artifact comparison | pending |

**Do not mark POSTAL as build-verified until G0–G6 pass.** G7 is required before calling the build reproducible in the strict bit-for-bit sense.

"""Filename: cgsdb_discovery/source_audit.py"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable

IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules",
    "target", "dist", "build-cache",
}
SOURCE_EXTENSIONS = {
    ".c": "C", ".h": "C/header", ".cc": "C++", ".cpp": "C++",
    ".cxx": "C++", ".hpp": "C++/header", ".hh": "C++/header",
    ".hxx": "C++/header", ".m": "Objective-C", ".mm": "Objective-C++",
    ".s": "Assembly", ".asm": "Assembly", ".inc": "Include/assembly",
    ".pas": "Pascal", ".pp": "Pascal", ".p": "Pascal",
    ".rs": "Rust", ".zig": "Zig", ".cs": "C#", ".java": "Java",
    ".py": "Python", ".lua": "Lua", ".js": "JavaScript",
    ".ts": "TypeScript", ".go": "Go", ".swift": "Swift",
}
BUILD_FILES = {
    "makefile", "gnumakefile", "cmakelists.txt", "meson.build",
    "build.ninja", "configure", "configure.ac", "configure.in",
    "sconstruct", "sconscript", "justfile", "cargo.toml",
    "package.json", "pyproject.toml", "build.gradle", "pom.xml",
}
BUILD_SUFFIXES = {
    ".mak", ".mk", ".sln", ".vcxproj", ".vcproj", ".dsp", ".dsw",
    ".xcodeproj", ".xcworkspace", ".bat", ".cmd", ".sh", ".ps1",
}
ASSET_DIR_HINTS = {
    "asset", "assets", "data", "resource", "resources", "media",
    "gfx", "graphics", "sound", "audio", "music", "texture",
    "textures", "model", "models", "map", "maps", "level", "levels",
    "sprite", "sprites", "art", "video", "movie", "cinematic",
}
DEPENDENCY_FILES = {
    "requirements.txt", "conanfile.py", "conanfile.txt", "vcpkg.json",
    "cargo.toml", "go.mod", "package.json", "pyproject.toml",
    "pom.xml", "build.gradle", "packages.config",
}
INCLUDE_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"', re.MULTILINE)
@dataclass(slots=True)
class FileEntry:
    path: str
    size: int
    suffix: str


def _walk(root: Path) -> tuple[list[FileEntry], list[str]]:
    files: list[FileEntry] = []
    dirs: list[str] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in IGNORED_DIRS
            and not (Path(current) / name).is_symlink()
        )
        current_path = Path(current)
        for dirname in dirnames:
            dirs.append((current_path / dirname).relative_to(root).as_posix())
        for filename in filenames:
            path = current_path / filename
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                stat = path.stat(follow_symlinks=False)
            except OSError:
                continue
            files.append(FileEntry(
                path=path.relative_to(root).as_posix(),
                size=stat.st_size,
                suffix=path.suffix.casefold(),
            ))
    return files, dirs


async def _read_text(path: Path, limit: int = 2_000_000) -> str:
    def read() -> str:
        try:
            if path.stat().st_size > limit:
                return ""
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    return await asyncio.to_thread(read)


async def _scan(root: Path) -> dict:
    files, dirs = await asyncio.to_thread(_walk, root)
    by_path = {entry.path.casefold(): entry for entry in files}
    extensions = Counter(entry.suffix or "[no-extension]" for entry in files)
    languages = Counter(
        language for entry in files
        if (language := SOURCE_EXTENSIONS.get(entry.suffix))
    )
    build_files = [
        entry.path for entry in files
        if Path(entry.path).name.casefold() in BUILD_FILES
        or entry.suffix.casefold() in BUILD_SUFFIXES
    ]
    asset_dirs = sorted({
        directory for directory in dirs
        if any(hint in Path(directory).name.casefold() for hint in ASSET_DIR_HINTS)
    })
    dependency_files = [
        entry.path for entry in files
        if Path(entry.path).name.casefold() in DEPENDENCY_FILES
    ]

    dependencies: set[str] = set()
    unresolved_includes: list[dict[str, str]] = []
    for rel in dependency_files:
        text = await _read_text(root / rel)
        name = Path(rel).name.casefold()
        if name == "cargo.toml":
            dependencies.update(re.findall(r'(?m)^\s*([A-Za-z0-9_-]+)\s*=\s*["{]', text))
        elif name == "package.json":
            try:
                package = json.loads(text)
                for key in ("dependencies", "devDependencies", "peerDependencies"):
                    dependencies.update(package.get(key, {}).keys())
            except (json.JSONDecodeError, AttributeError):
                pass
        elif name == "requirements.txt":
            dependencies.update(
                match.group(1) for line in text.splitlines()
                if (match := re.match(r"\s*([A-Za-z0-9_.-]+)", line))
                and not line.lstrip().startswith("#")
            )
        elif name in {"conanfile.txt", "conanfile.py", "vcpkg.json"}:
            dependencies.add(f"dependency-manifest:{rel}")

    source_files = [
        entry for entry in files
        if entry.suffix in {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}
    ]
    for entry in source_files:
        text = await _read_text(root / entry.path, limit=500_000)
        for include in INCLUDE_RE.findall(text):
            candidate = (Path(entry.path).parent / include).as_posix()
            normalized = os.path.normpath(candidate).replace("\\", "/").casefold()
            if normalized not in by_path and include.casefold() not in by_path:
                unresolved_includes.append({"from": entry.path, "include": include})

    top_level = Counter(
        entry.path.split("/", 1)[0] for entry in files
    )
    total_bytes = sum(entry.size for entry in files)
    c_count = sum(extensions[suffix] for suffix in (".c", ".h"))
    cpp_count = sum(extensions[suffix] for suffix in (".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"))
    has_cmake = any(Path(path).name.casefold() == "cmakelists.txt" for path in build_files)
    has_make = any(Path(path).name.casefold() in {"makefile", "gnumakefile"} or Path(path).suffix.casefold() in {".mak", ".mk"} for path in build_files)
    has_vs = any(Path(path).suffix.casefold() in {".sln", ".vcxproj", ".vcproj", ".dsp", ".dsw"} for path in build_files)

    return {
        "schema_version": 1,
        "root": str(root),
        "inventory": {
            "file_count": len(files),
            "directory_count": len(dirs),
            "total_bytes": total_bytes,
            "extension_counts": dict(sorted(extensions.items())),
            "language_file_counts": dict(sorted(languages.items())),
            "top_level_file_counts": dict(sorted(top_level.items())),
        },
        "source_presence": {
            "c_or_c_headers": c_count,
            "cpp_or_cpp_headers": cpp_count,
            "assembly_files": languages.get("Assembly", 0),
            "source_extensions": sorted(
                suffix for suffix in extensions
                if suffix in SOURCE_EXTENSIONS
            ),
        },
        "build_systems": {
            "build_files": sorted(build_files),
            "cmake": has_cmake,
            "make": has_make,
            "visual_studio_or_legacy_project": has_vs,
        },
        "asset_directories": asset_dirs,
        "dependency_manifests": sorted(dependency_files),
        "dependency_names": sorted(dependencies),
        "unresolved_local_includes": unresolved_includes[:500],
        "unresolved_local_include_count": len(unresolved_includes),
        "assessment": {
            "source_present": bool(c_count or cpp_count or languages.get("Assembly", 0)),
            "build_metadata_present": bool(build_files),
            "assets_or_data_directories_present": bool(asset_dirs),
            "buildability": "not-tested",
            "completeness": "not-assessed",
            "license_or_authorization": "not-assessed",
            "warning": (
                "This is a static inventory only. It does not establish source "
                "authorization, license compatibility, complete game coverage, "
                "dependency availability, or successful buildability."
            ),
        },
    }


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


async def audit_source_tree(root: Path) -> dict:
    resolved = root.expanduser().resolve(strict=True)
    if not resolved.is_dir():
        raise NotADirectoryError(resolved)
    return await _scan(resolved)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inventory a local game source tree without modifying it."
    )
    parser.add_argument("source", type=Path, help="Local source checkout directory")
    parser.add_argument(
        "--output", type=Path,
        help="Optional JSON report path (written atomically)",
    )
    args = parser.parse_args(argv)
    report = asyncio.run(audit_source_tree(args.source))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        _atomic_write(args.output, rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

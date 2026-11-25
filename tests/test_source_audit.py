"""Filename: tests/test_source_audit.py"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cgsdb_discovery.source_audit import audit_source_tree, main


class SourceAuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_inventory_reports_languages_build_files_assets_and_includes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "assets").mkdir()
            (root / "src" / "main.c").write_text(
                '#include "local.h"\n#include "missing.h"\n', encoding="utf-8"
            )
            (root / "src" / "local.h").write_text("#pragma once\n", encoding="utf-8")
            (root / "src" / "game.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            (root / "CMakeLists.txt").write_text("project(sample)\n", encoding="utf-8")
            (root / "assets" / "tile.bin").write_bytes(b"asset")

            report = await audit_source_tree(root)

            self.assertEqual(report["inventory"]["file_count"], 5)
            self.assertEqual(report["source_presence"]["c_or_c_headers"], 2)
            self.assertEqual(report["source_presence"]["cpp_or_cpp_headers"], 1)
            self.assertTrue(report["build_systems"]["cmake"])
            self.assertIn("assets", report["asset_directories"])
            self.assertEqual(report["unresolved_local_include_count"], 1)
            self.assertEqual(report["assessment"]["buildability"], "not-tested")
            self.assertEqual(report["assessment"]["completeness"], "not-assessed")

    async def test_symlink_directories_are_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root"
            outside = Path(temp) / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "secret.c").write_text("int x;\n", encoding="utf-8")
            (root / "linked").symlink_to(outside, target_is_directory=True)

            report = await audit_source_tree(root)
            self.assertEqual(report["inventory"]["file_count"], 0)

    def test_cli_writes_valid_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "src"
            root.mkdir()
            output = Path(temp) / "report.json"
            self.assertEqual(main([str(root), "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)

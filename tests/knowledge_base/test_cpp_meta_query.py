from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "knowledge_base"))

from src.cpp_meta_query import (
    analyze_function,
    export_source_bundle,
    export_subfunction_source_bundle,
    print_function_call_sequence,
    print_function_param_constraints,
)


@unittest.skipUnless(
    Path(os.environ.get("KREPO_TEST_REPO", "linux-7.0")).exists(),
    "requires a local Linux source tree with .vscode/BROWSE.VC.DB; set KREPO_TEST_REPO to override",
)
class CppMetaQuerySmokeTest(unittest.TestCase):
    repo = os.environ.get("KREPO_TEST_REPO", "linux-7.0")

    def test_analyze_function_finds_vfs_read(self) -> None:
        report = analyze_function(
            "vfs_read",
            repo=self.repo,
            file_filter=r"fs\read_write.c",
            max_deps=2,
            max_snippet_lines=3,
        )
        self.assertEqual(report["selected"]["name"], "vfs_read")
        self.assertIn("vfs_read", report["source"])

    def test_export_source_bundle_includes_nested_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "vfs_read_bundle.c"
            export_source_bundle(
                "vfs_read",
                output=output,
                repo=self.repo,
                file_filter=r"fs\read_write.c",
                max_deps=20,
                max_snippet_lines=6,
                max_nesting_depth=2,
            )
            text = output.read_text(encoding="utf-8")
        self.assertIn("struct file", text)
        self.assertIn("struct file_operations", text)
        self.assertIn("vfs_read", text)

    def test_call_chain_prints_upstream_path(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            print_function_call_sequence(
                "can_send",
                repo=self.repo,
                file_filter=r"net\can\af_can.c",
                max_depth=2,
                max_chains=5,
                max_callers_per_level=10,
            )
        text = stdout.getvalue()
        self.assertIn("Target: can_send", text)
        self.assertIn("-> can_send", text)

    def test_export_subfunction_bundle_includes_child_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "vfs_read_subfunctions_bundle.c"
            export_subfunction_source_bundle(
                "vfs_read",
                output=output,
                repo=self.repo,
                file_filter=r"fs\read_write.c",
                max_depth=1,
                max_functions=5,
                max_deps=10,
                max_snippet_lines=12,
                max_nesting_depth=1,
            )
            text = output.read_text(encoding="utf-8")
        self.assertIn("Function sources: callees before callers", text)
        self.assertIn("rw_verify_area", text)
        self.assertIn("vfs_read", text)
        self.assertIn("Skipped auxiliary callees", text)
        self.assertNotRegex(text, r"/\* \[\d+\] add_rchar")
        self.assertNotRegex(text, r"/\* \[\d+\] inc_syscr")

    def test_param_constraints_prints_user_pointer(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            print_function_param_constraints(
                "vfs_read",
                repo=self.repo,
                file_filter=r"fs\read_write.c",
                max_deps=2,
                max_snippet_lines=3,
            )
        text = stdout.getvalue()
        self.assertIn("Parameter: buf", text)
        self.assertIn("__user", text)


if __name__ == "__main__":
    unittest.main()


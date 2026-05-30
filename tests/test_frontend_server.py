from __future__ import annotations

import unittest
from pathlib import Path

from frontend.server import build_steps, default_config


class FrontendServerTest(unittest.TestCase):
    def test_build_steps_creates_selected_knowledge_commands(self) -> None:
        steps = build_steps(
            {
                "repo": "./linux-7.0",
                "function": "can_send",
                "file": "net/can/af_can.c",
                "artifacts": ["report_json", "subsource", "calls", "params"],
                "max_depth": 1,
                "max_functions": 30,
                "call_depth": 3,
            },
            Path("/tmp/axf-task"),
        )

        self.assertEqual([step.name for step in steps], ["report_json", "subsource", "calls", "params"])
        commands = [" ".join(step.command) for step in steps]
        self.assertIn("cpp_meta_query.py report can_send", commands[0])
        self.assertIn("--format json", commands[0])
        self.assertIn("cpp_meta_query.py subsource can_send", commands[1])
        self.assertIn("--max-functions 30", commands[1])
        self.assertIn("cpp_meta_query.py calls can_send", commands[2])
        self.assertIn("--max-depth 3", commands[2])
        self.assertTrue(steps[1].artifact_path.name.endswith("_subsource_bundle.c"))

    def test_build_steps_requires_core_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "缺少必填字段：function"):
            build_steps({"repo": "./linux-7.0"}, Path("/tmp/axf-task"))

    def test_default_config_targets_knowledge_base_outputs(self) -> None:
        defaults = default_config()

        self.assertEqual(defaults["function"], "can_send")
        self.assertIn(defaults["repo"], {"./linux-7.0", "../linux-7.0"})
        self.assertIn("report_json", defaults["artifacts"])
        self.assertIn("subsource", defaults["artifacts"])


if __name__ == "__main__":
    unittest.main()

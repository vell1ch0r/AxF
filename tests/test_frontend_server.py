from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from agents.harness_generation.agent import parse_model_json
from frontend.server import PipelineStep, build_steps, default_config, _extra_artifacts_for_step


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
        self.assertIn("harness_generation_agent", defaults["artifacts"])
        self.assertEqual(defaults["api_key_env"], "API_KEY")

    def test_harness_step_adds_required_context_steps(self) -> None:
        steps = build_steps(
            {
                "repo": "./linux-7.0",
                "function": "can_send",
                "file": "net/can/af_can.c",
                "artifacts": ["harness_generation_agent"],
                "model": "glm-5.1",
                "chat_url": "https://example.invalid/v1/chat/completions",
                "api_key_env": "API_KEY",
            },
            Path("/tmp/axf-task"),
        )

        self.assertEqual(
            [step.name for step in steps],
            ["report_json", "subsource", "calls", "params", "harness_generation_agent"],
        )
        harness_command = steps[-1].command
        command_text = " ".join(harness_command)
        self.assertIn("-m agents.harness_generation.agent", command_text)
        self.assertIn("--model glm-5.1", command_text)
        self.assertIn("--api-key-env API_KEY", command_text)
        self.assertEqual(steps[-1].artifact_path.name, "generated_harness.txt")

    def test_parse_model_json_accepts_fenced_json(self) -> None:
        payload = parse_model_json(
            """```json
{"classification":"byte_parser","files":[{"path":"harness.c","content":"int x;"}]}
```"""
        )

        self.assertEqual(payload["classification"], "byte_parser")
        self.assertEqual(payload["files"][0]["path"], "harness.c")

    def test_harness_agent_exposes_generated_files_as_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            step = PipelineStep(
                "harness_generation_agent",
                ["python", "-m", "agents.harness_generation.agent"],
                "harness_generation_agent",
                task_dir / "generated_harness.txt",
            )
            self.assertEqual(_extra_artifacts_for_step(step), [])

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            harness_dir = task_dir / "harness"
            harness_dir.mkdir()
            (harness_dir / "harness.c").write_text("int x;\n", encoding="utf-8")
            (harness_dir / "harness_spec.json").write_text("{}\n", encoding="utf-8")
            step = PipelineStep(
                "harness_generation_agent",
                [],
                "harness_generation_agent",
                task_dir / "generated_harness.txt",
            )

            names = [name for name, _path in _extra_artifacts_for_step(step)]

        self.assertEqual(names, ["fuzz_harness", "harness_spec"])


if __name__ == "__main__":
    unittest.main()

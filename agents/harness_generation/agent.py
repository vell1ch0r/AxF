from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


AGENT_NAME = "harness_generation"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "glm-5.1"
MAX_REPORT_CHARS = 50_000
MAX_SOURCE_CHARS = 90_000
MAX_TEXT_CHARS = 24_000


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_local_env(PROJECT_ROOT / ".env.local")
    load_local_env(PROJECT_ROOT / ".env")

    try:
        result = HarnessGenerationAgent().run(args)
    except HarnessGenerationError as exc:
        print(f"生成失败：{exc}", file=sys.stderr)
        return 2
    except urllib.error.URLError as exc:
        print(f"请求模型失败：{exc}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"写入产物失败：{exc}", file=sys.stderr)
        return 4

    print(f"Harness 生成 Agent 已完成：{result['artifact']}")
    return 0


class HarnessGenerationAgent:
    name = AGENT_NAME

    def run(self, args: argparse.Namespace) -> dict[str, str]:
        return generate_harness(args)


class HarnessGenerationError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Harness 生成 Agent：使用 LLM 基于知识库产物生成 libFuzzer 驱动")
    parser.add_argument("--function", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--subsource", required=True)
    parser.add_argument("--calls", required=True)
    parser.add_argument("--params", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--file", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--chat-url", default="")
    parser.add_argument("--api-key-env", default="API_KEY")
    parser.add_argument("--timeout", type=int, default=180)
    return parser.parse_args(argv)


def generate_harness(args: argparse.Namespace) -> dict[str, str]:
    output_dir = Path(args.out).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = Path(args.artifact)

    context = build_context(args)
    prompt = build_prompt(context)
    (output_dir / "llm_prompt.txt").write_text(prompt, encoding="utf-8")

    payload = request_harness_json(
        prompt=prompt,
        model=args.model or os.environ.get("MODEL") or DEFAULT_MODEL,
        chat_url=args.chat_url or _env_first("CHAT_COMPLETIONS_URL", "API_BASE_URL", "BASE_URL"),
        api_key_env=args.api_key_env or "API_KEY",
        timeout=args.timeout,
    )

    (output_dir / "llm_response.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    written = write_harness_files(output_dir, payload, context)
    write_artifact(artifact_path, output_dir, written, payload)
    return {"out": str(output_dir), "artifact": str(artifact_path)}


def build_context(args: argparse.Namespace) -> dict[str, str]:
    report_path = Path(args.report_json)
    subsource_path = Path(args.subsource)
    calls_path = Path(args.calls)
    params_path = Path(args.params)
    missing = [str(path) for path in [report_path, subsource_path, calls_path, params_path] if not path.exists()]
    if missing:
        raise HarnessGenerationError("缺少知识库产物：" + ", ".join(missing))

    return {
        "function": args.function,
        "file": args.file,
        "repo": args.repo,
        "task_dir": args.task_dir,
        "report_json": _read_limited(report_path, MAX_REPORT_CHARS),
        "subsource": _read_limited(subsource_path, MAX_SOURCE_CHARS),
        "calls": _read_limited(calls_path, MAX_TEXT_CHARS),
        "params": _read_limited(params_path, MAX_TEXT_CHARS),
    }


def build_prompt(context: dict[str, str]) -> str:
    target = f"{context['file']}::{context['function']}" if context["file"] else context["function"]
    return f"""你是 AxF 的 Harness 生成 Agent。请基于下方 kRepo/AxF 知识库产物，为目标函数生成用户态 libFuzzer 驱动。

目标函数：{target}
源码根目录：{context['repo']}

要求：
1. 统一入口必须是 int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size)。
2. 生成最小可读的用户态 C 代码，优先用 Data/Size 构造 buffer、长度、flags、枚举、地址结构、sk_buff 形态输入。
3. 如果目标严重依赖真实内核状态、硬件、并发或函数指针分派，请给出 unsupported 或 needs_manual_fixture，不要伪造成功。
4. 只能生成文件内容，不要修改 Linux 源码。
5. 同时给出 Unix build.sh 和 Windows build.ps1。编译命令以 clang 和 libFuzzer sanitizer 为默认假设即可。
6. 输出必须是一个 JSON 对象，不要输出 Markdown。JSON schema：
{{
  "classification": "byte_parser|skb_handler|sock_msg|net_device_state|unsupported|needs_manual_fixture",
  "unsupported_reason": "",
  "mock_rationale": "为什么这些 mock/fixture 足够或为什么不足",
  "seed_hints": ["可选种子建议"],
  "files": [
    {{"path": "harness.c", "content": "..."}},
    {{"path": "mocks.h", "content": "..."}},
    {{"path": "mocks.c", "content": "..."}},
    {{"path": "build.sh", "content": "..."}},
    {{"path": "build.ps1", "content": "..."}},
    {{"path": "dict.txt", "content": "..."}}
  ],
  "harness_spec": {{
    "function": {{"name": "{context['function']}", "file": "{context['file']}"}},
    "classification": "",
    "input_plan": [],
    "status": "generated|unsupported|needs_manual_fixture",
    "diagnostics": []
  }}
}}

--- report.json ---
{context['report_json']}

--- subsource bundle ---
{context['subsource']}

--- upstream calls ---
{context['calls']}

--- parameter constraints ---
{context['params']}
"""


def request_harness_json(
    *,
    prompt: str,
    model: str,
    chat_url: str,
    api_key_env: str,
    timeout: int,
) -> dict[str, Any]:
    if not chat_url:
        raise HarnessGenerationError("缺少 Chat Completions URL，请在 .env.local 设置 CHAT_COMPLETIONS_URL 或在前端填写")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise HarnessGenerationError(f"缺少 API key，请在环境变量或 .env.local 设置 {api_key_env}")

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是 AxF Harness 生成 Agent，只输出一个 JSON 对象，内容用于写入本地 fuzz harness 文件。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        chat_url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")

    envelope = json.loads(raw)
    content = _choice_content(envelope)
    if not content:
        raise HarnessGenerationError("模型响应中没有 choices[0].message.content")
    try:
        return parse_model_json(content)
    except json.JSONDecodeError as exc:
        raise HarnessGenerationError(f"模型没有返回合法 JSON：{exc}") from exc


def parse_model_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise HarnessGenerationError("模型 JSON 顶层必须是对象")
    return value


def write_harness_files(output_dir: Path, payload: dict[str, Any], context: dict[str, str]) -> list[Path]:
    files = payload.get("files")
    if not isinstance(files, list):
        files = _legacy_files(payload)
    written: list[Path] = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        rel_path = str(entry.get("path") or "").strip()
        content = entry.get("content")
        if not rel_path or content is None:
            continue
        target = _safe_output_path(output_dir, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")
        if target.name in {"build.sh"}:
            target.chmod(target.stat().st_mode | stat.S_IXUSR)
        written.append(target)

    ensure_support_files(output_dir, payload, context, written)
    return sorted(set(written), key=lambda path: str(path))


def ensure_support_files(output_dir: Path, payload: dict[str, Any], context: dict[str, str], written: list[Path]) -> None:
    existing = {path.relative_to(output_dir).as_posix() for path in written}
    spec = payload.get("harness_spec")
    if not isinstance(spec, dict):
        spec = {}
    spec.setdefault("function", {"name": context["function"], "file": context["file"]})
    spec.setdefault("classification", payload.get("classification", "needs_manual_fixture"))
    spec.setdefault("status", "unsupported" if payload.get("unsupported_reason") else "generated")
    spec.setdefault("diagnostics", [])
    spec.setdefault("mock_rationale", payload.get("mock_rationale", ""))
    spec_path = output_dir / "harness_spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    written.append(spec_path)

    if "build.sh" not in existing:
        path = output_dir / "build.sh"
        path.write_text(default_build_sh(), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        written.append(path)
    if "build.ps1" not in existing:
        path = output_dir / "build.ps1"
        path.write_text(default_build_ps1(), encoding="utf-8")
        written.append(path)
    if "seed_corpus/README.txt" not in existing:
        seed_dir = output_dir / "seed_corpus"
        seed_dir.mkdir(exist_ok=True)
        hints = payload.get("seed_hints")
        text = "\n".join(str(item) for item in hints) if isinstance(hints, list) and hints else "Add seed files here.\n"
        path = seed_dir / "README.txt"
        path.write_text(text.rstrip() + "\n", encoding="utf-8")
        written.append(path)


def write_artifact(artifact_path: Path, output_dir: Path, files: list[Path], payload: dict[str, Any]) -> None:
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Harness 生成 Agent 产物",
        "",
        f"分类: {payload.get('classification', 'unknown')}",
        f"状态: {payload.get('harness_spec', {}).get('status', 'generated') if isinstance(payload.get('harness_spec'), dict) else 'generated'}",
        "",
        "## 文件",
    ]
    for path in files:
        rel = path.relative_to(output_dir).as_posix()
        lines.append(f"- {rel}")
    lines.append("")
    rationale = payload.get("mock_rationale")
    if rationale:
        lines.extend(["## Mock/Fixture 说明", "", str(rationale), ""])
    unsupported = payload.get("unsupported_reason")
    if unsupported:
        lines.extend(["## 未支持原因", "", str(unsupported), ""])
    lines.append("## 主要文件内容")
    for path in files:
        if path.suffix not in {".c", ".h", ".sh", ".ps1", ".json", ".txt"}:
            continue
        rel = path.relative_to(output_dir).as_posix()
        lines.extend(["", f"### {rel}", "", "```", _read_limited(path, 24_000), "```"])
    artifact_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.startswith("export "):
            stripped = stripped.removeprefix("export ").strip()
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def _choice_content(envelope: dict[str, Any]) -> str:
    choices = envelope.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    text = first.get("text")
    return text if isinstance(text, str) else ""


def _legacy_files(payload: dict[str, Any]) -> list[dict[str, str]]:
    mapping = {
        "harness_c": "harness.c",
        "mocks_h": "mocks.h",
        "mocks_c": "mocks.c",
        "build_sh": "build.sh",
        "build_ps1": "build.ps1",
        "dict_txt": "dict.txt",
    }
    return [
        {"path": path, "content": str(payload[key])}
        for key, path in mapping.items()
        if key in payload
    ]


def _safe_output_path(output_dir: Path, rel_path: str) -> Path:
    target = (output_dir / rel_path).resolve()
    try:
        target.relative_to(output_dir.resolve())
    except ValueError as exc:
        raise HarnessGenerationError(f"非法输出路径：{rel_path}") from exc
    return target


def _read_limited(path: Path, limit: int) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n/* truncated: {len(text) - limit} chars omitted */\n"


def _env_first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return ""


def default_build_sh() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
clang -std=gnu11 -fsanitize=fuzzer,address,undefined harness.c mocks.c -I. -o fuzzer
"""


def default_build_ps1() -> str:
    return """$ErrorActionPreference = "Stop"
clang -std=gnu11 -fsanitize=fuzzer,address,undefined harness.c mocks.c -I. -o fuzzer.exe
"""


if __name__ == "__main__":
    raise SystemExit(main())

# AI-Assisted libFuzzer Driver Generation Platform

本项目是一个基于知识库的 AI 辅助 `libFuzzer` 驱动生成平台，目标是围绕 C/C++ 库构建“知识库 -> 驱动生成 -> 种子生成 -> 执行 -> Crash/覆盖率分析 -> 反馈”的迭代闭环。

当前阶段保持 high-level、可演进的工程骨架，优先跑通知识库组件和后续 Agent 工作流的最小闭环。

## 核心组件

- `knowledge_base/`：知识库组件代码，当前包含 C/C++ 元数据抽取能力。
- `agents/driver_generation/`：Fuzz 驱动生成 Agent。
- `agents/driver_execution/`：Fuzz 驱动执行 Agent。
- `agents/crash_analysis/`：Crash 分析 Agent。
- `scheduler/`：调度组件。
- `tools/`：构建、libFuzzer、覆盖率、Crash 等工具封装。
- `workspace/`：本地运行产物目录。

## 文档

- [架构文档](docs/architecture.md)
- [知识库组件说明](docs/knowledge_base/README.md)
- [API 文档索引](docs/api/README.md)
- [cpp_meta_query API](docs/api/knowledge_base/cpp_meta_query.md)

## 测试

知识库组件烟测：

```powershell
$env:KREPO_TEST_REPO='F:\AI\codexProject\kRepo\linux-7.0'
python -m unittest tests.knowledge_base.test_cpp_meta_query -v
```

如果未设置 `KREPO_TEST_REPO` 且当前目录不存在 `linux-7.0`，相关测试会自动跳过。

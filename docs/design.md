# AxF 详细设计

本文档描述 AxF 当前版本的工程设计。README 只保留快速入口；本文件记录具体架构、任务流、文件协议、Agent 约定和后续扩展方式。

## 1. 当前目标

AxF 当前版本不追求完整 fuzzing 平台，而是先跑通一个最小可用闭环：

```text
用户选择函数
  -> 知识库抽取函数上下文
  -> Harness 生成 Agent 调用 LLM
  -> 生成 libFuzzer harness 产物
```

第一阶段只生成 harness，不负责真实编译、运行、覆盖率统计和 crash 分析。这些能力以后作为独立 Agent 加入。

## 2. 非目标

当前版本明确不做：

- 不修改 Linux 源码。
- 不修改 kRepo 来源代码。
- 不引入数据库服务、消息队列、用户权限系统或多租户能力。
- 不把前端做成完整云端平台。
- 不在 README 中堆放详细设计。
- 不把编译修复、运行 fuzz、crash 分析混进 Harness 生成 Agent。

这些能力后续可以加，但要以独立 Agent 或独立工具层加入，避免第一版架构变重。

## 3. 顶层结构

```text
AxF/
  agents/
    harness_generation/
      agent.py
      README.md
  frontend/
    server.py
    static/
      index.html
      app.js
      styles.css
  knowledge_base/
    src/
      cpp_meta_query.py
      cpp_meta/
  docs/
    architecture.md
    design.md
  tests/
  workspace/
```

每层职责：

- `frontend/`：本地 Web 控制台和轻量任务调度。
- `knowledge_base/`：函数级知识抽取。
- `agents/`：面向 fuzzing 生命周期的 Agent。
- `workspace/`：所有运行时任务和产物。
- `docs/`：设计、架构和 API 说明。

## 4. 数据边界

AxF 使用文件作为组件之间的协议。这样做是为了保持早期系统简单、可调试、可复制。

任务目录是唯一共享状态：

```text
workspace/web/tasks/<task_id>/
```

前端、知识库和 Agent 都只通过这个目录交换输入和输出。

### 4.1 任务元数据

`task.json` 记录任务配置和实际执行步骤：

```json
{
  "id": "9ca6df37c93c",
  "config": {
    "repo": "../linux-7.0",
    "function": "can_send",
    "file": "net/can/af_can.c",
    "artifacts": ["report_json", "subsource", "calls", "params", "harness_generation_agent"],
    "model": "glm-5.1",
    "api_key_env": "API_KEY"
  },
  "steps": []
}
```

`events.jsonl` 记录面向 UI 的事件流：

```json
{"ts": 1780110187.69, "phase": "report_json", "message": "JSON 报告 已完成", "artifact": "report_json"}
```

`task.log` 记录实际执行命令和进程输出。

## 5. 前端与任务调度

入口：

```bash
python -m frontend.server --host 127.0.0.1 --port 8787 --open
```

核心文件：

- `frontend/server.py`
- `frontend/static/index.html`
- `frontend/static/app.js`
- `frontend/static/styles.css`

### 5.1 前端职责

前端只做：

- 收集用户输入。
- 调用本地 API 创建任务。
- 展示任务状态、事件、日志和产物。
- 读取已生成的产物文件。

前端不做：

- 不直接调用 LLM。
- 不直接拼 prompt。
- 不解析模型 JSON。
- 不编译 fuzz target。
- 不修改 Linux 源码。

### 5.2 后端 API

当前本地 HTTP API 很小：

```text
GET  /api/defaults
GET  /api/tasks
GET  /api/tasks/<task_id>
GET  /api/tasks/<task_id>/artifact?name=<artifact>
POST /api/tasks
POST /api/tasks/<task_id>/cancel
```

这些 API 只服务本地 Web UI，不作为长期稳定的公开 API。

### 5.3 任务步骤构造

`build_steps(config, task_dir)` 将一次任务转换为线性步骤。

如果只勾选知识产物：

```text
report_md
report_json
subsource
calls
params
```

如果勾选 `Harness 生成 Agent`，调度层会自动补齐上下文步骤：

```text
report_json
subsource
calls
params
harness_generation_agent
```

这是因为 Harness 生成 Agent 依赖这四个输入文件：

- `report.json`
- `<function>_subsource_bundle.c`
- `calls.txt`
- `params.txt`

## 6. 知识库层设计

入口：

```bash
python knowledge_base/src/cpp_meta_query.py <command> <function> --repo <repo> --file <file>
```

当前使用的命令：

```text
report --format json
subsource
calls
params
```

### 6.1 输入

- Linux 或其他 C/C++ 项目源码根目录。
- VS Code C/C++ 插件生成的 `.vscode/BROWSE.VC.DB`。
- 目标函数名。
- 可选文件过滤，例如 `net/can/af_can.c`。

### 6.2 输出

知识库层输出纯上下文，不生成 harness：

```text
report.json
<function>_subsource_bundle.c
calls.txt
params.txt
```

### 6.3 路径兼容

文件过滤需要兼容 macOS/Linux 的 `/` 和 Windows 的 `\`。因此查询函数时要同时接受两种路径形式。

## 7. Harness 生成 Agent

位置：

```text
agents/harness_generation/
```

入口：

```bash
python -m agents.harness_generation.agent --help
```

### 7.1 职责

Harness 生成 Agent 负责：

- 读取知识库产物。
- 构造 LLM prompt。
- 调用兼容 Chat Completions 的模型服务。
- 解析模型返回的 JSON。
- 写出 harness 文件和规格文件。
- 写出便于 UI 预览的 `generated_harness.txt`。

它不负责：

- 编译 harness。
- 修复编译错误。
- 运行 libFuzzer。
- 分析 crash。
- 管理长期知识库。

这些能力应由后续 Agent 负责。

### 7.2 CLI 参数

Harness 生成 Agent 的最小命令形式：

```bash
python -m agents.harness_generation.agent \
  --function can_send \
  --file net/can/af_can.c \
  --repo ../linux-7.0 \
  --task-dir workspace/web/tasks/<task_id> \
  --report-json workspace/web/tasks/<task_id>/report.json \
  --subsource workspace/web/tasks/<task_id>/can_send_subsource_bundle.c \
  --calls workspace/web/tasks/<task_id>/calls.txt \
  --params workspace/web/tasks/<task_id>/params.txt \
  --out workspace/web/tasks/<task_id>/harness \
  --artifact workspace/web/tasks/<task_id>/generated_harness.txt
```

可选参数：

```text
--model
--chat-url
--api-key-env
--timeout
```

### 7.3 环境变量

默认读取仓库根目录下的 `.env.local` 和 `.env`：

```text
API_KEY=...
CHAT_COMPLETIONS_URL=...
MODEL=glm-5.1
```

也支持 shell 风格：

```bash
export API_KEY=...
```

密钥不进入任务目录，不进入日志，不进入 Git。

### 7.4 Prompt 输入

Agent 发送给模型的上下文包含：

- 目标函数名。
- 文件路径。
- 源码根目录。
- `report.json` 内容。
- `subsource` 源码包。
- 上层调用链。
- 参数约束。

为了避免上下文过长，Agent 对输入做长度限制：

```text
report.json: 50000 chars
subsource:   90000 chars
calls:       24000 chars
params:      24000 chars
```

超过限制时会截断，并在 prompt 中标记 omitted chars。

### 7.5 模型输出协议

模型必须返回 JSON 对象。推荐 schema：

```json
{
  "classification": "byte_parser|skb_handler|sock_msg|net_device_state|unsupported|needs_manual_fixture",
  "unsupported_reason": "",
  "mock_rationale": "",
  "seed_hints": [],
  "files": [
    {"path": "harness.c", "content": ""},
    {"path": "mocks.h", "content": ""},
    {"path": "mocks.c", "content": ""},
    {"path": "build.sh", "content": ""},
    {"path": "build.ps1", "content": ""},
    {"path": "dict.txt", "content": ""}
  ],
  "harness_spec": {
    "function": {"name": "can_send", "file": "net/can/af_can.c"},
    "classification": "skb_handler",
    "input_plan": [],
    "status": "generated",
    "diagnostics": []
  }
}
```

Agent 会接受带 Markdown code fence 的 JSON，例如：

````text
```json
{...}
```
````

但最终会只解析其中的 JSON 对象。

### 7.6 输出文件

Agent 输出目录：

```text
workspace/web/tasks/<task_id>/harness/
```

标准文件：

```text
harness.c
mocks.h
mocks.c
build.sh
build.ps1
dict.txt
harness_spec.json
llm_prompt.txt
llm_response.json
seed_corpus/README.txt
```

汇总文件：

```text
workspace/web/tasks/<task_id>/generated_harness.txt
```

前端会把以下文件作为独立产物展示：

- `Harness 生成 Agent`
- `Fuzz 驱动 harness.c`
- `Mock 头文件`
- `Mock 源文件`
- `Unix 构建脚本`
- `Windows 构建脚本`
- `Harness 规格`
- `Fuzz 字典`

## 8. 产物说明

一次任务会产生两类产物：知识库上下文和 Agent 生成结果。

### 8.1 知识库上下文

`report.json`
: 结构化函数报告。包含目标函数位置、源码、参数、依赖、调用信息等。主要给 Agent 当机器可读上下文。

`<function>_subsource_bundle.c`
: 目标函数和下游子函数源码包。Harness 生成 Agent 主要依赖它判断目标函数内部会调用什么、需要构造什么输入、需要 mock 什么内核依赖。

`calls.txt`
: 上层调用链。用于理解目标函数的真实调用场景，例如谁会调用它、调用路径大致是什么。

`params.txt`
: 参数约束。用于记录参数类型、空指针检查、长度字段、分支条件和从源码中推断出的输入限制。

### 8.2 Harness 生成结果

`generated_harness.txt`
: Harness 生成 Agent 的汇总预览文件。它把分类、mock/fixture 说明、未支持原因、文件清单和主要代码内容放在一起，方便在前端快速查看。它是人读预览，不是稳定机器协议。

`harness/harness.c`
: 真正的 fuzz 驱动入口文件。它应该包含 `LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size)`，是后续编译和执行最重要的文件。

`harness/mocks.h`
: mock 和 fixture 的头文件。通常包含用户态替代结构体、函数声明、常量和辅助构造函数声明。

`harness/mocks.c`
: mock 和 fixture 的实现文件。通常包含最小内核依赖模拟、内存释放函数、网络结构体构造函数等。

`harness/build.sh`
: macOS/Linux 下尝试编译 fuzz 驱动的脚本。当前只是生成产物，是否能真实编译通过需要后续 Harness 执行 Agent 验证。

`harness/build.ps1`
: Windows PowerShell 下尝试编译 fuzz 驱动的脚本。当前只是生成产物，是否能真实编译通过需要后续 Harness 执行 Agent 验证。

`harness/dict.txt`
: libFuzzer 字典。通常包含协议 magic、flag、长度字段、常见枚举值等，有助于 libFuzzer 更快探索有效输入。

`harness/harness_spec.json`
: 机器可读的 harness 规格。包含目标函数、分类、输入构造计划、生成状态和诊断信息。后续执行、编译修复或 crash 分析 Agent 应优先读取这个文件，而不是解析 `generated_harness.txt`。

### 8.3 优先查看顺序

调试一次生成结果时，推荐按以下顺序查看：

1. `generated_harness.txt`：先看 Agent 的总体判断。
2. `harness/harness.c`：确认 fuzz 入口和目标函数调用。
3. `harness/mocks.c` / `harness/mocks.h`：确认 mock 是否过度简化或明显错误。
4. `harness/harness_spec.json`：确认分类、输入计划和状态。
5. `build.sh` 或 `build.ps1`：进入编译执行阶段时再看。

## 9. 任务状态与错误处理

当前任务状态：

```text
queued
running
cancelling
cancelled
completed
failed
```

任一步骤返回非零退出码，任务标记为 `failed`。

常见失败原因：

- 找不到 `BROWSE.VC.DB`。
- 函数名找不到。
- 同名函数未用 `--file` 精确过滤。
- `API_KEY` 没有设置。
- `CHAT_COMPLETIONS_URL` 没有设置。
- 模型返回不是合法 JSON。
- 模型输出的文件路径非法。

Agent 会拒绝写出逃逸输出目录的路径，例如：

```text
../../bad.c
```

## 10. Windows 支持

当前 Windows 支持范围：

- 前端服务可用 `python -m frontend.server` 启动。
- `.env.local` 可直接放在仓库根目录。
- 也可用 PowerShell 环境变量：

```powershell
$env:API_KEY='...'
$env:CHAT_COMPLETIONS_URL='...'
$env:MODEL='glm-5.1'
```

Agent 会要求模型同时输出：

- `build.sh`
- `build.ps1`

知识库查询的文件过滤需要兼容：

```text
net/can/af_can.c
net\can\af_can.c
```

当前没有保证生成的 harness 一定能在 Windows 上成功编译；`build.ps1` 是生成产物的一部分，真实可用性需要后续 Harness 执行 Agent 验证。

## 11. 安全与隐私边界

- `.env.local` 被 `.gitignore` 忽略。
- 不打印 API key。
- 任务日志记录命令参数，但不记录 `Authorization` header。
- 只有勾选 `Harness 生成 Agent` 时，知识库上下文才会发送给模型服务。
- Linux 源码和 kRepo 来源代码不被修改。
- 生成物只写入 `workspace/`。

## 12. 如何新增 Agent

新增 Agent 的推荐步骤：

1. 在 `agents/<agent_name>/` 下创建 `agent.py`。
2. 提供命令行入口：

```bash
python -m agents.<agent_name>.agent --help
```

3. 使用文件作为输入输出协议。
4. 在 `frontend/server.py` 中增加一个 artifact 常量。
5. 在 `build_steps()` 中将用户选择映射为 Agent 命令。
6. 在 `_artifact_label()` 和 `_extra_artifacts_for_step()` 中登记产物展示。
7. 增加单元测试验证命令构造和产物映射。
8. 在 `docs/design.md` 记录 Agent 协议。

Agent 之间不要直接互相 import。调度层用文件和命令行连接它们。

## 13. 后续 Agent 建议

### 13.1 Harness 执行 Agent

职责：

- 编译 `harness.c`。
- 运行 `-runs=N` smoke test。
- 记录 sanitizer 输出。
- 判断 target function 是否实际到达。
- 输出执行报告。

建议输出：

```text
execution/build.log
execution/run.log
execution/result.json
```

### 13.2 编译修复 Agent

职责：

- 读取编译错误。
- 把诊断反馈给 LLM。
- 只修改 `workspace/<task>/harness/` 下生成文件。
- 限制最大修复轮数。

它可以和 Harness 执行 Agent 分开，也可以作为执行 Agent 的子模式。

### 13.3 Seed 生成 Agent

职责：

- 从 `params.txt`、`harness_spec.json` 和 `dict.txt` 生成初始语料。
- 输出 `seed_corpus/`。
- 后续根据覆盖率反馈优化 seed。

### 13.4 Crash 分析 Agent

职责：

- 读取 sanitizer 日志、crash input、调用栈和 harness 代码。
- 判断真实缺陷、harness 误用、环境问题或低价值异常。
- 输出结构化 crash 报告。

## 14. 测试策略

当前测试重点：

- `build_steps()` 是否正确构造知识抽取命令。
- 勾选 Harness 生成 Agent 时是否自动补齐上下文步骤。
- 模型返回 fenced JSON 时是否能解析。
- Agent 成功后是否把 `harness.c` 等文件映射为前端产物。

运行：

```bash
python -m unittest discover -s tests -v
```

带真实 Linux 源码树的知识库测试可设置：

```powershell
$env:KREPO_TEST_REPO='F:\path\to\linux-7.0'
python -m unittest tests.knowledge_base.test_cpp_meta_query -v
```

## 15. 当前已知限制

- Harness 生成结果还没有自动编译验证。
- 没有覆盖率统计。
- 没有 crash 分析。
- 没有自动判断 target function 是否实际到达。
- `generated_harness.txt` 是预览文件，不是稳定机器协议。
- 模型输出质量会直接影响 harness 可用性。

这些限制应通过后续 Agent 逐步补齐，而不是继续扩大前端或知识库层职责。

# AxF

AxF 是一个本地运行的知识驱动 fuzz harness 生成原型。当前版本聚焦一条最小链路：

```text
函数知识抽取 -> Harness 生成 Agent -> 本地产物
```

当前支持基于 VS Code C/C++ 插件生成的 `BROWSE.VC.DB` 抽取函数级上下文，并调用兼容 Chat Completions 的模型服务生成 `libFuzzer` harness。

## 目录

- `knowledge_base/`：函数源码、下游子函数、调用链和参数约束抽取。
- `agents/harness_generation/`：Harness 生成 Agent。
- `frontend/`：本地 Web 控制台。
- `workspace/`：本地任务和生成产物。
- `docs/`：架构、设计和 API 文档。

## 文档

- [精简架构](docs/architecture.md)
- [详细设计](docs/design.md)
- [知识库组件说明](docs/knowledge_base/README.md)
- [cpp_meta_query API](docs/api/knowledge_base/cpp_meta_query.md)

## 快速运行

在仓库根目录准备 `.env.local`。该文件已被 `.gitignore` 忽略，不会同步到 GitHub：

```bash
API_KEY=你的模型服务密钥
CHAT_COMPLETIONS_URL=https://your-provider.example/v1/chat/completions
MODEL=glm-5.1
```

启动前端：

```bash
python -m frontend.server --host 127.0.0.1 --port 8787 --open
```

Windows PowerShell 同样可以运行：

```powershell
python -m frontend.server --host 127.0.0.1 --port 8787 --open
```

页面中填入源码根目录、函数名、文件过滤，勾选 `Harness 生成 Agent` 后新建任务。产物写入：

```text
workspace/web/tasks/<task_id>/
```

核心产物：

- `report.json`
- `<function>_subsource_bundle.c`
- `calls.txt`
- `params.txt`
- `generated_harness.txt`
- `harness/harness.c`
- `harness/mocks.h`
- `harness/mocks.c`
- `harness/harness_spec.json`

各产物用途见 [详细设计：产物说明](docs/design.md#8-产物说明)。

## 测试

```bash
python -m unittest discover -s tests -v
```

如果要运行依赖 Linux 源码树的知识库测试，可以设置：

```powershell
$env:KREPO_TEST_REPO='F:\path\to\linux-7.0'
python -m unittest tests.knowledge_base.test_cpp_meta_query -v
```

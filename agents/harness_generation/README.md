# Harness 生成 Agent

该 Agent 负责把知识库产物转换为 `libFuzzer` fuzz 驱动。前端不会直接拼 prompt 或解析模型响应，只负责把任务目录中的上下文文件传给 Agent。

输入：

- `report.json`
- `<function>_subsource_bundle.c`
- `calls.txt`
- `params.txt`

输出：

- `harness/harness.c`
- `harness/mocks.h`
- `harness/mocks.c`
- `harness/build.sh`
- `harness/build.ps1`
- `harness/harness_spec.json`
- `generated_harness.txt`

命令行入口：

```bash
python -m agents.harness_generation.agent --help
```

# 可测试的 Coding Agent Runtime

面向本地代码任务的轻量 Agent Runtime。模型通过工具调用读代码、改代码、跑测试，运行时把结果写回历史，并在没有 `tool_calls` 时停下来。

主线只有这一条：读代码，修改代码，运行测试，再根据结果继续。RAG 工具可以换上，但不是这个项目要讲的功能。

## 目录

Python 包仍在 `src` 里。测试、评测、示例和说明放在 `src` 外面。文件保持完整，没有按函数拆开。

```text
agent-runtime/
├── src/agent_runtime/
│   ├── agent.py            # 循环
│   ├── llm.py              # OpenAI 兼容适配器
│   ├── environment.py
│   ├── paths.py
│   ├── permissions.py
│   └── tools/
├── examples/
│   ├── coding_agent.py     # 手动真实接口示例
│   └── demo_workspace/
├── evals/
├── tests/
└── docs/
    ├── architecture.md
    ├── test-results.md
    ├── limits.md
    └── design.md
```

`tests/fakes.py` 里的剧本模型和剧本环境只给测试用。

## 测试

在本目录运行。`pytest.ini` 会把 `src` 放进路径，这里不要 `pip install -e`，否则会盖住其他同名包。

```powershell
cd projects/agent-runtime
python -m pytest -q
```

这条命令不调用真实接口。要连上 `.env` 里的模型时，再单独跑：

```powershell
python -m pytest -m live -q
```

这四项会真实请求模型：普通回复、`echo` 往返、读取工作区文件、按原文替换。没有密钥时会跳过。日常开发继续用上面不带 `-m live` 的命令。

## 手动 Demo

把 `.env.example` 复制成项目根目录的 `.env`，填入 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。不要把密钥提交进仓库。

```powershell
python examples/coding_agent.py
python examples/coding_agent.py 请只读取 hello.py，并告诉我 add 现在返回什么
```

不带参数时，它在 `examples/demo_workspace` 里把 `add` 改成返回 `a + b + 1` 并运行 `test_hello.py`。带参数时，同一套工具和权限处理你写的任务，记录写到 `examples/traces/last_run.txt`，不会覆盖原来的 `coding_demo.txt`。

## 功能

- 只接受结构化 `tool_calls`。Markdown 代码块不会被当成工具执行
- OpenAI 兼容的 tool calling
- 多轮执行循环，工具结果回写，最大步数
- `read_file`、`grep`、`str_replace`、`run_tests`
- 调用前统一做参数校验和权限检查
- workspace 路径边界；`run_tests` 只执行测试命令
- Scripted Model、假环境和假客户端，离线测试
- 八道固定 Coding 评测，见 `evals/coding_suite.py`
- 工具结果是 JSON，同一条失败的测试命令连续两次之后不再执行
- 传入 `event_log` 时，循环把 `run_started`、模型回合和工具成败写成 JSONL。不记录完整提示词、文件正文和密钥
- 一个需要自己准备 `.env` 的手动 Demo。脱敏记录在 `examples/traces/coding_demo.txt`

## 限制

详见 [docs/limits.md](docs/limits.md)。架构和测试结果在 [docs/architecture.md](docs/architecture.md)、[docs/test-results.md](docs/test-results.md)。

- 不是生产级沙箱。路径检查和测试命令限制只拦住常见误操作。
- 评测是剧本，不代表真实模型的成功率。
- 没有多 Agent、长期记忆和并发会话。
- 模型超时和限流会重试最多 3 次。上下文超限不重试。
- RAG 不是主功能。

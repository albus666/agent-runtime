# 项目限制

这是一个可测试的 Coding Agent Runtime 原型，不是生产级编程平台。

## 已经做到的

- 一个循环同时服务 Coding 和 RAG。差别只在构造时传入的登记表。
- 工具失败写成观察并回到模型，循环继续。
- 工作区路径会先解析再判断是否越界。`..` 和指向区外的符号链接会被拒绝。
- 命令有超时和输出截断。达到最大步数后停止，不再继续问模型。
- 工具调用先校验参数，再按登记表上的 `permission` 决定是否执行。失败结果是 JSON。同一条测试命令连续失败两次后，第三次不再执行。
- `run_tests` 只执行测试命令，并仍经过 `PermissionPolicy`。
- 真实 OpenAI 兼容接口负责 schema、`tool_calls` 解析和消息格式转换。超时和限流最多重试 3 次。
- 自动化测试不连网。
- 传入 `event_log` 后，同一循环会追加 JSONL 事件。默认不写。事件里没有完整系统提示、文件正文和密钥。

## 尚未实现

**不是安全沙箱。** `PermissionPolicy` 只拒绝以 `rm`、`del`、`format`、`shutdown` 开头的命令，以及包含 `..` 的命令。重定向要经过 `ask_fn`。`run_tests` 另外只接受 `pytest`、`python -m pytest`、`python -m unittest`，以及带 `assert` 的 `python -c`。允许的测试命令本身仍可以做很多事，不能代替容器或进程隔离。

**不是向量检索。** RAG 的索引是测试里的几条字典。`search_docs` 用子串匹配公司名、摘要和正文，没有 embedding，也没有向量库。

**不是多 Agent，也没有会话系统。** 没有规划器、多模型路由、历史压缩和数据库记忆。格式错误、工具失败和命令超时会把说明写回历史，然后继续。模型请求只对超时和限流重试，上下文超限不重试。

**真实接口不在默认测试里。** `python -m pytest -q` 使用假客户端。`python -m pytest -m live -q` 才会读 `.env` 并调用接口。密钥不能写进仓库。

**RAG 不是主功能。** 不传 `tools` 时会登记 `echo` 和文件工具。只读问答必须传入 `rag_tools`，否则模型可以改文件。对外介绍这个项目时只讲 Coding 闭环。

**不解析 Markdown 代码块。** 没有 `tool_calls` 时，正文就是最终回答，不会因为出现 bash、read 或 replace 代码块而执行命令。写入只用 `str_replace`，不提供通用 `write_file` 或任意 shell。

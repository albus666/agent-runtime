# 测试结果

命令在 `projects/agent-runtime` 下执行：

```powershell
python -m pytest -q --tb=no
```

2026-10-04 去掉 Markdown 代码块协议之后的结果：

```text
51 passed, 4 deselected in 15.03s
```

默认命令带 `-m "not live"`，4 个真实接口测试被排除。其余测试使用 `ScriptedModel`、`ScriptedEnvironment` 或假的 OpenAI 客户端。

## 覆盖了什么

| 文件 | 通过 | 在查什么 |
| --- | ---: | --- |
| `test_loop.py` | 6 | 最终回答停止、工具后再回答、格式错误后恢复、代码块不执行、步数上限、超时后恢复 |
| `test_environment.py` | 4 | 命令输出、重定向留在工作区、超时观察、长输出截断 |
| `test_permissions.py` | 4 | 允许、拒绝、重定向询问、非零退出码仍继续 |
| `test_queues.py` | 4 | `exit` 不送给模型、steering、follow-up |
| `test_trajectory.py` | 1 | 轨迹与历史一致，且不再多问一次模型 |
| `test_tool_calls.py` | 4 | 无调用则结束、工具结果下一轮可见、未知工具、两个调用按顺序执行 |
| `test_file_tools.py` | 6 | 读文件、grep、唯一替换、歧义不改文件、越界拒绝、询问拒绝 |
| `test_run_tests.py` | 5 | 测试失败仍继续、危险命令不执行、同一命令第三次不再执行、Coding 评测通过 |
| `test_llm.py` | 7 | 文本回复、工具 schema 与解析、非法 JSON、缺配置、超时重试、上下文超限不重试 |
| `test_rag.py` | 3 | 搜索返回编号并读出正文、RAG 表下 `str_replace` 不改文件、RAG 评测通过 |
| `test_two_evals.py` | 2 | 同一次 `run_eval` 里 Coding 和 RAG 都通过；RAG 表忽略 Coding 写入 |
| `test_evals.py` | 2 | 三道工具调用剧本题通过；歧义替换后仍能结束 |
| `test_coding_suite.py` | 3 | 八道固定 Coding 题都通过；缺参数拒绝；非测试命令不执行 |

上表合计 51 项，全部通过。真实接口测试另有 4 项，默认不跑。同一条失败测试命令第三次不再执行，也在 `test_run_tests.py` 里。

## 两套评测

`evals/run_eval.py` 对同一个 `DefaultAgent.run` 调用两次：

- Coding：`coding_tools`，2 步，文件变成 `return a + b + 1`，输出里有 `tests passed`。
- RAG：`rag_tools`，3 步，最终回答包含「星河的入职日期是 3 月 1 日。」，且不包含索引里没有的「年薪一百万」。

真实接口示例是 `python examples/coding_agent.py`。它不在这 44 项里面，需要自己准备 `.env` 后手动跑。

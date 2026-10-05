# 设计说明

## 为什么 Model 要做成可替换协议

`Agent` 只调用 `model.query(messages)`，不出现某个 SDK 的客户端。测试传入 `ScriptedModel`，按写好的回复逐句返回，所以六条测试都不需要 API key。以后换成 DeepSeek，只新写一个同样有 `query` 方法的类，`run` / `step` 不用改。

## 为什么 Environment 不能 import Agent

环境只实现 `execute(command)`，返回 `output` 和 `returncode`，或者抛 `TimeoutError`。它不需要知道循环、步数或消息列表。这样可以单独构造 `ScriptedEnvironment`，检查某条命令有没有真的被执行。如果环境反过来引用 `Agent`，换一个假环境或以后换沙箱时，就得把整条循环一起拖进来。

## 为什么格式错误和超时要留在历史里

`FormatError` 是 `InterruptAgentFlow`。空回复既没有 `tool_calls` 也没有正文时，`run` 接住它，把说明追加成一条 `user` 消息，然后继续循环。命令超时由工具写成观察，不中断循环。步数用尽则是 `LimitsExceeded`，消息角色是 `exit`，循环到这里停止。其他异常不接住，避免把编程错误伪装成模型还能补救的情况。

## 为什么 SDK 只放在 OpenAICompatModel 里

循环只调用 `model.query(messages)`。`chat.completions.create` 写在 `OpenAICompatModel.query` 里，`OpenAI(...)` 只在 `from_env()` 里创建。测试传入假客户端或 `ScriptedModel` 时，不会碰 SDK，也不会读 API key。换 DeepSeek 或通义，改的是 `base_url` 和模型名，`Agent.step` 不用改。

## 为什么 exit 要在进模型之前丢掉

`role="exit"` 是循环用来停止的标记，不是模型对话协议里的角色。`to_model_messages` 在 `query` 之前把它滤掉，模型收到的仍是 system、user、assistant 和观察。历史列表本身还留着这条 `exit`，轨迹和 `run` 的结束判断都靠它。若把这条标记交给模型，它会看到一个不认识的角色，下一轮回复就没有稳定格式。

## 为什么超时要抛 TimeoutError

`LocalEnvironment.execute` 只负责跑命令。`subprocess.run` 超时抛出的是 `subprocess.TimeoutExpired`，循环认不出这个类型。环境把它转成内置 `TimeoutError` 再抛出，`run_tests` 里的 `except TimeoutError` 会写成 `error: timeout` 的观察，然后继续下一轮。如果环境自己把循环停掉，它就要知道 `messages`、`exit` 和 `RunResult`，换一个假环境时这套停止逻辑也得重写一遍。

## 为什么截断发生在环境里

超长输出是命令结果的一部分，还没进历史。`execute` 在返回前按 `max_output` 截断，并接上 `\n[truncated]`。循环只把这个字典写成观察，不用知道输出上限。若等观察进了 `messages` 再砍，轨迹里会先留下全文，模型下一轮也可能已经看到未截断的内容。

## 为什么拒绝要发生在 execute 之前

`deny` 表示这条命令不能启动。`run_tests` 在调用 `env.execute` 之前先检查测试命令，再调用 `PermissionPolicy.decide`。被拒绝时只返回 `error: denied` 的观察，`subprocess` 不会跑。`rm`、写到工作区外的重定向，在进程开始之后就改不回来了；等命令结束再看退出码，文件已经没了。假环境的 `history` 也因此是空的，测试可以确认它确实没被执行。观察仍留在历史里，下一轮模型还能换一条命令。

## 为什么退出码非 0 仍把输出交回模型

非 0 的 `returncode` 表示命令已经跑完，程序自己报告失败，输出里通常有原因。`run_tests` 不为此抛异常，只把真实退出码和输出写成观察。`run()` 继续循环，模型下一句可以改口并给出最终回答，所以 `status` 仍是 `"ok"`。若这里直接让 `run()` 失败返回，模型看不到失败原因，也没有机会再试一次。这和超时、拒绝不同：那两种情况命令没有正常结束，观察里的 `exit_code` 是 `null`。

## 为什么替换要求原文恰好出现一次

`old` 是从文件里抄出来的一段原文。出现一次时，`text.replace(old, new, 1)` 改的就是这一处，文件其余部分不动。出现多次时，第一次匹配未必是模型想改的那一行；若直接换掉第一个，另一处会被悄悄留下，测试也看不出改错了位置。所以次数不是 1 就写成 `not_found` 或 `ambiguous` 的观察，不调用 `write_text`。模型下一轮可以加上前后文，让这段原文变得唯一，再替换一次。

## 为什么文件不存在和空回复是两种失败

文件不存在时，`read_file` 或 `str_replace` 本身是合法的工具调用。路径或原文对不上是这次操作的结果，写成观察交回模型，循环继续，它可以换一个路径。既没有 `tool_calls`、正文又是空的，则是回复格式不对。这和文件在不在无关，所以抛 `FormatError`，把格式说明追加进历史。Markdown 代码块不会被当成工具执行。

## 为什么 steering 插进当前任务，follow-up 要等 exit

Steering 是用户在任务还没做完时改口。它在下一次 `query` 之前写进同一份 `self.messages`，模型下一轮看到的是当前历史末尾的新指令，`run` 不重新开始。Follow-up 是做完之后再做一件事。循环本来要在 `exit` 停下；这时如果队列里还有内容，就弹出一条 `user` 消息并继续 `step`。任务没结束前不弹出它，这样同一次运行里会先消化 steering，等第一次 `exit` 出现后再开始 follow-up。

## 为什么转换函数只有一个

`self.messages` 留着完整历史，包括 `exit`。模型能看见什么只由 `to_model_messages` 决定，`_call_llm` 是唯一调用它的地方。Steering 和 follow-up 都是真正的 `user` 消息，写进历史后会自然进入下一次转换。若在 `step` 里临时删掉 `exit` 再传给 `query`，以后每加一种不该给模型看的标记，就要改循环里的另一处，历史和模型看到的列表也会对不上。

## 为什么多个工具调用按顺序执行

同一轮里的 `tool_calls` 按列表顺序执行，前一个的结果写进历史之后才执行下一个。`str_replace` 先把文件改完，`run_tests` 再去跑，测试看到的才是改完的文件。若两个同时进行，测试可能读到改到一半的内容，退出码就不能说明这次修改是否正确。其中一个失败也只是一条 `role="tool"` 的结果，后面的调用仍然执行。

## 为什么 RAG 另登记一份工具表

RAG 只从索引里查原文并回答。`str_replace` 会改文件，shell 会执行命令。若复用 Coding 的工具表，模型一次误调用就会改磁盘。所以检索用 `rag_tools`，里面只有 `list_companies`、`search_docs`、`read_chunk`。调用 `str_replace` 或 `read_file` 时，登记表里没有这个名字，写成 `role="tool"` 的失败结果，不执行。Coding 评测仍传入原来的工具表，循环本身不用改。

## 为什么循环里不能出现工具名

`step` 只看回复里有没有 `tool_calls`，再按名字到当前登记表里查找。`read_file`、`search_docs` 这些名字若写进 `step`，换一套工具就要改循环。工具名只出现在各自的工具模块和评测剧本里。`evals/run_eval.py` 对 Coding 传入 `coding_tools`，对 RAG 传入 `rag_tools`，两次都是同一个 `DefaultAgent.run`。

## 为什么停止看的是有没有 tool_calls

模型可以一边写解释，一边调用工具。回复文本不是空的，仍然可能带着 `tool_calls`。这时要执行工具，循环继续。没有 `tool_calls`、正文也不是空的，才是最终回答，写成 `exit`。会话保存、历史压缩、按错误种类重试，这一份不做。

## 真实接口只做格式转换

`OpenAICompatModel` 把 `ToolSpec` 转成 `tools` schema 发给模型，再把返回的 `tool_calls` 收成内部格式：`arguments` 是字典，不是 JSON 字符串。解析失败时用空字典，不把循环打崩。没有工具调用时不写 `tool_calls` 这个键，循环把正文当成最终回答。

`step` 保存的助手消息带上 `tool_calls`。下一轮 `role="tool"` 前面才有对应的助手调用。发给供应商之前，再把内部字典转回它要的 JSON 字符串。`Agent.step` 不处理供应商对象。

## 现在的限制

这是 Coding Agent Runtime 原型。RAG 是内存里的关键词检索，没有向量库。权限是 Demo 级：拦住常见危险命令，并把 `run_tests` 也送进同一个 `policy`，不是容器沙箱。不支持多 Agent、历史压缩和按错误种类重试。真实接口只在 `examples/coding_agent.py` 里手动调用，`pytest` 使用假客户端，不连网。

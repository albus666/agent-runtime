import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_runtime.protocols import Model, Environment
from .errors import FormatError, InterruptAgentFlow, LimitsExceeded
from .event_log import EventLogger, clip_text, summarize_arguments, summarize_result
from .permissions import PermissionPolicy
from .observation import _observation
from .tools.registry import ToolSpec, coding_tools
from .trajectory import save_trajectory

FORMAT_ERROR = "Expected tool calls or a non-empty final answer."
MAX_STEPS_TEXT = "stopped: max_steps reached"


@dataclass
class RunResult:
    """run 的返回值，比裸字符串携带更多信息。

    例如 RunResult(status="ok", final_text="done", steps=1, messages=[{"role": "exit", "content": "done"}])。

    * status："ok" 或 "max_steps"
    * final_text：最后一条 exit 的正文。例如 "done"
    * steps：query 的调用次数。例如 1
    * messages：完整历史。例如 [{"role": "system", "content": "..."}, {"role": "exit", "content": "done"}]
    """
    status: str  # "ok" 或 "max_steps"
    final_text: str  # 最终回答文本
    steps: int  # query 的调用次数
    messages: list  # 完整对话历史


class Agent:
    def __init__(
            self,
            name: str,
            system_prompt: str,
            max_iterations: int,
            model: Model,
            env: Environment,
            trajectory_path: str | Path | None = None,
            policy: PermissionPolicy | None = None,
            tools: dict[str, ToolSpec] | None = None,
            event_log: str | Path | EventLogger | None = None,
    ) -> None:
        """
        :param name: 代理名字。例如 "agent"
        :param system_prompt: 系统提示。例如 "请通过已注册工具读取、搜索、修改代码和运行测试。"
        :param max_iterations: 最多调用模型的次数。例如 8
        :param model: 实现 Model 的对象。例如 ScriptedModel(["done"]) 或 OpenAICompatModel.from_env()
        :param env: 实现 Environment 的对象。例如 LocalEnvironment(Path(".")) 或 ScriptedEnvironment()
        :param trajectory_path: 轨迹文件。例如 Path("traj.jsonl")；不记录时为 None
        :param policy: 命令权限。例如 PermissionPolicy(lambda command: False)；不传时，需要询问的命令一律拒绝
        :param tools: 工具登记表。不传时使用 echo 和 coding_tools。例如 rag_tools(index)，表里就只有检索工具
        :param event_log: 事件日志路径或 EventLogger。例如 Path("logs/coding-demo.events.jsonl")；不记录时为 None
        """
        self.name = name
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.model = model  # 有 query 方法的对象（真模型或 ScriptedModel）
        self.env = env  # 有 execute 方法的环境（真环境或 ScriptedEnvironment）
        self.trajectory_path = Path(trajectory_path) if trajectory_path else None
        self.event_log = event_log if isinstance(event_log, EventLogger) or event_log is None else EventLogger(event_log)
        self.policy = policy if policy is not None else PermissionPolicy(lambda _command: False)
        self.steps: int = 0
        # 历史从一条 system 消息开始
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self._steering: list[str] = []
        self._followups: list[str] = []
        # 钩子，方便测试
        self.after_query = None
        self._last_test_command = None
        self._test_fail_streak = 0
        if tools is None:
            self.tools = {
                "echo": ToolSpec(
                    name="echo",
                    description="Return the input text.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Text to echo",
                            }
                        },
                        "required": ["text"],
                        "additionalProperties": False,
                    },
                    handler=self._echo,
                    permission="allow",
                    read_only=True,
                ),
                **coding_tools(self.env, self.policy),
            }
        else:
            self.tools = dict(tools)

    @staticmethod
    def _echo(arguments: dict) -> str:
        """
        :param arguments: echo 的参数字典。例如 {"text": "hello"}
        """
        return str(arguments.get("text", ""))

    def _emit(self, event: str, **fields) -> None:
        """没有配置事件日志时什么都不写。

        :param event: 例如 "run_started"
        :param fields: 事件字段。例如 step=1, tool="read_file"
        """
        if self.event_log is None:
            return
        self.event_log.emit(event, **fields)

    def _run_tool(self, call: dict):
        """执行 tool_calls 里的一项。没登记的名字写成观察，不抛异常，也不写 exit。

        :param call: 一次工具调用。例如 {"id": "c1", "name": "echo", "arguments": {"text": "hello"}}
        """
        started = time.perf_counter()
        name = call.get("name") or ""
        call_id = call.get("id") or ""
        arguments = call.get("arguments") or {}
        self._emit(
            "tool_started",
            step=self.steps,
            tool=name,
            call_id=call_id,
            arguments=summarize_arguments(arguments),
        )
        spec = self.tools.get(name)
        if spec is None:
            text = _observation(name, "null", "未知工具", error="not_found", tool=name)
        else:
            problem = _validate_arguments(spec, arguments)
            if problem:
                text = _observation(name, "null", problem, error="invalid_argument", tool=name)
            elif not self._tool_allowed(spec, arguments):
                text = _observation(name, "null", "未获允许", error="denied", tool=name)
            else:
                command = str(arguments.get("command", "")).strip()
                if name == "run_tests" and self._repeat_blocked(command):
                    text = _observation(
                        command,
                        "null",
                        "同一测试命令已连续失败，请先检查错误原因或修改命令。",
                        error="repeated_failure",
                        tool="run_tests",
                    )
                else:
                    try:
                        text = spec.handler(arguments)
                    except Exception as exc:
                        text = _observation(name, "null", str(exc), error="tool_error", tool=name)
                    if name == "run_tests":
                        self._note_test_result(command, text)
        ok, summary = summarize_result(text)
        self._emit(
            "tool_finished" if ok else "tool_failed",
            step=self.steps,
            tool=name,
            call_id=call_id,
            ok=ok,
            result_summary=summary,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        self._append_tool_result(call, text)

    def _repeat_blocked(self, command: str) -> bool:
        """同一条测试命令已经连续失败两次时，不再执行。

        :param command: 例如 "python -m pytest -q"
        """
        return bool(command) and command == self._last_test_command and self._test_fail_streak >= 2

    def _note_test_result(self, command: str, text: str) -> None:
        """成功则清零。失败则累计同一条命令的连续次数。

        :param command: 本次测试命令
        :param text: run_tests 返回的 JSON
        """
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return
        if payload.get("ok"):
            self._last_test_command = None
            self._test_fail_streak = 0
            return
        if command == self._last_test_command:
            self._test_fail_streak += 1
        else:
            self._last_test_command = command
            self._test_fail_streak = 1

    def _append_tool_result(self, call: dict, text: str) -> None:
        """
        :param call: 一次工具调用。例如 {"id": "c1", "name": "echo", "arguments": {"text": "hello"}}
        :param text: 工具返回的字符串。例如 "hello"
        """
        self.messages.append({
            "role": "tool",
            "name": call["name"],
            "tool_call_id": call["id"],
            "content": text,
        })

    def _tool_allowed(self, spec: ToolSpec, arguments: dict) -> bool:
        """登记表上的 permission 在执行前统一检查。allow 直接通过，ask 交给 policy。

        :param spec: 当前工具。例如 echo 的 ToolSpec，permission 为 "allow"
        :param arguments: 已通过校验的参数。例如 {"text": "hello"}
        """
        if spec.permission == "deny":
            return False
        if spec.permission == "ask":
            target = arguments.get("path") or arguments.get("command") or spec.name
            return bool(self.policy.ask_fn(f"{spec.name} {target}"))
        return True

    @staticmethod
    def to_model_messages(messages: list[dict]):
        """丢掉 exit，role="tool" 会留给模型。

        :param messages: 客户端保存的历史。例如 [{"role": "user", "content": "echo hello"}, {"role": "tool", "name": "echo", "tool_call_id": "c1", "content": "hello"}, {"role": "exit", "content": "done"}]
        """
        return [m for m in messages if m.get("role") != "exit"]

    def add_messages(self, *messages: dict) -> None:
        """
        :param messages: 要追加的一条或多条消息。例如 {"role": "user", "content": "<observation>...</observation>"}
        """
        self.messages.extend(messages)

    def push_steering(self, text: str) -> None:
        """
        :param text: 下一次 query 之前插入的用户句子。例如 "顺便加测试"
        """
        self._steering.append(text)

    def push_followup(self, text: str) -> None:
        """
        :param text: 本轮 exit 之后再开一轮的用户句子。例如 "再写一个测试"
        """
        self._followups.append(text)

    def _call_llm(self, messages: list[dict]) -> dict[str, Any]:
        """先排空 steering，再调用模型，返回整份回复。

        :param messages: 当前历史，调用处传入的是 self.messages。例如 [{"role": "system", "content": "..."}, {"role": "user", "content": "echo hello"}]
        :return: 旧剧本例如 {"role": "assistant", "content": "done"}。工具调用例如 {"role": "assistant", "content": "我先回显", "tool_calls": [{"id": "c1", "name": "echo", "arguments": {"text": "hello"}}]}
        """
        # # model.query 返回 {"role": "assistant", "content": "..."}，取 content
        # reply = self.model.query(messages)
        while self._steering:
            text = self._steering.pop(0)
            self.messages.append({"role": "user", "content": text})
        reply = self.model.query(self.to_model_messages(messages), tools=self.tool_schemas())
        if self.after_query is not None:
            self.after_query(self)
        return reply

    def tool_schemas(self) -> list[dict]:
        """把当前登记表转成供应商要的 tools 列表。循环不认识具体工具名。

        :return: 例如 [{"type": "function", "function": {"name": "echo", "description": "Return the input text.", "parameters": {"type": "object"}}}]
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self.tools.values()
        ]

    def _append_assistant_message(self, reply: dict) -> None:
        """把助手回复写进历史。有工具调用时一并保存，后面的 role=tool 才有前置消息。

        :param reply: 内部格式。例如 {"role": "assistant", "content": "我先读取", "tool_calls": [{"id": "call_1", "name": "read_file", "arguments": {"path": "hello.py"}}]}
        """
        message = {
            "role": reply.get("role", "assistant"),
            "content": reply.get("content") or "",
        }
        if reply.get("tool_calls"):
            message["tool_calls"] = reply["tool_calls"]
        self.messages.append(message)

    def step(self):
        self._emit("model_requested", step=self.steps)
        reply = self._call_llm(self.messages)
        calls = reply.get("tool_calls") or []
        self._emit(
            "model_replied",
            step=self.steps,
            tool_calls=[call.get("name") for call in calls],
        )
        self._append_assistant_message(reply)
        if calls:
            for call in calls:
                self._run_tool(call)
            return
        text = (reply.get("content") or "").strip()
        if text:
            self.messages.append({"role": "exit", "content": text})
            return
        raise FormatError({"role": "user", "content": FORMAT_ERROR})

    def save_trajectory(self) -> None:
        if self.trajectory_path is None:
            return
        save_trajectory(self.trajectory_path, self.steps, self.messages)

    def run(self, task):
        """
        :param task: 用户任务，会写成第一条 user 消息。例如 "echo hello"
        :return: RunResult。例如 RunResult(status="ok", final_text="done", steps=1, messages=self.messages)
        """
        # 开头追加任务。steering 和 follow-up 会在循环中再追加 user 消息。
        self.messages.append({"role": "user", "content": task})
        self.steps = 0
        self._last_test_command = None
        self._test_fail_streak = 0
        status = "ok"
        self._emit("run_started", task=clip_text(str(task)))

        try:
            while True:
                try:
                    if self.messages[-1]["role"] == "exit":
                        if self._followups and not self._steering:
                            text = self._followups.pop(0)
                            self.messages.append({"role": "user", "content": text})
                        elif not self._steering:
                            break
                    # 下一次 query 之前检查：步数已用尽就停，这次不再调用模型
                    if self.steps >= self.max_iterations:
                        status = "max_steps"
                        raise LimitsExceeded({"role": "exit", "content": MAX_STEPS_TEXT})
                    self.steps += 1
                    self.step()
                except InterruptAgentFlow as exc:
                    self.add_messages(*exc.messages)
                finally:
                    self.save_trajectory()

            final_text = self.messages[-1]["content"]
            return RunResult(
                status=status,
                final_text=final_text,
                steps=self.steps,
                messages=self.messages,
            )
        finally:
            self._emit("run_finished", status=status, steps=self.steps)


class DefaultAgent(Agent):
    """作业约定的构造方式：模型、环境，以及步数上限和轨迹路径。"""

    def __init__(self, model, env, *, max_steps: int = 8, trajectory_path=None, policy=None, tools=None,
                 name: str = "agent",
                 system_prompt: str = "请通过已注册工具读取、搜索、修改代码和运行测试。任务完成后直接返回最终说明，不要输出 Markdown 代码块来模拟工具调用。",
                 event_log=None):
        """
        :param model: 例如 ScriptedModel(["done"]) 或 OpenAICompatModel.from_env()
        :param env: 例如 LocalEnvironment(Path(".")) 或 ScriptedEnvironment()
        :param max_steps: 最多调用模型的次数。例如 8
        :param trajectory_path: 例如 Path("traj.jsonl")；不记录时为 None
        :param policy: 例如 PermissionPolicy(lambda command: False)
        :param tools: 不传时登记 coding 工具。例如 rag_tools(index)
        :param name: 例如 "agent"
        :param system_prompt: 例如 "请通过已注册工具读取、搜索、修改代码和运行测试。"
        :param event_log: 例如 Path("logs/coding-demo.events.jsonl")。不传时不写事件
        """
        super().__init__(name, system_prompt, max_steps, model, env, trajectory_path=trajectory_path, policy=policy,
                         tools=tools, event_log=event_log)


def _validate_arguments(spec: ToolSpec, arguments) -> str:
    """按 ToolSpec.parameters 检查必填项和类型。通过时返回空字符串。

    :param spec: 当前工具。例如 echo 的 ToolSpec
    :param arguments: 模型给出的参数。例如 {"text": "hello"}
    :return: 问题说明。例如 "缺少参数 text"。没有问题时是 ""
    """
    if not isinstance(arguments, dict):
        return "参数必须是对象"
    schema = spec.parameters or {}
    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    for key in required:
        if key not in arguments:
            return f"缺少参数 {key}"
    if schema.get("additionalProperties") is False:
        extra = [key for key in arguments if key not in properties]
        if extra:
            return "存在未声明的参数"
    for key, value in arguments.items():
        expected = (properties.get(key) or {}).get("type")
        if expected == "string" and not isinstance(value, str):
            return f"参数 {key} 必须是字符串"
        if expected == "boolean" and not isinstance(value, bool):
            return f"参数 {key} 必须是布尔值"
        if expected == "integer" and not isinstance(value, int):
            return f"参数 {key} 必须是整数"
    return ""

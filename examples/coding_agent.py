"""手动跑一次真实 Coding Agent。pytest 不会执行这个文件。

在项目根目录准备 .env，再运行：

    python examples/coding_agent.py
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from agent_runtime.agent import DefaultAgent
from agent_runtime.environment import LocalEnvironment
from agent_runtime.llm import OpenAICompatModel
from agent_runtime.permissions import PermissionPolicy
from agent_runtime.tools.registry import coding_tools

PROMPT = """请修改 hello.py，让 add 函数返回 a + b + 1，并运行测试。

工作区里只有这两个文件：
- hello.py
- test_hello.py

测试命令必须使用：
python -m pytest test_hello.py -q

不要使用 python -m pytest -q，也不要省略测试文件名。
"""
WORKSPACE = Path(__file__).resolve().parent / "demo_workspace"
TRACE = ROOT / "examples" / "traces" / "coding_demo.txt"


def main() -> None:
    task = " ".join(sys.argv[1:]).strip() or PROMPT
    policy = PermissionPolicy(lambda command: True)
    env = LocalEnvironment(WORKSPACE, timeout=30)
    agent = DefaultAgent(
        OpenAICompatModel.from_env(),
        env,
        policy=policy,
        tools=coding_tools(env, policy),
        max_steps=12,
        event_log=ROOT / "logs" / ("coding-demo.events.jsonl" if task == PROMPT else "last-run.events.jsonl"),
    )
    result = agent.run(task)
    for message in result.messages:
        calls = message.get("tool_calls") or []
        if message["role"] == "assistant" and calls:
            names = ", ".join(call["name"] for call in calls)
            print(f"[step] assistant requested {names}")
        elif message["role"] == "tool":
            preview = message["content"].splitlines()[0]
            print(f"[tool] {message['name']} -> {preview}")
    print(f"[final] {result.final_text}")
    print(f"[status] {result.status} steps={result.steps}")
    trace = TRACE if task == PROMPT else TRACE.with_name("last_run.txt")
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text(_trace(task, result), encoding="utf-8")
    print(f"[trace] {trace}")


def _trace(task: str, result) -> str:
    """把一轮运行写成不含密钥的文本。成功的读文件和替换只记 success。"""
    lines = [
        "Task:",
        task.strip(),
        "",
        "Workspace:",
        "hello.py",
        "test_hello.py",
        "",
    ]
    step = 0
    pending = []
    for message in result.messages:
        calls = message.get("tool_calls") or []
        if message.get("role") == "assistant" and calls:
            if pending:
                lines.extend(pending)
                pending = []
            step += 1
            names = ", ".join(call["name"] for call in calls)
            lines.append(f"Step {step}:")
            lines.append(f"Assistant requested: {names}")
            lines.append("")
            lines.append("Tool result:")
        elif message.get("role") == "tool":
            lines.append(_tool_line(message))
            pending = [""]
    if pending:
        lines.extend(pending)
    lines.append("Final:")
    lines.append(result.final_text.strip())
    lines.append("")
    lines.append(f"status: {result.status}")
    lines.append(f"steps: {result.steps}")
    lines.append("")
    return "\n".join(lines)


def _tool_line(message: dict) -> str:
    name = message.get("name", "tool")
    content = message.get("content") or ""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return f"{name} -> success"
    if payload.get("ok"):
        output = (payload.get("output") or "").strip().splitlines()
        if output and ("passed" in output[-1] or "failed" in output[-1].lower()):
            return f"{name} -> {output[-1]}"
        return f"{name} -> success"
    return f"{name} -> {payload.get('error') or 'failed'}"


if __name__ == "__main__":
    main()

"""真实接口测试。默认的 pytest 不会收集它们。

在 projects/agent-runtime/.env 写好 LLM_BASE_URL、LLM_API_KEY、LLM_MODEL 后：

    python -m pytest -m live -q
"""
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from agent_runtime.agent import DefaultAgent
from agent_runtime.environment import LocalEnvironment
from agent_runtime.llm import OpenAICompatModel
from agent_runtime.permissions import PermissionPolicy
from agent_runtime.tools.registry import ToolSpec
from fakes import ScriptedEnvironment

pytestmark = pytest.mark.live
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def live_model():
    """从项目根目录的 .env 创建客户端。缺配置时跳过，不打印密钥。"""
    load_dotenv(ROOT / ".env")
    missing = [name for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL") if not os.environ.get(name)]
    if missing:
        pytest.skip("missing " + ", ".join(missing))
    return OpenAICompatModel.from_env()


def _echo_tools():
    return {
        "echo": ToolSpec(
            name="echo",
            description="Return the input text.",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            handler=lambda arguments: str(arguments.get("text", "")),
            permission="allow",
            read_only=True,
        )
    }


def test_live_query_returns_assistant_text(live_model):
    result = live_model.query([
        {"role": "user", "content": "Reply with the single word pong."},
    ])
    assert result["role"] == "assistant"
    assert result["content"].strip()


def test_live_echo_result_comes_back(live_model):
    result = DefaultAgent(
        live_model,
        ScriptedEnvironment(),
        tools=_echo_tools(),
        max_steps=4,
    ).run("Call the echo tool once with text pong. After the tool result, reply with exactly pong.")

    tool = next(message for message in result.messages if message.get("role") == "tool")
    assert tool["name"] == "echo"
    assert "pong" in tool["content"]
    assert result.status == "ok"
    assert "pong" in result.final_text.lower()


def test_live_read_file_returns_workspace_text(live_model, tmp_path):
    (tmp_path / "hello.py").write_text("VALUE = 42\n", encoding="utf-8")
    result = DefaultAgent(
        live_model,
        LocalEnvironment(tmp_path),
        max_steps=4,
    ).run("Use read_file on hello.py and reply with the exact integer assigned to VALUE.")

    blob = "\n".join(message["content"] for message in result.messages)
    assert "VALUE = 42" in blob
    assert result.status == "ok"
    assert "42" in result.final_text


def test_live_str_replace_changes_return(live_model, tmp_path):
    file = tmp_path / "hello.py"
    file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    result = DefaultAgent(
        live_model,
        LocalEnvironment(tmp_path),
        policy=PermissionPolicy(lambda command: True),
        max_steps=6,
    ).run(
        "Use str_replace once. In hello.py, replace the exact text 'return a + b' "
        "with 'return a + b + 1'. Do not run tests. Then say done."
    )

    assert file.read_text(encoding="utf-8") == "def add(a, b):\n    return a + b + 1\n"
    assert result.status == "ok"

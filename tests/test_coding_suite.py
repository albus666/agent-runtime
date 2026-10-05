from agent_runtime.agent import DefaultAgent
from evals.coding_suite import run_suite
from fakes import ScriptedEnvironment
from test_tool_calls import RecordingModel


def test_coding_suite_passes():
    results = run_suite()
    assert [item["name"] for item in results] == [
        "读取返回值",
        "搜索常量",
        "修改函数",
        "修改并测试",
        "替换失败后重读",
        "拒绝越界路径",
        "测试超时后继续",
        "测试失败后继续",
    ]
    assert [item["ok"] for item in results] == [True] * 8


def test_missing_required_argument_is_invalid(tmp_path):
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "读文件",
            "tool_calls": [
                {"id": "c1", "name": "read_file", "arguments": {}},
            ],
        },
        "做完了",
    ])
    from agent_runtime.environment import LocalEnvironment

    result = DefaultAgent(model, LocalEnvironment(tmp_path)).run("读文件")
    blob = "\n".join(message["content"] for message in result.messages)
    assert '"error": "invalid_argument"' in blob
    assert "缺少参数 path" in blob
    assert result.status == "ok"


def test_non_test_command_is_not_executed():
    model = RecordingModel([
        {
            "role": "assistant",
            "content": "随便执行",
            "tool_calls": [
                {"id": "c1", "name": "run_tests", "arguments": {"command": "echo hello"}},
            ],
        },
        "做完了",
    ])
    env = ScriptedEnvironment()
    result = DefaultAgent(model, env).run("执行 echo")
    blob = "\n".join(message["content"] for message in result.messages)
    assert "只允许执行测试命令" in blob
    assert env.history == []
    assert result.status == "ok"

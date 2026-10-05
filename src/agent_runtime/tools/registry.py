from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolSpec:
    """已登记的一个工具。

    例如 ToolSpec(name="echo", description="Return the input text.", parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False}, handler=Agent._echo, permission="allow", read_only=True)。

    * name：工具名。例如 "echo"
    * description：给模型看的说明。例如 "Return the input text."
    * parameters：JSON Schema。例如 {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
    * handler：执行函数。例如 Agent._echo，入参是 arguments 字典，返回字符串
    * permission："allow" 或 "ask"。例如 "allow"
    * read_only：是否只读。例如 True
    """
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    permission: str = "allow"   # allow / ask / deny
    read_only: bool = True


def coding_tools(env, policy) -> dict[str, ToolSpec]:
    """登记文件工具。循环只按名字查找，不在这里写调用逻辑。

    :param env: 提供 workspace 的环境。例如 LocalEnvironment(tmp_path)
    :param policy: 写入前询问的权限。例如 PermissionPolicy(lambda command: False)
    :return: 以工具名为键的表，含 read_file、grep、str_replace、run_tests
    """
    from .grep import tool as grep_tool
    from .read_file import tool as read_file_tool
    from .run_tests import tool as run_tests_tool
    from .str_replace import tool as str_replace_tool

    specs = [
        read_file_tool(env),
        grep_tool(env),
        str_replace_tool(env, policy),
        run_tests_tool(env, policy),
    ]
    return {spec.name: spec for spec in specs}
# example_tools: dict[str, ToolSpec] = {
#     "echo": ToolSpec(
#         name="echo",
#         description="Return the input text.",
#         parameters={
#             "type": "object",
#             "properties": {
#                 "text": {
#                     "type": "string",
#                     "description": "Text to echo",
#                 }
#             },
#             "required": ["text"],
#             "additionalProperties": False,
#         },
#         handler=self._echo,
#         permission="allow",
#         read_only=True,
#     )
# }

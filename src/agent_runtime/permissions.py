class PermissionPolicy:
    """命令权限。具体用法例如 PermissionPolicy(lambda command: False)。"""

    def __init__(self, ask_fn):
        """
        :param ask_fn: 遇到重定向时是否允许的函数。例如 lambda command: False。这里要传入函数，不是 True 或 False
        """
        self.ask_fn = ask_fn

    def decide(self, command: str) -> str:
        """
        :param command: 待判断的 shell 命令。例如 "echo hello" 得到 "allow"，"rm a.txt" 得到 "deny"，"echo hi > a.txt" 交给 ask_fn
        :return: "allow" 或 "deny"
        """
        if ".." in command or command.startswith(("rm", "del", "format", "shutdown")):
            return "deny"
        if ">" in command:
            return "allow" if self.ask_fn(command) else "deny"
        return "allow"

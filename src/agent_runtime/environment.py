import subprocess
from pathlib import Path


class LocalEnvironment:
    """本机工作区。例如 LocalEnvironment(Path("."))，测试里常用 LocalEnvironment(tmp_path)。"""

    def __init__(self, workspace: str | Path, *, timeout: int | float = 2, max_output: int = 4000):
        """
        :param workspace: 工作区目录。例如 Path("workspace") 或 pytest 的 tmp_path
        :param timeout: 单条命令的秒数上限。例如 2
        :param max_output: 保留的输出字符数。例如 4000，超出后末尾是 "\\n[truncated]"
        """
        self.workspace = Path(workspace)
        self.timeout = timeout
        self.max_output = max_output
        self._require_workspace()

    def _require_workspace(self) -> None:
        if not self.workspace.is_dir():
            raise FileNotFoundError(f"Workspace {self.workspace} does not exist")

    def execute(self, command: str) -> dict:
        """
        :param command: 在 workspace 里执行的命令。例如 "echo hello"
        :return: 例如 {"output": "hello\\n", "returncode": 0}
        """
        try:
            completed = subprocess.run(
                command,
                shell=True,
                timeout=self.timeout,
                cwd=self.workspace,
                capture_output=True,
                text=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(str(exc)) from exc

        output = completed.stdout
        if len(output) > self.max_output:
            output = output[:self.max_output] + "\n[truncated]"
        return {"output": output, "returncode": completed.returncode}

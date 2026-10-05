class InterruptAgentFlow(Exception):
    """step 里可恢复的中断。run 只接住这一类，并把 messages 追加进历史。

    具体类例如 FormatError、LimitsExceeded、ActionTimeout。
    """

    def __init__(self, *messages: dict):
        """
        :param messages: 追加进历史的消息。例如 {"role": "exit", "content": "stopped: max_steps reached"}，或 {"role": "user", "content": "Expected tool calls or a non-empty final answer."}
        """
        super().__init__(messages[0]["content"] if messages else "interrupt")
        self.messages = list(messages)


class FormatError(InterruptAgentFlow):
    pass


class LimitsExceeded(InterruptAgentFlow):
    pass


class ActionTimeout(InterruptAgentFlow):
    pass


class ModelRequestError(InterruptAgentFlow):
    """模型请求在有限次重试后仍然失败。run 会把说明写回历史并继续。"""

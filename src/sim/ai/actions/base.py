from abc import ABC, abstractmethod


class Action(ABC):
    """全アクション共通: JSON の params を self.params にマージして保持する。"""

    DEFAULT_PARAMS: dict = {}

    def __init__(self, **params):
        self.completed = False
        self.params = {**self.DEFAULT_PARAMS, **params}

    @abstractmethod
    def execute(self, creature) -> bool:
        pass

    def is_completed(self) -> bool:
        return self.completed

    def calculate_utility(self, creature) -> float:
        return 0.5

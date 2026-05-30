from abc import ABC, abstractmethod


class Action(ABC):
    """全アクション共通。JSON 由来は from_config、テスト等は __init__ + DEFAULT_PARAMS マージ。"""

    DEFAULT_PARAMS: dict = {}

    def __init__(self, **params):
        self.completed = False
        config_only = params.pop("_use_config_only", False)
        if config_only:
            self.params = dict(params)
        else:
            self.params = {**self.DEFAULT_PARAMS, **params}

    @classmethod
    def from_config(cls, params: dict | None, *, source: str = ""):
        """種 JSON / reproduction_profiles から生成。欠落キーはエラー。"""
        from src.sim.ai.action_config import require_action_params

        resolved = require_action_params(cls, params, source=source)
        return cls(_use_config_only=True, **resolved)

    @abstractmethod
    def execute(self, creature) -> bool:
        pass

    def is_completed(self) -> bool:
        return self.completed

    def calculate_utility(self, creature) -> float:
        return 0.5

"""年齢・寿命・自然死判定を担当するマネージャ。"""
from typing import Any, Dict, Optional


class LifeCycleManager:
    """
    ライフステージ閾値（dict）の保持と自然死判定。
    creature.life_cycle.get("mature") 等の後方互換のため dict 風 API を提供する。
    """

    def __init__(self, owner: Any, stages: Dict) -> None:
        self.owner = owner
        self._stages = dict(stages)

    def get(self, key: str, default=None):
        return self._stages.get(key, default)

    def __bool__(self) -> bool:
        return bool(self._stages)

    def update(self) -> bool:
        """
        寿命到達で自然死。
        Returns:
            True なら update ループを打ち切る（become_corpse 済み）。
        """
        death_age = self._stages.get("death")
        # death: -1 は時間経過では死なない（不老）
        if death_age is None or int(death_age) < 0:
            return False
        if self.owner.age < int(death_age):
            return False

        self.owner.hp = 0
        self.owner.become_corpse(cause="lifespan")
        return True


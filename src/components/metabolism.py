"""代謝・成長・空腹による HP 影響を担当するコンポーネント（データ + 更新ロジック）。"""
from typing import Any

from src.utils.creature_helpers import current_size, satiety_ratio


class MetabolismComponent:
    """満腹度の消費、成長、空腹時の HP ダメージを処理する。"""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def update(self) -> bool:
        """
        1 ティック分の代謝を適用する。
        Returns:
            True なら HP が尽きて死骸化が必要（呼び出し側で become_corpse を実行）。
        """
        self.apply_growth()
        self._apply_metabolism()
        return self.owner.hp <= 0

    def apply_growth(self) -> None:
        """満腹度に応じて base_size を max_size まで自動成長（Action とは独立）。"""
        owner = self.owner
        traits = owner.traits
        max_size = float(traits.get("max_size", traits["base_size"]))
        size = current_size(owner)
        if size >= max_size:
            return

        growth_rate = float(traits.get("growth_rate", 0.0))
        if growth_rate <= 0:
            return

        delta = growth_rate * satiety_ratio(owner)
        traits["base_size"] = min(max_size, size + delta)

    def scale_size(self, factor: float) -> None:
        """traits.base_size を倍率で変更（分裂後の親縮小など）。"""
        traits = self.owner.traits
        traits["base_size"] = float(traits["base_size"]) * factor

    def _apply_metabolism(self) -> None:
        owner = self.owner
        owner.satiety -= owner.traits["metabolism_rate"]

        if owner.satiety < 0:
            owner.hp += owner.satiety * 0.12
            owner.satiety = 0

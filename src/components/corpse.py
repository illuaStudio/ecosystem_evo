"""死骸化・分解・バイオマス管理を担当するコンポーネント。"""
from typing import Any


class CorpseComponent:
    """死亡後の残存バイオマスと自然分解、マナ還元を処理する。"""

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.remaining_biomass = 0.0
        self.initial_biomass = 0.0

    def update(self) -> None:
        """死骸専用: 自然分解でバイオマス減少とマナ還元（アクションなし）。"""
        if self.remaining_biomass <= 0:
            return

        owner = self.owner
        size = float(owner.traits.get("base_size", 9.0))
        decompose_amount = size * 0.018
        self.remaining_biomass -= decompose_amount

        world = owner.world
        if world:
            world.return_mana_from_decomposition(
                decompose_amount * 0.65, owner.pos[0], owner.pos[1]
            )

        if self.remaining_biomass <= 0:
            self.remaining_biomass = 0.0
            if world:
                world.return_mana_from_decomposition(
                    15.0, owner.pos[0], owner.pos[1]
                )

    def become_corpse(self) -> None:
        """死亡→死骸化。残存バイオマスをサイズ・栄養に比例して設定。"""
        owner = self.owner
        if not owner.alive and self.initial_biomass > 0:
            return

        owner.alive = False
        owner.hp = 0
        size = float(owner.traits.get("base_size", 9.0))
        biomass = owner.max_satiety * 0.75 + size * 2.2
        self.remaining_biomass = biomass
        self.initial_biomass = biomass

    def biomass_ratio(self) -> float:
        """残存バイオマスの割合（1.0=死亡直後, 0.0=消滅直前）"""
        if self.initial_biomass <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining_biomass / self.initial_biomass))

    def is_depleted(self) -> bool:
        return self.remaining_biomass <= 0

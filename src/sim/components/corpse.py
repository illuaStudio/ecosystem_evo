"""死骸化・分解・バイオマス管理を担当するコンポーネント。"""
from typing import Any

from src.sim.utils.position_helpers import entity_xy


class CorpseComponent:
    """死亡後の残存バイオマスと自然分解を処理する。"""

    DECOMPOSE_FRACTION_PER_DT = 0.00003

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.remaining_biomass = 0.0
        self.initial_biomass = 0.0

    def update(self, dt: float = 1.0) -> None:
        """死骸専用: 自然分解でバイオマス減少。"""
        if self.remaining_biomass <= 0:
            return

        owner = self.owner
        initial = max(float(self.initial_biomass), 1.0)
        rate = float(
            owner.traits.get("corpse_decompose_rate", self.DECOMPOSE_FRACTION_PER_DT)
        )
        decompose_amount = initial * rate * float(dt)
        decompose_amount = min(decompose_amount, self.remaining_biomass)
        self.remaining_biomass -= decompose_amount

        if self.remaining_biomass <= 0:
            self.remaining_biomass = 0.0

    def become_corpse(self, cause: str = "unknown") -> None:
        """死亡フラグとイベントのみ。バイオマス化は PostLife の convert_biomass step。"""
        owner = self.owner
        if not owner.alive:
            return

        was_alive = owner.alive
        owner.alive = False
        owner.hp = 0

        if was_alive and owner.world is not None:
            owner.world.on_creature_became_corpse(owner)
            from src.sim.emitters import emit_death
            from src.sim.events import DeathCause

            death_cause: DeathCause = cause  # type: ignore[assignment]
            emit_death(owner.world, owner, cause=death_cause)

    def biomass_ratio(self) -> float:
        if self.initial_biomass <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining_biomass / self.initial_biomass))

    def is_depleted(self) -> bool:
        return self.remaining_biomass <= 0

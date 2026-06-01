"""死亡フラグ・死亡イベント・（死骸個体ルート用の）残留量と分解。

死後のレシピ（ドロップ・削除等）は PostLife / death_policy のパーツが担当。
"""
from typing import Any

from src.sim.utils.position_helpers import entity_xy


class CorpseComponent:
    """死亡後の残留量と自然分解。"""

    DECOMPOSE_FRACTION_PER_DT = 0.00003

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.remaining_mass = 0.0
        self.initial_mass = 0.0

    def update(self, dt: float = 1.0) -> None:
        if self.remaining_mass <= 0:
            return

        owner = self.owner
        initial = max(float(self.initial_mass), 1.0)
        rate = float(
            owner.traits.get("corpse_decay_rate", self.DECOMPOSE_FRACTION_PER_DT)
        )
        decompose_amount = initial * rate * float(dt)
        decompose_amount = min(decompose_amount, self.remaining_mass)
        self.remaining_mass -= decompose_amount

        if self.remaining_mass <= 0:
            self.remaining_mass = 0.0

    def become_corpse(self, cause: str = "unknown") -> None:
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

    def fill_ratio(self) -> float:
        if self.initial_mass <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining_mass / self.initial_mass))

    def is_depleted(self) -> bool:
        return self.remaining_mass <= 0

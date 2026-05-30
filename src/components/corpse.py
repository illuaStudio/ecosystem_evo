"""死骸化・分解・バイオマス管理を担当するコンポーネント。"""
from typing import Any

from src.utils.position_helpers import entity_xy


class CorpseComponent:
    """死亡後の残存バイオマスと自然分解、マナ還元を処理する。"""

    # initial_biomass に対する分解率（sim 時間 dt=1 あたり）。0.00003 ≈ 実時間数分規模。
    DECOMPOSE_FRACTION_PER_DT = 0.00003
    MANA_YIELD_RATIO = 0.65
    DEPLETION_MANA_BONUS = 15.0

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.remaining_biomass = 0.0
        self.initial_biomass = 0.0

    def update(self, dt: float = 1.0) -> None:
        """死骸専用: 自然分解でバイオマス減少とマナ還元（アクションなし）。"""
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

        world = owner.world
        if world and decompose_amount > 0:
            ox, oy = entity_xy(owner)
            world.mana_layer.return_from_decomposition(
                decompose_amount * self.MANA_YIELD_RATIO, ox, oy
            )

        if self.remaining_biomass <= 0:
            self.remaining_biomass = 0.0
            if world:
                ox, oy = entity_xy(owner)
                world.mana_layer.return_from_decomposition(
                    self.DEPLETION_MANA_BONUS, ox, oy
                )

    def become_corpse(self, cause: str = "unknown") -> None:
        """死亡→死骸化。残存バイオマスをサイズ・栄養に比例して設定。"""
        owner = self.owner
        if not owner.alive and self.initial_biomass > 0:
            return

        was_alive = owner.alive
        owner.alive = False
        owner.hp = 0
        size = float(owner.traits.get("base_size", 9.0))
        biomass = size * 200
        self.remaining_biomass = biomass
        self.initial_biomass = biomass

        if was_alive and owner.world is not None:
            from src.sim.emitters import emit_death
            from src.sim.events import DeathCause

            death_cause: DeathCause = cause  # type: ignore[assignment]
            emit_death(owner.world, owner, cause=death_cause)

    def biomass_ratio(self) -> float:
        """残存バイオマスの割合（1.0=死亡直後, 0.0=消滅直前）"""
        if self.initial_biomass <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining_biomass / self.initial_biomass))

    def is_depleted(self) -> bool:
        return self.remaining_biomass <= 0

# creature.py
import random

from entity import BaseEntity
from creature_renderer import CreatureRenderer
from creature_helpers import (
    current_size,
    get_life_stage,
    satiety_ratio,
)
from species import Species
from mind import UtilityMind


class Creature(BaseEntity):
    """原始的な単細胞生物基底クラス"""

    def __init__(self, x, y, species_name: str = "Amoeba"):
        super().__init__(x, y)

        self.species = Species.create(species_name)
        self.traits = self.species.traits
        self.life_cycle = dict(self.species.life_cycle)

        self.mind = UtilityMind(self.species.mind_data)
        self.current_action = None
        self.wander_angle = random.uniform(0, 360)

        self.max_hp = float(self.traits.get("max_hp", 100))
        self.hp = self.max_hp
        self.max_satiety = float(self.traits.get("max_satiety", 80))
        self.satiety = self.max_satiety
        self.remaining_biomass = 0.0
        self.initial_biomass = 0.0

        self.world = None
        self.last_pos = self.pos.copy()
        # 分裂・産卵・交配など繁殖系アクション共通のクールダウン（ティック）
        self.repro_cooldown = 0

    def get_current_speed(self) -> float:
        return float(self.traits.get("base_speed", 1.0))

    def get_current_vision(self) -> float:
        return self.traits["base_vision"]

    def get_current_size(self) -> float:
        return current_size(self)

    def get_life_stage(self) -> str:
        return get_life_stage(self.age, self.life_cycle)

    def _apply_growth(self) -> None:
        """満腹度に応じて base_size を max_size まで自動成長（Action とは独立）。"""
        max_size = float(self.traits.get("max_size", self.traits["base_size"]))
        size = current_size(self)
        if size >= max_size:
            return

        growth_rate = float(self.traits.get("growth_rate", 0.0))
        if growth_rate <= 0:
            return

        delta = growth_rate * satiety_ratio(self)
        self.traits["base_size"] = min(max_size, size + delta)

    def _check_natural_lifespan(self) -> bool:
        """life_cycle.death 到達で自然死。True なら update を打ち切る。"""
        death_age = self.life_cycle.get("death")
        if death_age is None or self.age < int(death_age):
            return False
        self.hp = 0
        self.become_corpse()
        return True

    def scale_size(self, factor: float) -> None:
        """traits.base_size を倍率で変更（分裂後の親縮小など）。"""
        self.traits["base_size"] = float(self.traits["base_size"]) * factor

    def set_repro_cooldown(self, ticks: int) -> None:
        self.repro_cooldown = max(0, int(ticks))

    def is_dead(self) -> bool:
        """生存中は HP 判定。死骸は残存バイオマスが尽きたら削除対象。"""
        if self.alive:
            return self.hp <= 0
        return self.remaining_biomass <= 0

    def biomass_ratio(self) -> float:
        """残存バイオマスの割合（1.0=死亡直後, 0.0=消滅直前）"""
        if self.initial_biomass <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining_biomass / self.initial_biomass))

    def become_corpse(self) -> None:
        """死亡→死骸化。残存バイオマスをサイズ・栄養に比例して設定。"""
        if not self.alive and self.initial_biomass > 0:
            return

        self.alive = False
        self.hp = 0
        size = float(self.traits.get("base_size", 9.0))
        biomass = self.max_satiety * 0.75 + size * 2.2
        self.remaining_biomass = biomass
        self.initial_biomass = biomass

    def _update_corpse(self) -> None:
        """死骸専用: 自然分解でバイオマス減少とマナ還元（アクションなし）。"""
        if self.remaining_biomass <= 0:
            return

        size = float(self.traits.get("base_size", 9.0))
        decompose_amount = size * 0.018
        self.remaining_biomass -= decompose_amount

        if self.world:
            self.world.return_mana_from_decomposition(decompose_amount * 0.65)

        if self.remaining_biomass <= 0:
            self.remaining_biomass = 0.0
            if self.world:
                self.world.return_mana_from_decomposition(15.0)

    def update(self):
        if not self.alive:
            self._update_corpse()
            return

        self.age += 1
        if self.repro_cooldown > 0:
            self.repro_cooldown -= 1
        self.last_pos = self.pos.copy()

        if self._check_natural_lifespan():
            return

        self._apply_growth()

        self.satiety -= self.traits["metabolism_rate"]

        if self.satiety < 0:
            self.hp += self.satiety * 0.12
            self.satiety = 0

        if self.hp <= 0:
            self.become_corpse()
            return

        self.current_action = self.mind.decide_next_action(self)
        self.current_action.execute(self)

        if self.world:
            self.pos[0] = max(30, min(self.world.width - 30, self.pos[0]))
            self.pos[1] = max(30, min(self.world.height - 30, self.pos[1]))

    def draw(self, screen, camera):
        CreatureRenderer.draw(self, screen, camera)


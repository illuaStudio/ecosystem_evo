# creature.py
import random

from entity import BaseEntity
from creature_renderer import CreatureRenderer
from species import Species
from mind import UtilityMind


class Creature(BaseEntity):
    """原始的な単細胞生物基底クラス"""

    def __init__(self, x, y, species_name: str = "Amoeba"):
        super().__init__(x, y)

        self.species = Species.create(species_name)
        self.traits = self.species.traits

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

    def get_current_speed(self) -> float:
        return self.traits.get("move_speed", self.traits.get("base_speed", 1.0))

    def get_current_vision(self) -> float:
        return self.traits["base_vision"]

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
        self.last_pos = self.pos.copy()

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

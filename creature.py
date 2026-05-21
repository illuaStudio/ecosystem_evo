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
        self.carcass_units = 0.0

        self.world = None
        self.last_pos = self.pos.copy()

    def get_current_speed(self) -> float:
        return self.traits.get("move_speed", self.traits.get("base_speed", 1.0))

    def get_current_vision(self) -> float:
        return self.traits["base_vision"]

    def is_dead(self) -> bool:
        if self.alive:
            return self.hp <= 0
        return self.carcass_units <= 0

    def update(self):
        if not self.alive:
            return

        self.age += 1
        self.last_pos = self.pos.copy()

        self.satiety -= self.traits["metabolism_rate"]

        if self.satiety < 0:
            self.hp += self.satiety * 0.12
            self.satiety = 0

        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            self.carcass_units = self.max_hp
            return

        self.current_action = self.mind.decide_next_action(self)
        self.current_action.execute(self)

        if self.world:
            self.pos[0] = max(30, min(self.world.width - 30, self.pos[0]))
            self.pos[1] = max(30, min(self.world.height - 30, self.pos[1]))

    def draw(self, screen, camera):
        CreatureRenderer.draw(self, screen, camera)

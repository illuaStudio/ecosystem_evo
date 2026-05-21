# creature.py
import pygame
import random
import math

from entity import BaseEntity
from creature_renderer import CreatureRenderer
from actions import WanderAction
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
        self.energy = self.traits.get("max_energy", 200.0) * 1.0
        
        # World管理
        self.last_pos = self.pos.copy()
        self.world = None

    def get_current_speed(self) -> float:
        return self.traits["base_speed"]

    def get_current_vision(self) -> float:
        return self.traits["base_vision"]

    def is_dead(self) -> bool:
        return super().is_dead() or self.energy <= 0

    def update(self):
        self.age += 1
        self.energy -= self.traits["energy_consume_base"]
        self.last_pos = self.pos.copy()

        # Action管理
        if self.current_action is None or self.current_action.is_completed():
            self.current_action = self.mind.decide_next_action(self)

        self.current_action.execute(self)

        # 境界制限
        if self.world:
            self.pos[0] = max(30, min(self.world.width - 30, self.pos[0]))
            self.pos[1] = max(30, min(self.world.height - 30, self.pos[1]))

    def draw(self, screen, camera):
        """描画処理"""
        CreatureRenderer.draw(self, screen, camera)
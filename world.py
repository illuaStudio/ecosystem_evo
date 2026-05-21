# world.py
import math
from typing import List, Tuple

from config import config
from creature_factory import CreatureFactory


class World:
    """ゲーム世界全体を管理"""
    
    def __init__(self, world_name: str = "Grassland"):
        # worldsフォルダからワールドデータを読み込み
        world_data = config.get_world(world_name)
        
        self.name = world_data["name"]
        self.display_name = world_data.get("display_name", self.name)
        self.width = world_data["world_width"]
        self.height = world_data["world_height"]
        self.background_color = world_data.get("background_color", [34, 60, 25])
        
        self.creatures: List = []
        self.obstacles = []
        self.resources = []

        # 初期生物生成
        factory = CreatureFactory()
        
        for _ in range(world_data.get("initial_amoeba", 0)):
            self.add_creature(factory.create("Amoeba", world=self))
        
        for _ in range(world_data.get("initial_predator", 0)):
            self.add_creature(factory.create("Predator", world=self))

    def add_creature(self, creature):
        """生物を世界に追加"""
        creature.world = self
        self.creatures.append(creature)

    def remove_creature(self, creature):
        if creature in self.creatures:
            self.creatures.remove(creature)

    def update(self):
        """全生物更新"""
        for creature in self.creatures[:]:   # コピーして安全に削除
            creature.update()
            if creature.is_dead():
                self.remove_creature(creature)

    def get_nearest_creature(self, pos: Tuple[float, float], species_name: str = None, 
                           max_dist: float = 9999.0, exclude=None):
        """最も近い対象を探す"""
        best = None
        min_dist = float('inf')
        
        for c in self.creatures:
            if c is exclude or not getattr(c, 'alive', True):
                continue
            if species_name and c.species.name != species_name:
                continue
            dist = math.hypot(c.pos[0] - pos[0], c.pos[1] - pos[1])
            if dist < min_dist and dist <= max_dist:
                min_dist = dist
                best = c
        return best

    def is_valid_position(self, x: float, y: float) -> bool:
        return (30 <= x <= self.width - 30 and 30 <= y <= self.height - 30)
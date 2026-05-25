"""初期エンティティの生成を担当。"""
from typing import TYPE_CHECKING, Dict

from src.config import config
from src.entities.creature_factory import CreatureFactory

if TYPE_CHECKING:
    from src.systems.world import World


class WorldSpawner:
    def __init__(self, world: "World") -> None:
        self._world = world

    def spawn_initial_entities(self, world_data: Dict) -> None:
        initial = dict(world_data.get("initial_entities", {}))

        if not initial:
            if world_data.get("initial_amoeba"):
                initial["Amoeba"] = world_data["initial_amoeba"]
            if world_data.get("initial_predator"):
                initial["Predator"] = world_data["initial_predator"]

        factory = CreatureFactory()
        for species_name, count in initial.items():
            n = int(count)
            if n <= 0:
                continue
            if species_name not in config.species:
                print(f"警告: 種族 '{species_name}' の JSON が無いためスキップします")
                continue
            for _ in range(n):
                self._world.add_creature(factory.create(species_name, world=self._world))

"""初期エンティティの生成を担当。"""
from dataclasses import replace
from typing import TYPE_CHECKING, Dict

from src.config import config
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.utils.spawn_placement import (
    SpawnPlacementResolver,
    expand_initial_spawns,
)

if TYPE_CHECKING:
    from src.sim.systems.world import World


class WorldSpawner:
    def __init__(self, world: "World") -> None:
        self._world = world
        self._resolver = SpawnPlacementResolver(world)

    def _pick_initial_position(self, entry):
        pos = self._resolver.pick(entry.anchor, entry.options)
        if pos is not None:
            return pos
        fallback = replace(
            entry.options,
            respect_zones=False,
            use_biome_weight=False,
            fallback_unrestricted=True,
            attempts=max(entry.options.attempts, 48),
        )
        return self._resolver.pick(entry.anchor, fallback)

    def spawn_initial_entities(self, world_data: Dict) -> None:
        entries = expand_initial_spawns(world_data, self._world)
        if not entries:
            return

        factory = CreatureFactory()
        for entry in entries:
            if entry.species not in config.species:
                print(f"警告: 種族 '{entry.species}' の JSON が無いためスキップします")
                continue
            for _ in range(entry.count):
                pos = self._pick_initial_position(entry)
                if pos is None:
                    print(
                        f"警告: 初期スポーン位置を決定できませんでした "
                        f"({entry.species}, anchor={entry.anchor.type})"
                    )
                    continue
                x, y = pos
                creature = factory.create(
                    entry.species, world=self._world, x=x, y=y
                )
                self._world.add_creature(creature, spawn_source="initial")

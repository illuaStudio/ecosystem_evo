"""combat/target 層のスモークテスト。"""
import unittest

from src.combat.target_query import (
    find_nearest_hostile_creature,
    find_nearest_spawn_node,
    iter_targets,
)
from src.combat.target_ref import TargetKind, TargetRef
from src.combat.target_damage import apply_damage_to_target
from src.entities.creature_factory import CreatureFactory
from src.systems.world import World


def _world():
    return World.from_json(
        {
            "name": "CombatTargetTest",
            "world_width": 1000,
            "world_height": 1000,
            "initial_entities": {},
            "population_limits": {
                "red_ant": 10,
                "red_ant_soldier": 6,
                "blue_ant": 10,
            },
            "colony": {
                "hole_max_hp": 100,
                "faction_species": {
                    "red_ant": ["red_ant", "red_ant_soldier"],
                    "blue_ant": ["blue_ant"],
                },
            },
        }
    )


class TestCombatTargets(unittest.TestCase):
    def test_iter_targets_creature_and_spawn_node(self):
        world = _world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        blue = factory.create("blue_ant", world=world, x=400, y=400)
        world.add_creature(red)
        world.add_creature(blue)

        kinds = set()
        for ref in iter_targets(world, (TargetKind.CREATURE, TargetKind.SPAWN_NODE)):
            kinds.add(ref.kind)
        self.assertIn(TargetKind.CREATURE, kinds)
        self.assertIn(TargetKind.SPAWN_NODE, kinds)

    def test_find_spawn_node_via_target_ref(self):
        world = _world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        blue = factory.create("blue_ant", world=world, x=200, y=200)
        world.add_creature(red)
        world.add_creature(blue)
        vanguard = factory.create("red_ant_soldier", world=world, x=150, y=150)
        world.add_creature(vanguard)

        ref = find_nearest_spawn_node(
            vanguard, ("blue_ant",), unrestricted=True
        )
        self.assertIsNotNone(ref)
        self.assertEqual(ref.kind, TargetKind.SPAWN_NODE)
        pair = ref.as_spawn_pair()
        self.assertIsNotNone(pair)

    def test_apply_damage_spawn_node(self):
        world = _world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        blue = factory.create("blue_ant", world=world, x=200, y=200)
        world.add_creature(red)
        world.add_creature(blue)
        soldier = factory.create("red_ant_soldier", world=world, x=190, y=190)
        world.add_creature(soldier)

        ref = find_nearest_spawn_node(
            soldier, ("blue_ant",), unrestricted=True
        )
        hole, nest = ref.as_spawn_pair()
        hp_before = hole.hp
        dealt = apply_damage_to_target(
            soldier, ref, 10.0, attacker_colony_id="red_ant"
        )
        self.assertEqual(dealt, 10.0)
        self.assertAlmostEqual(hole.hp, hp_before - 10.0)

    def test_find_hostile_creature(self):
        world = _world()
        factory = CreatureFactory()
        red_w = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(red_w)
        blue_w = factory.create("blue_ant", world=world, x=150, y=100)
        world.add_creature(blue_w)
        soldier = factory.create("red_ant_soldier", world=world, x=105, y=100)
        world.add_creature(soldier)

        ref = find_nearest_hostile_creature(
            soldier, ("blue_ant",), territory_only=True, exclude=soldier
        )
        self.assertIsNotNone(ref)
        self.assertIs(ref.creature, blue_w)


if __name__ == "__main__":
    unittest.main()

from src.game.colony_session import get_colony_orchestrator, try_get_colony_orchestrator

def colony(world):
    return get_colony_orchestrator(world)

"""combat/target 層のスモークテスト。"""
import unittest

from src.sim.combat.target_query import (
    find_nearest_hostile_creature,
    find_nearest_affiliation_access,
    iter_targets,
)
from src.sim.combat.target_ref import TargetKind, TargetRef
from src.sim.combat.target_damage import apply_damage_to_target
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from tests.sim.world_fixtures import RED_ANT_PROFILE, RIVAL_ANT_PROFILE, affiliation_settings, load_test_world


def _combat_affiliation_settings():
    red = dict(RED_ANT_PROFILE)
    red["nest_x"] = 100
    red["nest_y"] = 100
    blue = dict(RIVAL_ANT_PROFILE)
    blue["nest_x"] = 200
    blue["nest_y"] = 200
    return affiliation_settings(
        access_max_hp=100,
        profiles={"red_ant": red, "rival_ant": blue},
        affiliation_species={
            "red_ant": ["red_ant", "red_ant_soldier"],
            "rival_ant": ["rival_ant"],
        },
    )


def _world():
    return load_test_world(
        name="CombatTargetTest",
        population_limits={
            "red_ant": 10,
            "red_ant_soldier": 6,
            "rival_ant": 10,
        },
        affiliation=_combat_affiliation_settings(),
    )


class TestCombatTargets(unittest.TestCase):
    def test_standard_world_has_colony_objects(self):
        world = _world()
        ws = world.world_object_system
        self.assertTrue(ws.has_affiliation_root("red_ant"))
        self.assertTrue(ws.has_affiliation_root("rival_ant"))
        self.assertIsNotNone(colony(world).get_affiliation_root("red_ant"))
        self.assertIsNotNone(colony(world).get_affiliation_root("rival_ant"))

    def test_iter_targets_creature_and_colony_access(self):
        world = _world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        blue = factory.create("rival_ant", world=world, x=400, y=400)
        world.add_creature(red)
        world.add_creature(blue)

        kinds = set()
        for ref in iter_targets(
            world, (TargetKind.CREATURE, TargetKind.WORLD_OBJECT)
        ):
            kinds.add(ref.kind)
        self.assertIn(TargetKind.CREATURE, kinds)
        self.assertIn(TargetKind.WORLD_OBJECT, kinds)

    def test_find_colony_access_via_target_ref(self):
        world = _world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        blue = factory.create("rival_ant", world=world, x=200, y=200)
        world.add_creature(red)
        world.add_creature(blue)
        vanguard = factory.create("red_ant_soldier", world=world, x=150, y=150)
        world.add_creature(vanguard)

        ref = find_nearest_affiliation_access(
            vanguard, ("rival_ant",), unrestricted=True
        )
        self.assertIsNotNone(ref)
        self.assertEqual(ref.kind, TargetKind.WORLD_OBJECT)
        self.assertIsNotNone(ref.world_object)

    def test_apply_damage_colony_access(self):
        world = _world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        blue = factory.create("rival_ant", world=world, x=200, y=200)
        world.add_creature(red)
        world.add_creature(blue)
        soldier = factory.create("red_ant_soldier", world=world, x=190, y=190)
        world.add_creature(soldier)

        ref = find_nearest_affiliation_access(
            soldier, ("rival_ant",), unrestricted=True
        )
        access = ref.world_object
        self.assertIsNotNone(access)
        hp_before = access.hp
        dealt = apply_damage_to_target(
            soldier, ref, 10.0, attacker_affiliation_id="red_ant"
        )
        self.assertEqual(dealt, 10.0)
        self.assertAlmostEqual(access.hp, hp_before - 10.0)

    def test_world_object_target_from_instances(self):
        world = World.from_json(
            {
                "name": "ObjectCombatTest",
                "world_width": 1000,
                "world_height": 1000,
                "initial_entities": {},
                "instances": [
                    {
                        "id": "red_ant",
                        "layer": "affiliation_site",
                        "type": "affiliation_site",
                        "role": "root",
                        "x": 100,
                        "y": 100,
                    },
                    {
                        "id": "red_ant_access_main",
                        "layer": "affiliation_access",
                        "type": "affiliation_access",
                        "parent": "red_ant",
                        "x": 100,
                        "y": 100,
                    },
                    {
                        "id": "rival_ant",
                        "layer": "affiliation_site",
                        "type": "affiliation_site",
                        "role": "root",
                        "x": 500,
                        "y": 500,
                    },
                    {
                        "id": "rival_ant_access_main",
                        "layer": "affiliation_access",
                        "type": "affiliation_access",
                        "parent": "rival_ant",
                        "x": 500,
                        "y": 500,
                    },
                ],
                "affiliation": affiliation_settings(
                    access_max_hp=100,
                    affiliation_species={
                        "red_ant": ["red_ant", "red_ant_soldier"],
                        "rival_ant": ["rival_ant"],
                    },
                    profiles={
                        "red_ant": {"nest_x": 100, "nest_y": 100, "territory_radius": 180},
                        "rival_ant": {"nest_x": 500, "nest_y": 500, "territory_radius": 180},
                    },
                ),
            }
        )
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        blue = factory.create("rival_ant", world=world, x=500, y=500)
        world.add_creature(red)
        world.add_creature(blue)
        soldier = factory.create("red_ant_soldier", world=world, x=480, y=480)
        world.add_creature(soldier)

        ref = find_nearest_affiliation_access(
            soldier, ("rival_ant",), unrestricted=True
        )
        self.assertIsNotNone(ref)
        self.assertEqual(ref.kind, TargetKind.WORLD_OBJECT)

        access = ref.world_object
        hp_before = access.hp
        dealt = apply_damage_to_target(
            soldier, ref, 15.0, attacker_affiliation_id="red_ant"
        )
        self.assertEqual(dealt, 15.0)
        self.assertAlmostEqual(access.hp, hp_before - 15.0)

    def test_find_hostile_creature(self):
        world = _world()
        factory = CreatureFactory()
        red_w = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(red_w)
        blue_w = factory.create("rival_ant", world=world, x=150, y=100)
        world.add_creature(blue_w)
        soldier = factory.create("red_ant_soldier", world=world, x=105, y=100)
        world.add_creature(soldier)

        ref = find_nearest_hostile_creature(
            soldier, ("rival_ant",), territory_only=True, exclude=soldier
        )
        self.assertIsNotNone(ref)
        self.assertIs(ref.creature, blue_w)

if __name__ == "__main__":
    unittest.main()

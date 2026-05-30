"""SimBridge / SimCommand のテスト。"""
import unittest

from src.game.command_builder import (
    apply_mind_profile,
    apply_mind_profile_to_colony_caste,
    apply_mind_profile_to_species,
    apply_spawn_profile,
    spawn_creature,
)
from src.sim.bridge import SimBridge
from src.sim.commands import SetColonyCasteMind, SetCreatureMind, SetSpeciesMind, SpawnCreature
from src.sim.utils.caste_helpers import creature_matches_colony_caste, list_colony_caste_species
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.shelter.state import is_creature_sheltered
from src.sim.systems.world import World


def _world(**overrides) -> World:
    data = {
        "name": "BridgeTest",
        "world_width": 800,
        "world_height": 800,
        "initial_entities": {},
        "population_limits": {"red_ant": 20, "red_ant_queen": 3, "Spider": 10},
    }
    data.update(overrides)
    return World.from_json(data)


def _colony_world(**overrides) -> World:
    data = {
        "name": "CasteBridgeTest",
        "world_width": 800,
        "world_height": 800,
        "initial_entities": {},
        "population_limits": {
            "red_ant": 20,
            "red_ant_soldier": 10,
            "red_ant_vanguard": 10,
            "red_ant_queen": 3,
        },
        "colony": {
            "faction_species": {
                "red_ant": ["red_ant", "red_ant_soldier", "red_ant_vanguard"],
            },
        },
    }
    data.update(overrides)
    return World.from_json(data)


class TestColonyCasteMind(unittest.TestCase):
    def test_caste_species_resolution(self):
        world = _colony_world()
        self.assertEqual(
            list_colony_caste_species(world, "red_ant", "worker"),
            ("red_ant",),
        )
        self.assertEqual(
            list_colony_caste_species(world, "red_ant", "soldier"),
            ("red_ant_soldier",),
        )
        self.assertIn("red_ant_soldier", list_colony_caste_species(world, "red_ant", "combat"))
        self.assertIn("red_ant_vanguard", list_colony_caste_species(world, "red_ant", "combat"))

    def test_set_colony_caste_mind_workers_only(self):
        world = _colony_world()
        bridge = SimBridge(world)
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        soldier = factory.create("red_ant_soldier", world=world, x=110, y=100)
        world.add_creature(worker, spawn_source="initial")
        world.add_creature(soldier, spawn_source="initial")
        world.events.drain()

        wander = ({"name": "WanderAction", "weight": 9.0, "params": {}},)
        result = bridge.execute(
            SetColonyCasteMind(
                colony_id="red_ant",
                caste="worker",
                actions=wander,
                mode="replace",
            )
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.count, 1)
        self.assertEqual(worker.mind.action_defs[0]["name"], "WanderAction")
        self.assertNotEqual(soldier.mind.action_defs[0]["name"], "WanderAction")

    def test_set_colony_caste_mind_soldiers(self):
        world = _colony_world()
        bridge = SimBridge(world)
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        soldier = factory.create("red_ant_soldier", world=world, x=110, y=100)
        vanguard = factory.create("red_ant_vanguard", world=world, x=120, y=100)
        world.add_creature(worker, spawn_source="initial")
        world.add_creature(soldier, spawn_source="initial")
        world.add_creature(vanguard, spawn_source="initial")
        world.events.drain()

        patrol = ({"name": "NestPatrolAction", "weight": 5.0, "params": {}},)
        result = bridge.execute(
            SetColonyCasteMind(
                colony_id="red_ant",
                caste="combat",
                actions=patrol,
                mode="merge",
            )
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.count, 2)
        self.assertIn(soldier, result.creatures)
        self.assertIn(vanguard, result.creatures)
        self.assertNotIn(worker, result.creatures)
        for unit in (soldier, vanguard):
            names = [a["name"] for a in unit.mind.action_defs]
            self.assertIn("NestPatrolAction", names)

    def test_apply_mind_profile_to_colony_caste_helper(self):
        world = _colony_world()
        bridge = SimBridge(world)
        factory = CreatureFactory()
        for i in range(2):
            ant = factory.create("red_ant", world=world, x=100 + i, y=100)
            world.add_creature(ant, spawn_source="initial")
        world.events.drain()

        count = apply_mind_profile_to_colony_caste(
            bridge, "red_ant", "worker", "workers_only"
        )
        self.assertEqual(count, 2)
        for ant in world.creatures:
            if ant.species.name == "red_ant":
                self.assertEqual(
                    [a["name"] for a in ant.mind.action_defs],
                    ["ColonyReproduceAction"],
                )

    def test_other_colony_not_affected(self):
        world = World.from_json(
            {
                "name": "TwoColonies",
                "world_width": 800,
                "world_height": 800,
                "initial_entities": {},
                "population_limits": {"red_ant": 10, "blue_ant": 10},
                "colony": {
                    "faction_species": {
                        "red_ant": ["red_ant"],
                        "blue_ant": ["blue_ant"],
                    },
                },
            }
        )
        bridge = SimBridge(world)
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        blue = factory.create("blue_ant", world=world, x=500, y=500)
        world.add_creature(red, spawn_source="initial")
        world.add_creature(blue, spawn_source="initial")
        world.events.drain()

        wander = ({"name": "WanderAction", "weight": 1.0, "params": {}},)
        bridge.execute(
            SetColonyCasteMind(
                colony_id="red_ant",
                caste="worker",
                actions=wander,
                mode="replace",
            )
        )
        self.assertEqual(red.mind.action_defs[0]["name"], "WanderAction")
        self.assertNotEqual(blue.mind.action_defs[0]["name"], "WanderAction")


class TestSimBridge(unittest.TestCase):
    def test_spawn_at_coordinates(self):
        world = _world()
        bridge = SimBridge(world)
        result = bridge.execute(SpawnCreature(species="Spider", x=200, y=300, source="game"))
        self.assertTrue(result.ok)
        self.assertIsNotNone(result.creature)
        self.assertAlmostEqual(result.creature.position.x, 200)
        self.assertAlmostEqual(result.creature.position.y, 300)

    def test_spawn_random_position(self):
        world = _world()
        bridge = SimBridge(world)
        result = bridge.execute(SpawnCreature(species="Amoeba", source="game"))
        self.assertTrue(result.ok)
        c = result.creature
        self.assertGreaterEqual(c.position.x, 80)
        self.assertLessEqual(c.position.x, world.width - 80)

    def test_set_creature_mind_replace(self):
        world = _world()
        bridge = SimBridge(world)
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=100, y=100)
        world.add_creature(queen, spawn_source="initial")
        world.events.drain()

        apply_mind_profile(bridge, queen, "workers_only")
        names = [a["name"] for a in queen.mind.action_defs]
        self.assertEqual(names, ["ColonyReproduceAction"])

    def test_set_species_mind(self):
        world = _world()
        bridge = SimBridge(world)
        factory = CreatureFactory()
        for i in range(2):
            ant = factory.create("red_ant", world=world, x=100 + i, y=100)
            world.add_creature(ant, spawn_source="initial")
        world.events.drain()

        count = apply_mind_profile_to_species(
            bridge, "red_ant", "workers_only", mode="replace"
        )
        self.assertEqual(count, 2)
        for ant in world.creatures:
            names = [a["name"] for a in ant.mind.action_defs]
            self.assertIn("ColonyReproduceAction", names)

        profile_actions = (
            {"name": "WanderAction", "weight": 1.0, "params": {}},
        )
        result = bridge.execute(
            SetSpeciesMind(
                species_name="red_ant",
                actions=profile_actions,
                mode="merge",
            )
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.count, 2)
        for ant in result.creatures:
            names = [a["name"] for a in ant.mind.action_defs]
            self.assertIn("WanderAction", names)

    def test_set_species_mind_no_match(self):
        world = _world()
        bridge = SimBridge(world)
        count = apply_mind_profile_to_species(
            bridge, "nonexistent_species", "workers_only"
        )
        self.assertEqual(count, 0)

    def test_apply_spawn_profile_via_bridge(self):
        world = _world()
        bridge = SimBridge(world)
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen, spawn_source="initial")
        world.events.drain()

        apply_spawn_profile(bridge, queen)
        self.assertTrue(is_creature_sheltered(queen))
        self.assertEqual(
            [a["name"] for a in queen.mind.action_defs],
            ["ColonyReproduceAction"],
        )

    def test_spawn_creature_helper(self):
        world = _world()
        bridge = SimBridge(world)
        creature = spawn_creature(bridge, "Spider", x=50, y=60)
        self.assertIsNotNone(creature)
        self.assertEqual(creature.species.name, "Spider")

    def test_merge_mind_keeps_existing(self):
        world = _world()
        bridge = SimBridge(world)
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=100, y=100)
        world.add_creature(queen, spawn_source="initial")
        world.events.drain()
        apply_mind_profile(bridge, queen, "workers_only")

        extra = ({"name": "WanderAction", "weight": 0.1, "params": {}},)
        bridge.execute(
            SetCreatureMind(creature_id=id(queen), actions=extra, mode="merge")
        )
        names = [a["name"] for a in queen.mind.action_defs]
        self.assertIn("ColonyReproduceAction", names)
        self.assertIn("WanderAction", names)


if __name__ == "__main__":
    unittest.main()

"""女王の不老・MindPolicy・巣穴待機のテスト。"""
import unittest

from src.sim.ai.actions import ColonyReproduceAction
from src.sim.entities.creature_factory import CreatureFactory
from src.game.command_builder import apply_spawn_profile
from src.game.mind_policy import MindPolicy
from src.sim.bridge import SimBridge
from src.sim.shelter.state import is_creature_sheltered
from src.sim.systems.world import World
from tests.sim.world_fixtures import affiliation_settings


class TestQueenAndMindPolicy(unittest.TestCase):
    def test_queen_does_not_die_from_age(self):
        world = World.from_json(
            {
                "name": "QueenAgeTest",
                "world_width": 500,
                "world_height": 500,
                "initial_entities": {},
                "affiliation": affiliation_settings(),
            }
        )
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=100, y=100)
        world.add_creature(queen)

        queen.age = 999_999
        queen.life_cycle.update()
        self.assertTrue(queen.alive)
        self.assertGreater(queen.hp, 0)

    def test_queen_starts_sheltered_with_feed_only_profile(self):
        world = World.from_json(
            {
                "name": "QueenShelterTest",
                "world_width": 500,
                "world_height": 500,
                "initial_entities": {},
                "affiliation": affiliation_settings(),
            }
        )
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=100, y=100)
        world.add_creature(queen)
        apply_spawn_profile(SimBridge(world), queen)

        self.assertTrue(is_creature_sheltered(queen))
        names = [a["name"] for a in queen.mind.action_defs]
        self.assertEqual(names, ["FeedAtNestAction"])

    def test_mind_policy_swaps_reproduction_profile(self):
        world = World.from_json(
            {
                "name": "MindPolicyTest",
                "world_width": 500,
                "world_height": 500,
                "initial_entities": {},
                "affiliation": affiliation_settings(),
            }
        )
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=100, y=100)
        world.add_creature(queen)

        policy = MindPolicy()
        bridge = SimBridge(world)
        from src.game.command_builder import apply_mind_profile

        self.assertTrue(apply_mind_profile(bridge, queen, "workers_and_soldiers"))

        repro = next(
            a for a in queen.mind.action_defs if a["name"] == "ColonyReproduceAction"
        )
        offspring = repro["params"]["offspring"]
        species = {entry["species"] for entry in offspring}
        self.assertIn("red_ant_soldier", species)

        policy.reset_creature(queen)
        names = [a["name"] for a in queen.mind.action_defs]
        self.assertEqual(
            names,
            ["SeekShelterAction", "FeedAtNestAction", "WanderAction"],
        )

    def test_colony_reproduce_spawns_from_sheltered_queen(self):
        world = World.from_json(
            {
                "name": "QueenSpawnTest",
                "world_width": 500,
                "world_height": 500,
                "initial_entities": {},
                "population_limits": {"red_ant": 20, "red_ant_queen": 3},
                "affiliation": affiliation_settings(),
            }
        )
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen)
        bridge = SimBridge(world)
        apply_spawn_profile(bridge, queen)
        from src.game.command_builder import apply_mind_profile

        apply_mind_profile(bridge, queen, "workers_only")
        nest = world.nest_system.get_creature_nest(queen)

        self.assertTrue(is_creature_sheltered(queen))

        profile = MindPolicy().get_profile("workers_only") or {}
        params = next(
            a["params"]
            for a in profile["actions"]
            if a["name"] == "ColonyReproduceAction"
        )
        from src.sim.utils.affiliation_config_helpers import get_min_food_reserve

        nest.stored_food = get_min_food_reserve(world) + float(params["food_cost"]) + 10

        action = ColonyReproduceAction(**{**params, "spawn_cooldown": 0})
        member_species = [
            str(e["species"])
            for e in params.get("offspring", [])
            if e.get("species")
        ]
        before = world.nest_system.count_colony_members(nest.id, member_species)
        self.assertTrue(action.execute(queen))
        after = world.nest_system.count_colony_members(nest.id, member_species)
        self.assertEqual(after, before + 1)


if __name__ == "__main__":
    unittest.main()

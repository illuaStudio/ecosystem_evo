from src.game.colony_session import get_colony_orchestrator, try_get_colony_orchestrator

def colony(world):
    return get_colony_orchestrator(world)

"""女王の不老・MindPolicy・巣穴待機のテスト。"""
import unittest

from src.game.ai.reproduction_actions import AffiliationReproduceAction
from src.sim.entities.creature_factory import CreatureFactory
from src.game.command_builder import apply_spawn_profile
from src.game.mind_policy import MindPolicy
from src.game.sim_bridge_factory import make_sim_bridge
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
        apply_spawn_profile(make_sim_bridge(world), queen)

        self.assertTrue(is_creature_sheltered(queen))
        names = [a["name"] for a in queen.mind.action_defs]
        self.assertIn("FeedAtNestAction", names)
        self.assertIn("WanderAction", names)

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
        bridge = make_sim_bridge(world)
        from src.game.command_builder import apply_mind_profile

        self.assertTrue(apply_mind_profile(bridge, queen, "workers_and_soldiers"))

        repro = next(
            a for a in queen.mind.action_defs if a["name"] == "AffiliationReproduceAction"
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
        bridge = make_sim_bridge(world)
        apply_spawn_profile(bridge, queen)
        from src.game.command_builder import apply_mind_profile

        apply_mind_profile(bridge, queen, "workers_only")
        nest = colony(world).get_creature_affiliation_root(queen)

        self.assertTrue(is_creature_sheltered(queen))

        profile = MindPolicy().get_profile("workers_only") or {}
        params = next(
            a["params"]
            for a in profile["actions"]
            if a["name"] == "AffiliationReproduceAction"
        )
        from src.sim.utils.affiliation_config_helpers import get_min_storage_reserve

        nest.stored_mass = get_min_storage_reserve(world) + float(params["food_cost"]) + 10

        action = AffiliationReproduceAction(**{**params, "spawn_cooldown": 0})
        member_species = [
            str(e["species"])
            for e in params.get("offspring", [])
            if e.get("species")
        ]
        before = colony(world).count_affiliation_members(nest.id, member_species)
        self.assertTrue(action.execute(queen))
        after = colony(world).count_affiliation_members(nest.id, member_species)
        self.assertEqual(after, before + 1)


if __name__ == "__main__":
    unittest.main()

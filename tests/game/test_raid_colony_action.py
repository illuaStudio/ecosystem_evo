"""RaidColonyAction: unaffiliated raiders march on colony access (game layer)."""
import unittest

from src.game.ai.combat_actions import RaidColonyAction
from src.sim.combat.target_query import find_nearest_affiliation_access, vision_range
from src.sim.entities.creature_factory import CreatureFactory
from tests.sim.world_fixtures import RED_ANT_PROFILE, RIVAL_ANT_PROFILE, affiliation_settings, load_test_world


def _world():
    red = dict(RED_ANT_PROFILE)
    red["nest_x"] = 100
    red["nest_y"] = 100
    blue = dict(RIVAL_ANT_PROFILE)
    blue["nest_x"] = 200
    blue["nest_y"] = 200
    return load_test_world(
        name="RaidColonyTest",
        population_limits={"red_ant": 10, "rival_ant": 10},
        affiliation=affiliation_settings(
            access_max_hp=100,
            profiles={"red_ant": red, "rival_ant": blue},
            affiliation_species={
                "red_ant": ["red_ant", "red_ant_soldier"],
                "rival_ant": ["rival_ant"],
            },
        ),
    )


class TestRaidColonyAction(unittest.TestCase):
    def test_finds_player_nest_beyond_vision(self):
        world = _world()
        factory = CreatureFactory()
        enemy = factory.create("invader_ant", world=world, x=800, y=200)
        world.add_creature(enemy)

        capped = find_nearest_affiliation_access(
            enemy, ("red_ant",), unrestricted=True, max_distance=None
        )
        self.assertIsNone(capped)

        raid = RaidColonyAction(hostile_affiliation_ids=["red_ant"])
        ref = raid._find_colony_access(enemy)
        self.assertIsNotNone(ref)
        self.assertEqual(ref.affiliation_id, "red_ant")
        self.assertGreater(raid.calculate_utility(enemy), 0.0)

    def test_respects_finite_search_radius(self):
        world = _world()
        factory = CreatureFactory()
        enemy = factory.create("invader_ant", world=world, x=800, y=200)
        world.add_creature(enemy)
        vision = vision_range(enemy)

        raid = RaidColonyAction(
            hostile_affiliation_ids=["red_ant"],
            max_search_radius=vision,
        )
        self.assertIsNone(raid._find_colony_access(enemy))


if __name__ == "__main__":
    unittest.main()

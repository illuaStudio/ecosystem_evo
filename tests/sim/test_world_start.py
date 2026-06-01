from src.game.colony_session import get_colony_orchestrator, try_get_colony_orchestrator

def colony(world):
    return get_colony_orchestrator(world)

"""スタートワールド（1勢力・女王+働きアリ+極小虫）のスモークテスト。"""
import unittest

from src.config import config
from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES
from src.sim.systems.world import World


class TestWorldStart(unittest.TestCase):
    def test_world_spawns_single_affiliation(self):
        world = World()
        nests = list(colony(world).affiliation_roots.values())
        colony_ids = {n.affiliation_id for n in nests}
        self.assertEqual(colony_ids, {"red_ant"})
        self.assertEqual(len(nests), 1)

    def test_affiliation_species_single_faction(self):
        world = World()
        self.assertIn("red_ant", world.affiliation_species)
        self.assertNotIn("rival_ant", world.affiliation_species)
        self.assertNotIn("rival_ant", world.affiliation_species)
        self.assertIn("red_ant", world.affiliation_styles)

    def test_initial_population(self):
        world = World()
        queens = sum(1 for c in world.creatures if c.species.name == "red_ant_queen")
        workers = sum(1 for c in world.creatures if c.species.name == "red_ant")
        micro_fauna = sum(
            1 for c in world.creatures if c.species.name in DEFAULT_MICRO_FAUNA_SPECIES
        )
        self.assertEqual(queens, 1)
        self.assertEqual(workers, 2)
        self.assertEqual(micro_fauna, 20)
        self.assertEqual(len(world.creatures), 23)

    def test_species_still_in_config(self):
        self.assertIn("red_ant", config.species)
        self.assertIn("rival_ant", config.species)
        for name in DEFAULT_MICRO_FAUNA_SPECIES:
            self.assertIn(name, config.species)

    def test_spawn_system_configured(self):
        world = World()
        self.assertIsNotNone(world.spawn_system.ambient)
        self.assertEqual(
            tuple(world.spawn_system.species_pool),
            DEFAULT_MICRO_FAUNA_SPECIES,
        )
        self.assertGreater(len(world.spawn_system.emitters), 0)


if __name__ == "__main__":
    unittest.main()

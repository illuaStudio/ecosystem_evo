"""スタートワールド（1勢力・女王+働きアリ+アメーバ）のスモークテスト。"""
import unittest

from src.config import config
from src.sim.systems.world import World


class TestWorldStart(unittest.TestCase):
    def test_world_spawns_single_colony(self):
        world = World()
        nests = list(world.nest_system.nests.values())
        colony_ids = {n.colony_id for n in nests}
        self.assertEqual(colony_ids, {"red_ant"})
        self.assertEqual(len(nests), 1)

    def test_faction_species_single_faction(self):
        world = World()
        self.assertIn("red_ant", world.faction_species)
        self.assertNotIn("blue_ant", world.faction_species)
        self.assertNotIn("yellow_ant", world.faction_species)
        self.assertIn("red_ant", world.faction_styles)

    def test_initial_population(self):
        world = World()
        queens = sum(1 for c in world.creatures if c.species.name == "red_ant_queen")
        workers = sum(1 for c in world.creatures if c.species.name == "red_ant")
        amoebas = sum(1 for c in world.creatures if c.species.name == "Amoeba")
        self.assertEqual(queens, 1)
        self.assertEqual(workers, 2)
        self.assertEqual(amoebas, 20)
        self.assertEqual(len(world.creatures), 23)

    def test_species_still_in_config(self):
        self.assertIn("red_ant", config.species)
        self.assertIn("blue_ant", config.species)
        self.assertIn("Amoeba", config.species)


if __name__ == "__main__":
    unittest.main()

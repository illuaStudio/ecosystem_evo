"""赤・青・黄の3勢力ワールドのスモークテスト。"""
import unittest

from src.config import config
from src.sim.systems.world import World


class TestThreeFactions(unittest.TestCase):
    def test_world_spawns_three_colonies(self):
        world = World()
        nests = list(world.nest_system.nests.values())
        colony_ids = {n.colony_id for n in nests}
        self.assertEqual(colony_ids, {"red_ant", "blue_ant", "yellow_ant"})
        self.assertEqual(len(nests), 3)

    def test_faction_species_and_styles_configured(self):
        world = World()
        self.assertIn("red_ant", world.faction_species)
        self.assertIn("blue_ant", world.faction_species)
        self.assertIn("yellow_ant", world.faction_species)
        self.assertIn("red_ant", world.faction_styles)
        self.assertIn("blue_ant", world.faction_styles)
        self.assertIn("yellow_ant", world.faction_styles)

    def test_no_legacy_ant_species(self):
        self.assertNotIn("Ant", config.species)
        self.assertNotIn("EnemyAnt", config.species)
        self.assertIn("red_ant", config.species)
        self.assertIn("blue_ant", config.species)
        self.assertIn("yellow_ant", config.species)

    def test_initial_population_per_faction(self):
        world = World()
        for species in ("red_ant", "blue_ant", "yellow_ant"):
            alive = sum(1 for c in world.creatures if c.species.name == species)
            self.assertGreaterEqual(alive, 1, species)
        queens = sum(1 for c in world.creatures if c.species.name == "red_ant_queen")
        self.assertEqual(queens, 1)


if __name__ == "__main__":
    unittest.main()

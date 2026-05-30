"""生態表示 ON/OFF のユニットテスト。"""
import unittest

from src.client.species_visibility import SpeciesVisibilityManager
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World


class TestSpeciesVisibility(unittest.TestCase):
    def test_toggle_group_hides_species(self):
        world = World()
        vis = SpeciesVisibilityManager()
        vis.reset_for_world(world)

        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=100, y=100)
        amoeba = factory.create("Amoeba", world=world, x=200, y=100)

        self.assertTrue(vis.is_creature_visible(spider))
        vis.toggle_group("spider")
        self.assertFalse(vis.is_creature_visible(spider))
        self.assertTrue(vis.is_creature_visible(amoeba))

    def test_hotkey_toggle(self):
        vis = SpeciesVisibilityManager()
        vis.reset_for_world(World())
        self.assertTrue(vis.toggle_group_by_hotkey(ord("3")))
        self.assertFalse(vis.is_group_visible("blue_ant"))


if __name__ == "__main__":
    unittest.main()

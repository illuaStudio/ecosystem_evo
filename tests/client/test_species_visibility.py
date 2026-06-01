"""生態表示 ON/OFF のユニットテスト。"""
import unittest

from src.client.species_visibility import SpeciesVisibilityManager, VisibilityToggleRect
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World


class TestSpeciesVisibility(unittest.TestCase):
    def test_toggle_group_hides_species(self):
        world = World()
        vis = SpeciesVisibilityManager()
        vis.reset_for_world(world)

        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=100, y=100)
        amoeba = factory.create("springtail", world=world, x=200, y=100)

        self.assertTrue(vis.is_creature_visible(spider))
        vis.toggle_group("spider")
        self.assertFalse(vis.is_creature_visible(spider))
        self.assertTrue(vis.is_creature_visible(amoeba))

    def test_hotkey_toggle(self):
        vis = SpeciesVisibilityManager()
        vis.reset_for_world(World())
        self.assertTrue(vis.toggle_group_by_hotkey(ord("3")))
        self.assertFalse(vis.is_group_visible("spider"))

    def test_groups_for_world_filters_by_population_limits(self):
        world = World()
        world.population_limits = {"red_ant": 10, "Spider": 5}
        vis = SpeciesVisibilityManager()
        gids = [g[0] for g in vis.groups_for_world(world)]
        self.assertIn("red_ant", gids)
        self.assertIn("spider", gids)
        self.assertNotIn("micro_fauna", gids)

    def test_hit_test_toggle(self):
        vis = SpeciesVisibilityManager()
        vis.set_toggle_rects([VisibilityToggleRect("spider", (10, 20, 100, 22))])
        self.assertEqual(vis.hit_test_toggle(50, 30), "spider")
        self.assertIsNone(vis.hit_test_toggle(5, 5))


if __name__ == "__main__":
    unittest.main()

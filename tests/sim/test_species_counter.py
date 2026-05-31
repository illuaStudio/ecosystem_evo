"""World alive-species counter."""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World


def _empty_world():
    return World.from_json(
        {
            "name": "Test",
            "world_width": 400,
            "world_height": 400,
            "initial_entities": {},
        }
    )


class TestSpeciesPopulationCounter(unittest.TestCase):
    def test_count_tracks_spawn_and_death(self):
        world = _empty_world()
        factory = CreatureFactory()

        a = factory.create("Amoeba", world=world, x=50, y=50)
        world.add_creature(a)
        self.assertEqual(world.count_alive_by_species("Amoeba"), 1)

        a.hp = 0
        a.update(1.0)
        self.assertFalse(a.alive)
        self.assertEqual(world.count_alive_by_species("Amoeba"), 0)

    def test_stats_helper_uses_world_counter(self):
        world = _empty_world()
        factory = CreatureFactory()
        from src.sim.utils.stats_helpers import count_alive_by_species

        for i in range(3):
            c = factory.create("Amoeba", world=world, x=10 + i, y=10)
            world.add_creature(c)

        self.assertEqual(count_alive_by_species(world, "Amoeba"), 3)


if __name__ == "__main__":
    unittest.main()

"""シミュレーションのスモークテスト（依存最小・unittest）。"""
import unittest

from src.systems.world import World
from src.utils.position_helpers import entity_xy, sync_legacy_pos


class TestWorldSmoke(unittest.TestCase):
    def test_world_runs_500_ticks_without_error(self):
        world = World()
        self.assertGreater(len(world.creatures), 0)

        for _ in range(500):
            world.update()

        self.assertGreater(len(world.creatures), 0)
        self.assertLess(len(world.creatures), 10_000)

    def test_position_and_legacy_pos_stay_aligned(self):
        world = World()
        creature = world.creatures[0]

        for _ in range(50):
            world.update()
            sync_legacy_pos(creature, update_last=True)
            x, y = entity_xy(creature)
            self.assertAlmostEqual(creature.pos[0], x)
            self.assertAlmostEqual(creature.pos[1], y)
            self.assertAlmostEqual(creature.last_pos[0], x)
            self.assertAlmostEqual(creature.last_pos[1], y)


if __name__ == "__main__":
    unittest.main()

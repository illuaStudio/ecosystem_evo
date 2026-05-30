"""シミュレーション dt（Phase A）のスケール検証。"""
import unittest

from src.sim.systems.movement_system import MovementSystem
from src.sim.systems.world import World
from src.sim.utils.position_helpers import entity_xy


class TestSimDt(unittest.TestCase):
    def test_wander_step_scales_with_dt(self):
        world = World()
        creature = world.creatures[0]
        creature.position.x = 100.0
        creature.position.y = 100.0
        creature.wander_angle = 0.0

        MovementSystem.wander_step(creature, 0.0, 1.0, dt=1.0)
        x1, y1 = entity_xy(creature)

        creature.position.x = 100.0
        creature.position.y = 100.0
        creature.wander_angle = 0.0
        MovementSystem.wander_step(creature, 0.0, 1.0, dt=10.0)
        x2, y2 = entity_xy(creature)

        dist1 = abs(x1 - 100) + abs(y1 - 100)
        dist2 = abs(x2 - 100) + abs(y2 - 100)
        self.assertGreater(dist2, dist1 * 5.0)

    def test_metabolism_scales_with_dt(self):
        world = World()
        creature = world.creatures[0]
        metabolism = creature.traits["metabolism_per_tick"]

        creature.satiety = 20.0
        creature.metabolism._apply_metabolism(1.0)
        self.assertAlmostEqual(creature.satiety, 20.0 - metabolism)

        creature.satiety = 20.0
        creature.metabolism._apply_metabolism(10.0)
        self.assertAlmostEqual(creature.satiety, 20.0 - metabolism * 10.0)

    def test_mana_regen_scales_with_dt(self):
        world = World()
        col, row = 0, 0
        ml = world.mana_layer
        before = ml.mana_density[row][col]
        ml.mana_density[row][col] = 0.0

        ml.regenerate(1.0)
        after_1 = ml.mana_density[row][col]

        ml.mana_density[row][col] = 0.0
        ml.regenerate(10.0)
        after_10 = ml.mana_density[row][col]

        self.assertAlmostEqual(after_10, after_1 * 10.0, delta=after_1 * 0.01)
        ml.mana_density[row][col] = before


if __name__ == "__main__":
    unittest.main()

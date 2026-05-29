"""接触リング（standoff）付き接近のテスト。"""
import math
import unittest

from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import contact_range, move_toward, move_toward_contact
from src.utils.position_helpers import entity_xy


class TestMovementStandoff(unittest.TestCase):
    def test_move_toward_stops_at_min_distance(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        spider = factory.create("Spider", world=world, x=200, y=100)
        world.add_creature(ant)
        world.add_creature(spider)

        standoff = contact_range(ant, spider, 8.0)
        for _ in range(200):
            dist = move_toward(ant, spider, 1.5, dt=1.0, min_distance=standoff)
            if dist <= standoff + 0.01:
                break

        ax, ay = entity_xy(ant)
        sx, sy = entity_xy(spider)
        final_dist = math.hypot(sx - ax, sy - ay)
        self.assertGreaterEqual(final_dist, standoff - 0.5)
        self.assertLess(final_dist, standoff + 15.0)

    def test_move_toward_without_standoff_reaches_center(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        spider = factory.create("Spider", world=world, x=200, y=100)
        world.add_creature(ant)
        world.add_creature(spider)

        for _ in range(200):
            dist = move_toward(ant, spider, 1.5, dt=1.0)
            if dist < 5.0:
                break

        ax, ay = entity_xy(ant)
        sx, sy = entity_xy(spider)
        final_dist = math.hypot(sx - ax, sy - ay)
        self.assertLess(final_dist, contact_range(ant, spider, 8.0) * 0.5)

    def test_move_toward_contact_matches_standoff(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        spider = factory.create("Spider", world=world, x=250, y=100)
        world.add_creature(ant)
        world.add_creature(spider)

        standoff = contact_range(ant, spider, 8.0)
        for _ in range(300):
            dist = move_toward_contact(ant, spider, 1.2, 8.0, dt=1.0)
            if dist <= standoff + 0.01:
                break

        ax, ay = entity_xy(ant)
        sx, sy = entity_xy(spider)
        final_dist = math.hypot(sx - ax, sy - ay)
        self.assertGreaterEqual(final_dist, standoff - 0.5)


if __name__ == "__main__":
    unittest.main()

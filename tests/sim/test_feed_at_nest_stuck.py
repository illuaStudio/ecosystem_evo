"""FeedAtNestAction が巣外で空振りして固まらないこと。"""
import math
import unittest

from src.sim.ai.actions import FeedAtNestAction
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.creature_helpers import distance_to_point
from src.sim.utils.position_helpers import entity_xy


class TestFeedAtNestNotStuck(unittest.TestCase):
    def test_feed_approach_moves_predator_toward_nest(self):
        world = World()
        factory = CreatureFactory()
        predator = factory.create("red_ant", world=world, x=600, y=600)
        world.add_creature(predator)

        nest = world.nest_system.get_creature_nest(predator)
        nest.stored_food = 120.0
        predator.satiety = predator.max_satiety * 0.08

        action = FeedAtNestAction(feed_radius=38)
        self.assertGreater(action.calculate_utility(predator), 0.0)

        dist_before = distance_to_point(predator, nest.x, nest.y)
        self.assertGreater(dist_before, 38.0)

        predator.current_action = action
        action.execute(predator)
        dist_after = distance_to_point(predator, nest.x, nest.y)
        self.assertLess(dist_after, dist_before)

    def test_scavenge_does_not_cancel_nest_approach_same_tick(self):
        """死骸と巣が反対方向でも、1ティックで十分に動く（二重移動の相殺を防ぐ）。"""
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=400, y=500)
        spider = factory.create("Spider", world=world, x=300, y=500)
        spider.alive = False
        spider.remaining_biomass = 200.0
        world.add_creature(ant)
        world.add_creature(spider)

        nest = world.nest_system.get_creature_nest(ant)
        nest.stored_food = 300.0
        ant.satiety = ant.max_satiety * 0.10

        action = FeedAtNestAction(
            feed_radius=38,
            scavenge_species=["springtail", "Spider"],
        )
        x0, y0 = entity_xy(ant)
        action.execute(ant)
        x1, y1 = entity_xy(ant)
        step = math.hypot(x1 - x0, y1 - y0)
        expected = ant.get_current_speed() * 0.95 * 0.85
        self.assertGreater(step, expected)


if __name__ == "__main__":
    unittest.main()

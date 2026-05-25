"""FeedAtNestAction が巣外で空振りして固まらないこと。"""
import unittest

from src.ai.actions import FeedAtNestAction
from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import distance_to_point
from src.utils.position_helpers import entity_xy


class TestFeedAtNestNotStuck(unittest.TestCase):
    def test_feed_approach_moves_predator_toward_nest(self):
        world = World()
        factory = CreatureFactory()
        predator = factory.create("Predator", world=world, x=600, y=600)
        world.add_creature(predator)

        nest = world.nest_system.get_creature_nest(predator)
        nest.stored_food = 120.0
        predator.satiety = predator.max_satiety * 0.4

        action = FeedAtNestAction(feed_radius=38)
        self.assertGreater(action.calculate_utility(predator), 0.0)

        dist_before = distance_to_point(predator, nest.x, nest.y)
        self.assertGreater(dist_before, 38.0)

        predator.current_action = action
        action.execute(predator)
        dist_after = distance_to_point(predator, nest.x, nest.y)
        self.assertLess(dist_after, dist_before)


if __name__ == "__main__":
    unittest.main()

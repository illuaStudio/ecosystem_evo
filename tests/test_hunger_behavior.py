"""飢餓（traits 閾値）とアリの食事優先行動。"""
import unittest

from src.ai.actions import (
    FeedAtNestAction,
    HuntAction,
    ReturnToNestAction,
    ScavengeCarriedAction,
)
from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import (
    get_hunger_threshold,
    is_hungry,
    nest_has_usable_food,
    try_attack_only,
    try_pickup_carcass,
)


class TestHungerBehavior(unittest.TestCase):
    def _ant_and_prey(self, world, ant_satiety_ratio=1.0):
        factory = CreatureFactory()
        ant = factory.create("Ant", world=world, x=500, y=500)
        prey = factory.create("Amoeba", world=world, x=512, y=500)
        ant.satiety = ant.max_satiety * ant_satiety_ratio
        world.add_creature(ant)
        world.add_creature(prey)
        return ant, prey

    def test_hunger_threshold_from_traits(self):
        world = World()
        ant, _ = self._ant_and_prey(world)
        self.assertAlmostEqual(get_hunger_threshold(ant), 0.45)
        ant.satiety = ant.max_satiety * 0.6
        self.assertFalse(is_hungry(ant))
        ant.satiety = ant.max_satiety * 0.5
        self.assertTrue(is_hungry(ant))

    def test_hungry_ant_prefers_nest_when_food_available(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.48)
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=520, y=500)
        world.add_creature(spider)
        nest = world.nest_system.get_creature_nest(ant)
        nest.stored_food = 200.0

        hunt = HuntAction(target_types=["Amoeba", "Spider"])
        feed = FeedAtNestAction()
        self.assertGreater(feed.calculate_utility(ant), hunt.calculate_utility(ant))

    def test_hungry_ant_hunts_when_nest_empty(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.48)
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=520, y=500)
        world.add_creature(spider)
        nest = world.nest_system.get_creature_nest(ant)
        nest.stored_food = 0.0

        hunt = HuntAction(target_types=["Amoeba", "Spider"])
        feed = FeedAtNestAction()
        self.assertGreater(hunt.calculate_utility(ant), 0.0)
        self.assertEqual(feed.calculate_utility(ant), 0.0)

    def test_satiated_ant_still_hunts_for_colony_hoard(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.95)
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=520, y=500)
        world.add_creature(spider)
        nest = world.nest_system.get_creature_nest(ant)
        nest.stored_food = nest.max_food

        hunt = HuntAction(
            target_types=["Amoeba", "Spider"], colony_hoard_strength=0.8
        )
        self.assertGreater(hunt.calculate_utility(ant), 0.0)

    def test_satiated_ant_hunts_amoeba(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.95)
        hunt = HuntAction(target_types=["Amoeba", "Spider"])
        self.assertGreater(hunt.calculate_utility(ant), 0.0)

    def test_low_nest_reserve_not_usable_when_hungry(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.48)
        nest = world.nest_system.get_creature_nest(ant)
        nest.stored_food = 8.0
        nest.max_food = 5000.0
        self.assertFalse(nest_has_usable_food(ant))
        feed = FeedAtNestAction()
        hunt = HuntAction(target_types=["Amoeba", "Spider"])
        self.assertEqual(feed.calculate_utility(ant), 0.0)
        self.assertGreater(hunt.calculate_utility(ant), 0.0)

    def test_hungry_carrying_prefers_scavenge_over_return(self):
        world = World()
        ant, prey = self._ant_and_prey(world, ant_satiety_ratio=0.48)
        for _ in range(12):
            if not prey.alive:
                break
            try_attack_only(ant, prey, attack_power=2.5)
        self.assertTrue(try_pickup_carcass(ant, prey))

        scavenge = ScavengeCarriedAction()
        ret = ReturnToNestAction()
        self.assertGreater(scavenge.calculate_utility(ant), ret.calculate_utility(ant))

    def test_hungry_carrying_eats_carcass(self):
        world = World()
        ant, prey = self._ant_and_prey(world, ant_satiety_ratio=0.48)
        for _ in range(12):
            if not prey.alive:
                break
            try_attack_only(ant, prey, attack_power=2.5)
        try_pickup_carcass(ant, prey)
        biomass_before = prey.remaining_biomass
        satiety_before = ant.satiety

        action = ScavengeCarriedAction()
        action.execute(ant)

        self.assertGreater(ant.satiety, satiety_before)
        self.assertLess(prey.remaining_biomass, biomass_before)

    def test_feed_action_moves_toward_empty_nest_when_hungry(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.48)
        nest = world.nest_system.get_creature_nest(ant)
        nest.stored_food = 0.0
        ant.pos[0] = nest.x + 200
        ant.pos[1] = nest.y
        ant.position.x = ant.pos[0]
        ant.position.y = ant.pos[1]

        dist_before = ((ant.pos[0] - nest.x) ** 2 + (ant.pos[1] - nest.y) ** 2) ** 0.5
        FeedAtNestAction().execute(ant)
        dist_after = ((ant.pos[0] - nest.x) ** 2 + (ant.pos[1] - nest.y) ** 2) ** 0.5
        self.assertLess(dist_after, dist_before)


if __name__ == "__main__":
    unittest.main()

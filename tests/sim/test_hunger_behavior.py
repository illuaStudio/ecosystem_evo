"""栄養状態（満腹/通常/飢餓）とアリの食事優先行動。"""
import unittest

from src.sim.ai.actions import (
    FeedAtNestAction,
    HuntAction,
    NestPatrolAction,
    ReturnToNestAction,
    ScavengeCarriedAction,
)
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.creature_helpers import (
    NutritionState,
    get_nutrition_state,
    get_satiety_full_above,
    get_satiety_hungry_below,
    is_hungry,
    is_satiated,
    needs_nest_feed,
    needs_self_feed,
    nest_has_usable_food,
    satiety_ratio,
    try_attack_only,
    try_pickup_carcass,
    update_nutrition_recovery,
)
from src.sim.utils.inventory_helpers import inventory_is_loaded, total_biomass_amount
from src.sim.utils.position_helpers import entity_xy


class TestHungerBehavior(unittest.TestCase):
    def _ant_and_prey(self, world, ant_satiety_ratio=1.0):
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        prey = factory.create("Amoeba", world=world, x=512, y=500)
        ant.satiety = ant.max_satiety * ant_satiety_ratio
        world.add_creature(ant)
        world.add_creature(prey)
        return ant, prey

    def test_nutrition_thresholds_from_traits(self):
        world = World()
        ant, _ = self._ant_and_prey(world)
        self.assertAlmostEqual(get_satiety_hungry_below(ant), 0.15)
        self.assertAlmostEqual(get_satiety_full_above(ant), 0.85)

        ant.satiety = ant.max_satiety * 0.9
        self.assertEqual(get_nutrition_state(ant), NutritionState.FULL)
        self.assertFalse(is_hungry(ant))
        self.assertTrue(is_satiated(ant))

        ant.satiety = ant.max_satiety * 0.5
        self.assertEqual(get_nutrition_state(ant), NutritionState.NORMAL)
        self.assertFalse(is_hungry(ant))
        self.assertFalse(is_satiated(ant))

        ant.satiety = ant.max_satiety * 0.1
        self.assertEqual(get_nutrition_state(ant), NutritionState.HUNGRY)
        self.assertTrue(is_hungry(ant))
        self.assertFalse(is_satiated(ant))

    def test_normal_ant_hoard_hunts(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.5)
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=520, y=500)
        world.add_creature(spider)

        hunt = HuntAction(target_types=["Amoeba", "Spider"])
        self.assertGreater(hunt.calculate_utility(ant), 0.0)

    def test_hungry_ant_prefers_nest_when_food_available(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.10)
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
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.10)
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

    def test_low_nest_reserve_usable_when_hungry(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        nest = world.nest_system.get_creature_nest(ant)
        nest.stored_food = 8.0
        nest.max_food = 5000.0
        self.assertTrue(nest_has_usable_food(ant))
        feed = FeedAtNestAction()
        self.assertGreater(feed.calculate_utility(ant), 0.0)

    def test_hungry_carrying_prefers_scavenge_over_return(self):
        world = World()
        ant, prey = self._ant_and_prey(world, ant_satiety_ratio=0.10)
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
        ant, prey = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        for _ in range(12):
            if not prey.alive:
                break
            try_attack_only(ant, prey, attack_power=2.5)
        try_pickup_carcass(ant, prey)

        carried_before = total_biomass_amount(ant)
        satiety_before = ant.satiety
        self.assertGreater(carried_before, 0)

        action = ScavengeCarriedAction()
        action.execute(ant)

        self.assertGreater(ant.satiety, satiety_before)
        self.assertLess(total_biomass_amount(ant), carried_before)

    def test_scavenge_keeps_remainder_for_nest_after_recovery(self):
        """回復ラッチ終了後も運搬分を手放さず、帰巣行動に戻れる。"""
        world = World()
        ant, prey = self._ant_and_prey(world, ant_satiety_ratio=0.84)
        ant.nutrition_recovery = True
        for _ in range(12):
            if not prey.alive:
                break
            try_attack_only(ant, prey, attack_power=2.5)
        try_pickup_carcass(ant, prey)
        self.assertTrue(inventory_is_loaded(ant))

        scavenge = ScavengeCarriedAction()
        ret = ReturnToNestAction()
        scavenge.execute(ant)

        self.assertFalse(needs_self_feed(ant))
        self.assertTrue(inventory_is_loaded(ant))
        self.assertEqual(scavenge.calculate_utility(ant), 0.0)
        self.assertGreater(ret.calculate_utility(ant), 0.0)

    def test_hungry_does_not_approach_empty_nest(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        nest = world.nest_system.get_creature_nest(ant)
        nest.stored_food = 0.0
        ant.pos[0] = nest.x + 200
        ant.pos[1] = nest.y
        ant.position.x = ant.pos[0]
        ant.position.y = ant.pos[1]

        feed = FeedAtNestAction()
        self.assertEqual(feed.calculate_utility(ant), 0.0)
        x_before, y_before = entity_xy(ant)
        feed.execute(ant)
        x_after, y_after = entity_xy(ant)
        self.assertAlmostEqual(x_before, x_after, places=3)
        self.assertAlmostEqual(y_before, y_after, places=3)

    def test_nest_feed_stops_at_full_above(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.5)
        ant.nutrition_recovery = True
        nest = world.nest_system.get_creature_nest(ant)
        nest.stored_food = 500.0
        ant.pos[0] = nest.x
        ant.pos[1] = nest.y
        ant.position.x = nest.x
        ant.position.y = nest.y

        for _ in range(300):
            if is_satiated(ant):
                break
            FeedAtNestAction(feed_radius=38).execute(ant)

        self.assertTrue(is_satiated(ant))
        self.assertLessEqual(ant.satiety, ant.max_satiety)
        self.assertFalse(needs_self_feed(ant))

    def test_recovery_mode_persists_until_full_above(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        self.assertTrue(needs_self_feed(ant))

        nest = world.nest_system.get_creature_nest(ant)
        nest.stored_food = 200.0
        ant.satiety = ant.max_satiety * 0.25
        update_nutrition_recovery(ant)
        self.assertFalse(is_hungry(ant))
        self.assertTrue(needs_self_feed(ant))

        hunt = HuntAction(target_types=["Amoeba", "Spider"])
        self.assertEqual(hunt.calculate_utility(ant), 0.0)

    def test_recovery_clears_at_full_above(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        ant.satiety = ant.max_satiety * 0.90
        update_nutrition_recovery(ant)
        self.assertFalse(needs_self_feed(ant))

    def test_recovery_carrying_keeps_self_feed(self):
        world = World()
        ant, prey = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        needs_self_feed(ant)
        for _ in range(12):
            if not prey.alive:
                break
            try_attack_only(ant, prey, attack_power=2.5)
        try_pickup_carcass(ant, prey)
        ant.satiety = ant.max_satiety * 0.20
        update_nutrition_recovery(ant)

        self.assertTrue(needs_self_feed(ant))
        self.assertGreater(ScavengeCarriedAction().calculate_utility(ant), 0.0)
        self.assertEqual(ReturnToNestAction().calculate_utility(ant), 0.0)

    def test_feed_not_selected_after_recovery_clears_near_full_above(self):
        """回復解除後、85%付近の代謝ドリフトで FeedAtNest が再選択されない（チャタリング防止）。"""
        world = World()
        factory = CreatureFactory()
        vanguard = factory.create("red_ant_vanguard", world=world, x=500, y=500)
        world.add_creature(vanguard)
        nest = world.nest_system.get_creature_nest(vanguard)
        nest.stored_food = 500.0

        vanguard.satiety = vanguard.max_satiety * 0.84
        vanguard.nutrition_recovery = False
        update_nutrition_recovery(vanguard)

        feed = FeedAtNestAction(feed_radius=42)
        patrol = NestPatrolAction(patrol_radius=480)

        self.assertFalse(needs_self_feed(vanguard))
        self.assertEqual(feed.calculate_utility(vanguard), 0.0)
        self.assertGreater(patrol.calculate_utility(vanguard), 0.0)

    def test_feed_still_selected_while_in_recovery_below_full_above(self):
        world = World()
        factory = CreatureFactory()
        vanguard = factory.create("red_ant_vanguard", world=world, x=500, y=500)
        world.add_creature(vanguard)
        nest = world.nest_system.get_creature_nest(vanguard)
        self.assertIsNotNone(nest)
        nest.stored_food = 500.0

        vanguard.satiety = vanguard.max_satiety * 0.84
        vanguard.nutrition_recovery = True

        feed = FeedAtNestAction(feed_radius=42)
        self.assertTrue(needs_self_feed(vanguard))
        self.assertTrue(nest_has_usable_food(vanguard))
        self.assertGreater(feed.calculate_utility(vanguard), 0.0)

    def test_nest_usable_food_allows_top_up_near_full_above(self):
        world = World()
        ant, _ = self._ant_and_prey(world, ant_satiety_ratio=0.84)
        nest = world.nest_system.get_creature_nest(ant)
        nest.stored_food = 500.0
        self.assertTrue(nest_has_usable_food(ant))

    def test_vanguard_not_stuck_feeding_at_displayed_85_percent(self):
        """84.9% 等（HUD では 85%）で回復モード・FeedAtNest に張り付かない。"""
        world = World()
        factory = CreatureFactory()
        vanguard = factory.create("red_ant_vanguard", world=world, x=500, y=500)
        world.add_creature(vanguard)
        nest = world.nest_system.get_creature_nest(vanguard)
        nest.stored_food = 500.0

        vanguard.satiety = vanguard.max_satiety * 0.8493
        vanguard.nutrition_recovery = True

        update_nutrition_recovery(vanguard)
        self.assertFalse(needs_self_feed(vanguard))
        self.assertFalse(needs_nest_feed(vanguard))

        feed = FeedAtNestAction(feed_radius=42)
        patrol = NestPatrolAction(patrol_radius=480)
        self.assertEqual(feed.calculate_utility(vanguard), 0.0)
        self.assertGreater(patrol.calculate_utility(vanguard), 0.0)

    def test_metabolism_equilibrium_clears_recovery_for_vanguard(self):
        world = World()
        factory = CreatureFactory()
        vanguard = factory.create("red_ant_vanguard", world=world, x=500, y=500)
        world.add_creature(vanguard)
        nest = world.nest_system.get_creature_nest(vanguard)
        nest.stored_food = 500.0
        vanguard.pos[0] = nest.x
        vanguard.pos[1] = nest.y
        vanguard.position.x = nest.x
        vanguard.position.y = nest.y
        vanguard.satiety = vanguard.max_satiety * 0.5
        vanguard.nutrition_recovery = True

        feed = FeedAtNestAction(feed_radius=42)
        for _ in range(400):
            vanguard.metabolism.update(dt=1.0)
            if not needs_self_feed(vanguard):
                break
            feed.execute(vanguard)

        self.assertFalse(needs_self_feed(vanguard))
        self.assertEqual(feed.calculate_utility(vanguard), 0.0)


if __name__ == "__main__":
    unittest.main()

from src.game.colony_session import get_colony_orchestrator, try_get_colony_orchestrator

def colony(world):
    return get_colony_orchestrator(world)

"""栄養状態（満腹/通常/飢餓）とアリの食事優先行動。"""
import unittest

from src.game.ai.colony_actions import (
    FeedAtNestAction,
    NestPatrolAction,
    ReturnToNestAction,
    ScavengeCarriedAction,
)
from src.game.ai.hunt_actions import HuntAction
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.game.affiliation_feed import (
    is_affiliation_feed_satisfied,
    needs_affiliation_feed,
    nest_has_usable_storage,
    sync_nutrition_recovery_for_affiliation_feed,
)
from src.sim.utils.creature_helpers import (
    NutritionState,
    get_nutrition_state,
    get_satiety_full_above,
    get_satiety_hungry_below,
    is_hungry,
    is_satiated,
    needs_self_feed,
    satiety_ratio,
    try_attack_only,
    update_nutrition_recovery,
)
from tests.sim.field_drop_helpers import kill_creature, pickup_field_biomass
from src.sim.utils.inventory_helpers import inventory_is_loaded, carried_mass_for_kind
from src.sim.utils.position_helpers import entity_xy


class TestHungerBehavior(unittest.TestCase):
    def _ant_and_prey(self, world, ant_satiety_ratio=1.0, *, near_nest: bool = True):
        factory = CreatureFactory()
        if near_nest:
            ax, ay = 125.0, 125.0
        else:
            ax, ay = 500.0, 500.0
        ant = factory.create("red_ant", world=world, x=ax, y=ay)
        prey = factory.create("springtail", world=world, x=ax + 12, y=ay)
        ant.satiety = ant.max_satiety * ant_satiety_ratio
        world.add_creature(ant)
        world.add_creature(prey)
        return ant, prey, ax, ay

    def test_nutrition_thresholds_from_traits(self):
        world = World()
        ant, _, _ax, _ay = self._ant_and_prey(world)
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
        ant, _, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.5)
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=ax + 20, y=ay)
        world.add_creature(spider)

        hunt = HuntAction(target_types=["springtail", "Spider"])
        self.assertGreater(hunt.calculate_utility(ant), 0.0)

    def test_hungry_ant_prefers_nest_when_food_available(self):
        world = World()
        ant, _, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=ax + 20, y=ay)
        world.add_creature(spider)
        nest = colony(world).get_creature_affiliation_root(ant)
        nest.stored_mass = 200.0

        hunt = HuntAction(target_types=["springtail", "Spider"])
        feed = FeedAtNestAction()
        self.assertGreater(feed.calculate_utility(ant), hunt.calculate_utility(ant))

    def test_hungry_ant_hunts_when_nest_empty(self):
        world = World()
        ant, _, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=ax + 20, y=ay)
        world.add_creature(spider)
        nest = colony(world).get_creature_affiliation_root(ant)
        nest.stored_mass = 0.0

        hunt = HuntAction(target_types=["springtail", "Spider"])
        feed = FeedAtNestAction()
        self.assertGreater(hunt.calculate_utility(ant), 0.0)
        self.assertEqual(feed.calculate_utility(ant), 0.0)

    def test_satiated_ant_still_hunts_for_colony_hoard(self):
        world = World()
        ant, _, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.95)
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=ax + 20, y=ay)
        world.add_creature(spider)
        nest = colony(world).get_creature_affiliation_root(ant)
        nest.stored_mass = nest.capacity

        hunt = HuntAction(
            target_types=["springtail", "Spider"], affiliation_hoard_strength=0.8
        )
        self.assertGreater(hunt.calculate_utility(ant), 0.0)

    def test_low_nest_reserve_usable_when_hungry(self):
        world = World()
        ant, _, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        nest = colony(world).get_creature_affiliation_root(ant)
        nest.stored_mass = 8.0
        nest.capacity = 5000.0
        self.assertTrue(nest_has_usable_storage(ant))
        feed = FeedAtNestAction()
        self.assertGreater(feed.calculate_utility(ant), 0.0)

    def test_hungry_carrying_prefers_scavenge_over_return(self):
        world = World()
        ant, prey, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        loot = kill_creature(world, prey, ant)
        self.assertIsNotNone(loot)
        self.assertTrue(pickup_field_biomass(ant, loot))

        scavenge = ScavengeCarriedAction()
        ret = ReturnToNestAction()
        self.assertGreater(scavenge.calculate_utility(ant), ret.calculate_utility(ant))

    def test_hungry_carrying_does_not_get_stuck_in_return_to_nest(self):
        """ReturnToNestAction は飢餓時に completed になり、次 tick で ScavengeCarriedAction に切り替われる。"""
        world = World()
        ant, prey, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        loot = kill_creature(world, prey, ant)
        pickup_field_biomass(ant, loot)

        ret = ReturnToNestAction()
        ant.current_action = ret
        ret.execute(ant)
        self.assertTrue(ret.is_completed())

        # Next tick: mind should be free to pick ScavengeCarriedAction.
        ant.current_action = ant.mind.decide_next_action(ant)
        self.assertEqual(type(ant.current_action).__name__, "ScavengeCarriedAction")

    def test_hungry_carrying_eats_carcass(self):
        world = World()
        ant, prey, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        loot = kill_creature(world, prey, ant)
        pickup_field_biomass(ant, loot)

        carried_before = carried_mass_for_kind(ant)
        satiety_before = ant.satiety
        self.assertGreater(carried_before, 0)

        action = ScavengeCarriedAction()
        action.execute(ant)

        self.assertGreater(ant.satiety, satiety_before)
        self.assertLess(carried_mass_for_kind(ant), carried_before)

    def test_scavenge_keeps_remainder_for_nest_after_recovery(self):
        """回復ラッチ終了後も運搬分を手放さず、帰巣行動に戻れる。"""
        world = World()
        ant, prey, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.84)
        ant.nutrition_recovery = True
        loot = kill_creature(world, prey, ant)
        pickup_field_biomass(ant, loot)
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
        ant, _, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        nest = colony(world).get_creature_affiliation_root(ant)
        nest.stored_mass = 0.0
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
        ant, _, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.5)
        ant.nutrition_recovery = True
        nest = colony(world).get_creature_affiliation_root(ant)
        nest.stored_mass = 500.0
        ant.pos[0] = nest.x
        ant.pos[1] = nest.y
        ant.position.x = nest.x
        ant.position.y = nest.y

        for _ in range(300):
            if is_affiliation_feed_satisfied(ant):
                break
            FeedAtNestAction(feed_radius=38).execute(ant)

        self.assertTrue(is_affiliation_feed_satisfied(ant))
        self.assertLessEqual(ant.satiety, ant.max_satiety)
        self.assertFalse(needs_self_feed(ant))

    def test_recovery_mode_persists_until_full_above(self):
        world = World()
        ant, _, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        self.assertTrue(needs_self_feed(ant))

        nest = colony(world).get_creature_affiliation_root(ant)
        nest.stored_mass = 200.0
        ant.satiety = ant.max_satiety * 0.25
        update_nutrition_recovery(ant)
        self.assertFalse(is_hungry(ant))
        self.assertTrue(needs_self_feed(ant))

        hunt = HuntAction(target_types=["springtail", "Spider"])
        self.assertEqual(hunt.calculate_utility(ant), 0.0)

    def test_recovery_clears_at_full_above(self):
        world = World()
        ant, _, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        ant.satiety = ant.max_satiety * 0.90
        update_nutrition_recovery(ant)
        self.assertFalse(needs_self_feed(ant))

    def test_recovery_carrying_keeps_self_feed(self):
        world = World()
        ant, prey, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.10)
        needs_self_feed(ant)
        loot = kill_creature(world, prey, ant)
        pickup_field_biomass(ant, loot)
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
        nest = colony(world).get_creature_affiliation_root(vanguard)
        nest.stored_mass = 500.0

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
        nest = colony(world).get_creature_affiliation_root(vanguard)
        self.assertIsNotNone(nest)
        nest.stored_mass = 500.0

        vanguard.satiety = vanguard.max_satiety * 0.84
        vanguard.nutrition_recovery = True

        feed = FeedAtNestAction(feed_radius=42)
        self.assertTrue(needs_self_feed(vanguard))
        self.assertTrue(nest_has_usable_storage(vanguard))
        self.assertGreater(feed.calculate_utility(vanguard), 0.0)

    def test_nest_usable_food_allows_top_up_near_full_above(self):
        world = World()
        ant, _, ax, ay = self._ant_and_prey(world, ant_satiety_ratio=0.84)
        nest = colony(world).get_creature_affiliation_root(ant)
        nest.stored_mass = 500.0
        self.assertTrue(nest_has_usable_storage(ant))

    def test_vanguard_not_stuck_feeding_at_displayed_85_percent(self):
        """84.9% 等（HUD では 85%）で回復モード・FeedAtNest に張り付かない。"""
        world = World()
        factory = CreatureFactory()
        vanguard = factory.create("red_ant_vanguard", world=world, x=500, y=500)
        world.add_creature(vanguard)
        nest = colony(world).get_creature_affiliation_root(vanguard)
        nest.stored_mass = 500.0

        vanguard.satiety = vanguard.max_satiety * 0.8493
        vanguard.nutrition_recovery = True

        update_nutrition_recovery(vanguard)
        sync_nutrition_recovery_for_affiliation_feed(vanguard)
        self.assertFalse(needs_self_feed(vanguard))
        self.assertFalse(needs_affiliation_feed(vanguard))

        feed = FeedAtNestAction(feed_radius=42)
        patrol = NestPatrolAction(patrol_radius=480)
        self.assertEqual(feed.calculate_utility(vanguard), 0.0)
        self.assertGreater(patrol.calculate_utility(vanguard), 0.0)

    def test_metabolism_equilibrium_clears_recovery_for_vanguard(self):
        world = World()
        factory = CreatureFactory()
        vanguard = factory.create("red_ant_vanguard", world=world, x=500, y=500)
        world.add_creature(vanguard)
        nest = colony(world).get_creature_affiliation_root(vanguard)
        nest.stored_mass = 500.0
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


class TestQueenNestFeeding(unittest.TestCase):
    def _sheltered_queen(self, satiety_ratio: float):
        from src.game.command_builder import apply_spawn_profile
        from src.game.sim_bridge_factory import make_sim_bridge
        from src.sim.shelter.state import is_creature_sheltered

        world = World()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen)
        apply_spawn_profile(make_sim_bridge(world), queen)
        queen.satiety = queen.max_satiety * satiety_ratio
        queen.nutrition_recovery = False
        update_nutrition_recovery(queen)
        nest = colony(world).get_creature_affiliation_root(queen)
        from tests.sim.world_fixtures import set_affiliation_stored_mass

        set_affiliation_stored_mass(world, nest.affiliation_id, 500.0)
        self.assertTrue(is_creature_sheltered(queen))
        return world, queen, nest

    def test_queen_feed_below_threshold_from_traits(self):
        world = World()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen)
        from src.sim.utils.creature_helpers import get_satiety_feed_below

        self.assertAlmostEqual(get_satiety_feed_below(queen), 0.5)

    def test_sheltered_queen_does_not_feed_above_feed_below(self):
        _, queen, _ = self._sheltered_queen(0.60)
        feed = FeedAtNestAction(feed_radius=38)

        self.assertFalse(needs_self_feed(queen))
        self.assertEqual(feed.calculate_utility(queen), 0.0)
        sat_before = queen.satiety
        feed.execute(queen)
        self.assertAlmostEqual(queen.satiety, sat_before)

    def test_sheltered_queen_feeds_when_below_feed_below_until_full(self):
        _, queen, nest = self._sheltered_queen(0.45)
        feed = FeedAtNestAction(feed_radius=38)

        self.assertTrue(needs_self_feed(queen))
        self.assertGreater(feed.calculate_utility(queen), 0.0)

        for _ in range(400):
            if is_affiliation_feed_satisfied(queen):
                break
            feed.execute(queen)

        self.assertTrue(is_affiliation_feed_satisfied(queen))
        self.assertFalse(needs_self_feed(queen))
        self.assertLess(nest.stored_mass, 500.0)

    def test_sheltered_queen_no_chatter_near_full_above(self):
        _, queen, _ = self._sheltered_queen(0.89)
        feed = FeedAtNestAction(feed_radius=38)

        self.assertFalse(needs_self_feed(queen))
        self.assertEqual(feed.calculate_utility(queen), 0.0)

    def test_sheltered_queen_still_feeds_when_hungry(self):
        _, queen, _ = self._sheltered_queen(0.15)
        feed = FeedAtNestAction(feed_radius=38)

        self.assertTrue(is_hungry(queen))
        self.assertTrue(needs_self_feed(queen))
        self.assertGreater(feed.calculate_utility(queen), 0.0)


if __name__ == "__main__":
    unittest.main()

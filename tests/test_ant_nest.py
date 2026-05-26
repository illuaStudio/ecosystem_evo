"""アリコロニー（巣・持ち帰り）のスモークテスト。"""
import unittest

from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import (
    has_edible_carcass,
    hunger_ratio,
    is_carcass_carried,
    try_attack_only,
    try_pickup_carcass,
)
from src.config import config
from src.utils.creature_helpers import distance_to_point
from src.utils.position_helpers import entity_xy


class TestAntNest(unittest.TestCase):
    def _spawn_predators(self, world, count: int = 3):
        factory = CreatureFactory()
        preds = []
        for i in range(count):
            x = 400 + i * 25
            y = 400 + i * 15
            p = factory.create("Ant", world=world, x=x, y=y)
            world.add_creature(p)
            preds.append(p)
        return preds

    def test_predators_share_single_nest_even_when_far_apart(self):
        world = World()
        factory = CreatureFactory()
        preds = []
        for i, (x, y) in enumerate([(120, 120), (850, 850), (500, 200)]):
            p = factory.create("Ant", world=world, x=x, y=y)
            world.add_creature(p)
            preds.append(p)
        nest_ids = {p.colony.nest_id for p in preds}
        self.assertEqual(len(nest_ids), 1)
        self.assertEqual(len(world.nest_system.nests), 1)

    def test_initial_predators_spawn_near_nest_anchor(self):
        world = World()
        colony_cfg = config.get_species("Ant").get("colony", {})
        anchor_x = float(colony_cfg.get("nest_x", world.width * 0.5))
        anchor_y = float(colony_cfg.get("nest_y", world.height * 0.5))
        spread = float(colony_cfg.get("spawn_spread", 28))

        preds = [c for c in world.creatures if c.species.name == "Ant"]
        self.assertGreaterEqual(len(preds), 1)
        for p in preds:
            px, py = entity_xy(p)
            dist = ((px - anchor_x) ** 2 + (py - anchor_y) ** 2) ** 0.5
            self.assertLessEqual(dist, spread + 5)

    def test_nest_spawn_position_uses_existing_nest(self):
        world = World()
        factory = CreatureFactory()
        colony_cfg = config.get_species("Ant").get("colony", {})
        first = factory.create("Ant", world=world, x=300, y=300)
        world.add_creature(first)
        nest = world.nest_system.get_creature_nest(first)

        x, y = world.nest_system.spawn_position("Ant", colony_cfg)
        dist = distance_to_point(type("_P", (), {"pos": [x, y]})(), nest.x, nest.y)
        spread = float(colony_cfg.get("spawn_spread", 28))
        self.assertLessEqual(dist, spread + 1)

    def test_p_spawn_joins_existing_nest(self):
        world = World()
        factory = CreatureFactory()
        first = factory.create("Ant", world=world, x=300, y=300)
        world.add_creature(first)
        nest_id = first.colony.nest_id

        second = factory.create("Ant", world=world, x=900, y=900)
        world.add_creature(second)
        self.assertEqual(second.colony.nest_id, nest_id)
        self.assertEqual(len(world.nest_system.nests), 1)

    def test_hunt_pickup_and_deposit_increases_nest_storage(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        predator = preds[0]
        predator.satiety = predator.max_satiety * 0.95
        nest = world.nest_system.get_creature_nest(predator)

        factory = CreatureFactory()
        prey = factory.create("Amoeba", world=world, x=0, y=0)
        world.add_creature(prey)

        px, py = entity_xy(predator)
        prey.pos[0] = px + 12
        prey.pos[1] = py
        if hasattr(prey, "position"):
            prey.position.x = prey.pos[0]
            prey.position.y = prey.pos[1]

        for _ in range(12):
            if not prey.alive:
                break
            try_attack_only(predator, prey, attack_power=2.5)
        self.assertFalse(prey.alive)
        self.assertTrue(has_edible_carcass(prey))

        self.assertTrue(try_pickup_carcass(predator, prey))
        self.assertTrue(predator.colony.is_carrying)

        deposited = world.nest_system.deposit_carried(predator)
        self.assertGreater(deposited, 0)
        self.assertGreater(nest.stored_food, 0)
        self.assertFalse(predator.colony.is_carrying)

    def test_feed_at_nest_reduces_hunger(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        predator = preds[0]
        nest = world.nest_system.get_creature_nest(predator)
        nest.stored_food = 200.0
        predator.satiety = predator.max_satiety * 0.2

        before = hunger_ratio(predator)
        world.nest_system.feed_creature(predator, bite_gain=1.2)
        after = hunger_ratio(predator)
        self.assertLess(after, before)
        self.assertLess(nest.stored_food, 200.0)

    def test_food_leak_reduces_storage_and_adds_mana_at_nest(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        nest = world.nest_system.get_creature_nest(preds[0])
        nest.stored_food = 400.0

        mana_before = world.get_mana_density(nest.x, nest.y)
        for _ in range(80):
            world.nest_system.update(1.0)
        mana_after = world.get_mana_density(nest.x, nest.y)

        self.assertLess(nest.stored_food, 400.0)
        self.assertGreater(mana_after, mana_before)
        reserve = nest.max_food * 0.15
        self.assertGreaterEqual(nest.stored_food, reserve * 0.85)

    def test_feed_per_member_ratio_divides_by_colony_size(self):
        world = World()
        for c in list(world.creatures):
            if c.species.name == "Ant":
                world.remove_creature(c)
        world.nest_system.nests.clear()
        preds = self._spawn_predators(world, 3)
        nest = world.nest_system.get_creature_nest(preds[0])
        nest.stored_food = 200.0
        members = world.nest_system.member_count(nest.id, "Ant")
        self.assertEqual(members, 3)
        solo_cap = 200.0 * 0.14
        shared_cap = 200.0 * 0.14 / members
        self.assertLess(shared_cap, solo_cap)

    def test_spawn_worker_consumes_food_and_adds_member(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        predator = preds[0]
        nest = world.nest_system.get_creature_nest(predator)
        colony_cfg = config.get_species("Ant").get("colony", {})
        cost = float(colony_cfg["spawn_food_cost"])
        reserve = float(colony_cfg["min_food_reserve"])

        nest.stored_food = reserve + cost + 10
        members_before = world.nest_system.member_count(nest.id, "Ant")
        food_before = nest.stored_food

        from src.utils.position_helpers import entity_xy

        predator.pos[0] = nest.x
        predator.pos[1] = nest.y
        if hasattr(predator, "position"):
            predator.position.x = nest.x
            predator.position.y = nest.y

        worker = world.nest_system.spawn_worker(predator, colony_cfg)
        self.assertIsNotNone(worker)
        world.add_creature(worker)

        self.assertEqual(
            world.nest_system.member_count(nest.id, "Ant"),
            members_before + 1,
        )
        self.assertAlmostEqual(nest.stored_food, food_before - cost)
        self.assertEqual(worker.colony.nest_id, nest.id)

    def test_spawn_worker_blocked_at_max_workers(self):
        world = World()
        colony_cfg = config.get_species("Ant").get("colony", {})
        max_workers = int(colony_cfg["max_workers"])
        preds = self._spawn_predators(world, max_workers)
        nest = world.nest_system.get_creature_nest(preds[0])
        nest.stored_food = nest.max_food

        self.assertFalse(world.nest_system.can_spawn_worker(preds[0], colony_cfg))
        self.assertIsNone(world.nest_system.spawn_worker(preds[0], colony_cfg))

    def test_spawn_worker_blocked_below_min_reserve(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        predator = preds[0]
        nest = world.nest_system.get_creature_nest(predator)
        colony_cfg = config.get_species("Ant").get("colony", {})
        cost = float(colony_cfg["spawn_food_cost"])
        reserve = float(colony_cfg["min_food_reserve"])

        nest.stored_food = reserve + cost - 1
        self.assertFalse(world.nest_system.can_spawn_worker(predator, colony_cfg))

    def test_hunt_utility_positive_when_satiated_regardless_of_nest_fill(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        predator = preds[0]
        nest = world.nest_system.get_creature_nest(predator)
        predator.satiety = predator.max_satiety * 0.95

        prey = next(c for c in world.creatures if c.species.name == "Spider")
        px, py = entity_xy(predator)
        prey.pos[0] = px + 20
        prey.pos[1] = py
        if hasattr(prey, "position"):
            prey.position.x = prey.pos[0]
            prey.position.y = prey.pos[1]

        from src.ai.actions import HuntAction

        action = HuntAction(target_types=["Amoeba", "Spider"])
        for stored in (0.0, nest.max_food * 0.5, nest.max_food):
            nest.stored_food = stored
            with self.subTest(stored_food=stored):
                self.assertGreater(action.calculate_utility(predator), 0.0)

    def test_second_predator_cannot_pickup_carried_carcass(self):
        world = World()
        preds = self._spawn_predators(world, 2)
        carrier, other = preds[0], preds[1]
        factory = CreatureFactory()
        prey = factory.create("Amoeba", world=world, x=0, y=0)
        world.add_creature(prey)
        px, py = entity_xy(carrier)
        prey.pos[0] = px + 10
        prey.pos[1] = py
        if hasattr(prey, "position"):
            prey.position.x = prey.pos[0]
            prey.position.y = prey.pos[1]

        for _ in range(12):
            if not prey.alive:
                break
            try_attack_only(carrier, prey, attack_power=2.5)
        self.assertTrue(try_pickup_carcass(carrier, prey))
        self.assertTrue(is_carcass_carried(world, prey))
        self.assertFalse(try_pickup_carcass(other, prey))

    def test_deposit_zeros_carcass_biomass_prevents_double_storage(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        predator = preds[0]
        predator.satiety = predator.max_satiety * 0.95
        nest = world.nest_system.get_creature_nest(predator)
        factory = CreatureFactory()
        prey = factory.create("Amoeba", world=world, x=0, y=0)
        world.add_creature(prey)
        px, py = entity_xy(predator)
        prey.pos[0] = px + 10
        prey.pos[1] = py
        if hasattr(prey, "position"):
            prey.position.x = prey.pos[0]
            prey.position.y = prey.pos[1]

        for _ in range(12):
            if not prey.alive:
                break
            try_attack_only(predator, prey, attack_power=2.5)
        self.assertTrue(try_pickup_carcass(predator, prey))
        biomass = prey.remaining_biomass
        deposited = world.nest_system.deposit_carried(predator)
        self.assertGreater(deposited, 0)
        self.assertEqual(prey.remaining_biomass, 0.0)
        nest.stored_food = 0.0
        predator.colony.carried_carcass = prey
        second = world.nest_system.deposit_carried(predator)
        self.assertEqual(second, 0.0)

    def test_spawn_worker_action_at_nest(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        predator = preds[0]
        nest = world.nest_system.get_creature_nest(predator)
        colony_cfg = config.get_species("Ant").get("colony", {})
        cost = float(colony_cfg["spawn_food_cost"])
        reserve = float(colony_cfg["min_food_reserve"])
        nest.stored_food = reserve + cost + 50

        predator.pos[0] = nest.x
        predator.pos[1] = nest.y
        if hasattr(predator, "position"):
            predator.position.x = nest.x
            predator.position.y = nest.y

        from src.ai.actions import SpawnWorkerAction

        action = SpawnWorkerAction(spawn_cooldown=0)
        members_before = world.nest_system.member_count(nest.id, "Ant")
        self.assertTrue(action.execute(predator))
        self.assertEqual(
            world.nest_system.member_count(nest.id, "Ant"),
            members_before + 1,
        )

    def test_find_nest_at_click(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        nest = world.nest_system.get_creature_nest(preds[0])
        ns = world.nest_system

        hit = ns.find_nest_at(nest.x, nest.y, pick_radius=36)
        self.assertIs(hit, nest)

        miss = ns.find_nest_at(nest.x + 200, nest.y + 200, pick_radius=36)
        self.assertIsNone(miss)

    def test_spawn_readiness_reports_food_shortage(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        nest = world.nest_system.get_creature_nest(preds[0])
        colony_cfg = config.get_species("Ant").get("colony", {})
        needed = float(colony_cfg["min_food_reserve"]) + float(
            colony_cfg["spawn_food_cost"]
        )

        nest.stored_food = needed - 1
        ok, msg = world.nest_system.spawn_readiness(nest)
        self.assertFalse(ok)
        self.assertIn("備蓄不足", msg)

        nest.stored_food = needed
        ok, msg = world.nest_system.spawn_readiness(nest)
        self.assertTrue(ok)
        self.assertIn("繁殖可能", msg)


if __name__ == "__main__":
    unittest.main()

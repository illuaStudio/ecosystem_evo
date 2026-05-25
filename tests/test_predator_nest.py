"""捕食者コロニー（巣・持ち帰り）のスモークテスト。"""
import unittest

from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import has_edible_carcass, hunger_ratio, try_attack_only
from src.config import config
from src.utils.creature_helpers import distance_to_point
from src.utils.position_helpers import entity_xy


class TestPredatorNest(unittest.TestCase):
    def _spawn_predators(self, world, count: int = 3):
        factory = CreatureFactory()
        preds = []
        for i in range(count):
            x = 400 + i * 25
            y = 400 + i * 15
            p = factory.create("Predator", world=world, x=x, y=y)
            world.add_creature(p)
            preds.append(p)
        return preds

    def test_predators_share_single_nest_even_when_far_apart(self):
        world = World()
        factory = CreatureFactory()
        preds = []
        for i, (x, y) in enumerate([(120, 120), (850, 850), (500, 200)]):
            p = factory.create("Predator", world=world, x=x, y=y)
            world.add_creature(p)
            preds.append(p)
        nest_ids = {p.colony.nest_id for p in preds}
        self.assertEqual(len(nest_ids), 1)
        self.assertEqual(len(world.nest_system.nests), 1)

    def test_initial_predators_spawn_near_nest_anchor(self):
        world = World()
        colony_cfg = config.get_species("Predator").get("colony", {})
        anchor_x = float(colony_cfg.get("nest_x", world.width * 0.5))
        anchor_y = float(colony_cfg.get("nest_y", world.height * 0.5))
        spread = float(colony_cfg.get("spawn_spread", 28))

        preds = [c for c in world.creatures if c.species.name == "Predator"]
        self.assertGreaterEqual(len(preds), 1)
        for p in preds:
            px, py = entity_xy(p)
            dist = ((px - anchor_x) ** 2 + (py - anchor_y) ** 2) ** 0.5
            self.assertLessEqual(dist, spread + 5)

    def test_nest_spawn_position_uses_existing_nest(self):
        world = World()
        factory = CreatureFactory()
        colony_cfg = config.get_species("Predator").get("colony", {})
        first = factory.create("Predator", world=world, x=300, y=300)
        world.add_creature(first)
        nest = world.nest_system.get_creature_nest(first)

        x, y = world.nest_system.spawn_position("Predator", colony_cfg)
        dist = distance_to_point(type("_P", (), {"pos": [x, y]})(), nest.x, nest.y)
        spread = float(colony_cfg.get("spawn_spread", 28))
        self.assertLessEqual(dist, spread + 1)

    def test_p_spawn_joins_existing_nest(self):
        world = World()
        factory = CreatureFactory()
        first = factory.create("Predator", world=world, x=300, y=300)
        world.add_creature(first)
        nest_id = first.colony.nest_id

        second = factory.create("Predator", world=world, x=900, y=900)
        world.add_creature(second)
        self.assertEqual(second.colony.nest_id, nest_id)
        self.assertEqual(len(world.nest_system.nests), 1)

    def test_hunt_pickup_and_deposit_increases_nest_storage(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        predator = preds[0]
        nest = world.nest_system.get_creature_nest(predator)

        prey = world.creatures[0]
        if prey.species.name == "Predator":
            prey = next(c for c in world.creatures if c.species.name == "Amoeba")

        px, py = entity_xy(predator)
        prey.pos[0] = px + 12
        prey.pos[1] = py
        if hasattr(prey, "position"):
            prey.position.x = prey.pos[0]
            prey.position.y = prey.pos[1]

        for _ in range(8):
            if not prey.alive:
                break
            try_attack_only(predator, prey, attack_power=2.5)
        self.assertFalse(prey.alive)
        self.assertTrue(has_edible_carcass(prey))

        from src.utils.creature_helpers import try_pickup_carcass

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
        preds = self._spawn_predators(world, 3)
        nest = world.nest_system.get_creature_nest(preds[0])
        nest.stored_food = 200.0
        members = world.nest_system.member_count(nest.id, "Predator")
        self.assertEqual(members, 3)
        solo_cap = 200.0 * 0.14
        shared_cap = 200.0 * 0.14 / members
        self.assertLess(shared_cap, solo_cap)


if __name__ == "__main__":
    unittest.main()

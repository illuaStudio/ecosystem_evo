"""Spider（アリ捕食・食物連鎖頂点）のスモークテスト。"""
import unittest

from src.sim.ai.actions import ChaseAction, WanderAction
from src.config import config
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.creature_helpers import (
    has_edible_carcass,
    hunger_ratio,
    is_hungry,
    try_attack_only,
    try_pickup_carcass,
    try_predate,
)
from src.sim.utils.loot_helpers import find_nearest_field_loot_among, try_pickup_loot
from src.sim.utils.position_helpers import entity_xy
from tests.sim.legacy_corpse_helpers import become_legacy_corpse

ANT_PREY = (
    "red_ant",
    "red_ant_soldier",
    "red_ant_vanguard",
)


class TestSpider(unittest.TestCase):
    def test_spider_species_loaded(self):
        data = config.get_species("Spider")
        self.assertEqual(data.get("name"), "Spider")
        actions = data.get("mind", {}).get("actions", [])
        names = [a["name"] for a in actions]
        self.assertIn("ChaseAction", names)
        self.assertIn("WanderAction", names)
        chase = next(a for a in actions if a["name"] == "ChaseAction")
        self.assertEqual(chase["params"]["target_types"], list(ANT_PREY))
        self.assertNotIn("springtail", chase["params"]["target_types"])

    def test_spider_wanders(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)

        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=400, y=400)
        world.add_creature(spider)
        x0, y0 = entity_xy(spider)

        spider.current_action = WanderAction()
        for _ in range(40):
            spider.current_action.execute(spider)

        x1, y1 = entity_xy(spider)
        self.assertTrue((x0 - x1) ** 2 + (y0 - y1) ** 2 > 1.0)

    def test_spider_chases_ant_when_hungry(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)

        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=400, y=400)
        ant = factory.create("red_ant", world=world, x=430, y=400)
        world.add_creature(spider)
        world.add_creature(ant)

        spider.satiety = spider.max_satiety * 0.3
        self.assertTrue(is_hungry(spider))

        chase = ChaseAction(target_types=list(ANT_PREY))
        wander = WanderAction()
        self.assertGreater(chase.calculate_utility(spider), wander.calculate_utility(spider))

    def test_spider_ignores_amoeba_when_hungry(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)

        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=400, y=400)
        amoeba = factory.create("springtail", world=world, x=430, y=400)
        world.add_creature(spider)
        world.add_creature(amoeba)

        spider.satiety = spider.max_satiety * 0.3
        chase = ChaseAction(target_types=list(ANT_PREY))
        self.assertEqual(chase.calculate_utility(spider), 0.0)

    def test_spider_predates_ant_on_contact(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)

        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=400, y=400)
        ant = factory.create("red_ant", world=world, x=408, y=400)
        world.add_creature(spider)
        world.add_creature(ant)

        satiety_before = spider.satiety = spider.max_satiety * 0.2
        hunger_before = hunger_ratio(spider)

        for _ in range(80):
            if not ant.alive and not has_edible_carcass(ant):
                break
            try_predate(spider, ant, attack_power=1.5, bite_gain=1.4)

        self.assertFalse(ant.alive)
        self.assertGreater(spider.satiety, satiety_before)
        self.assertLess(hunger_ratio(spider), hunger_before)
        self.assertIsNone(getattr(spider, "colony", None))

    def test_chase_eats_carcass_sandwiched_without_long_freeze(self):
        """上下の死骸に挟まれても、接触圏内で満腹度が回復する（standoff 張り付き防止）。"""
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)

        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=500, y=500)
        top = factory.create("red_ant", world=world, x=500, y=433)
        bottom = factory.create("red_ant", world=world, x=500, y=567)
        for carcass in (top, bottom):
            become_legacy_corpse(carcass)
            carcass.remaining_mass = 60.0
        world.add_creature(spider)
        world.add_creature(top)
        world.add_creature(bottom)

        spider.satiety = spider.max_satiety * 0.01
        spider.nutrition_recovery = True

        freeze_at_starvation = 0
        for tick in range(120):
            sat_before = spider.satiety
            spider.update(1.0)
            if (
                type(spider.current_action).__name__ == "ChaseAction"
                and spider.satiety <= sat_before + 0.05
                and spider.satiety < spider.max_satiety * 0.1
            ):
                freeze_at_starvation += 1

        self.assertGreater(spider.satiety, spider.max_satiety * 0.3)
        self.assertLess(freeze_at_starvation, 30)

    def test_ant_hunts_spider_kill_pickup_deposit(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)

        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        spider = factory.create("Spider", world=world, x=512, y=500)
        world.add_creature(ant)
        world.add_creature(spider)

        nest = world.nest_system.get_creature_nest(ant)
        self.assertGreater(spider.max_hp, ant.max_hp)

        for _ in range(500):
            if spider not in world.creatures:
                break
            try_attack_only(ant, spider, attack_power=1.25)

        loot = find_nearest_field_loot_among(ant, ("Spider",))
        self.assertIsNotNone(loot)
        self.assertTrue(try_pickup_loot(ant, loot))
        deposited = world.nest_system.deposit_carried(ant)
        self.assertGreater(deposited, 0)
        self.assertGreater(nest.stored_mass, 0)


if __name__ == "__main__":
    unittest.main()

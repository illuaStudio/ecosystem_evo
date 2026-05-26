"""Spider（フェーズ1: 徘徊する大型獲物）のスモークテスト。"""
import unittest

from src.ai.actions import WanderAction
from src.config import config
from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import (
    has_edible_carcass,
    try_attack_only,
    try_pickup_carcass,
)
from src.utils.position_helpers import entity_xy


class TestSpider(unittest.TestCase):
    def test_spider_species_loaded(self):
        data = config.get_species("Spider")
        self.assertEqual(data.get("name"), "Spider")
        actions = data.get("mind", {}).get("actions", [])
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["name"], "WanderAction")

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

    def test_ant_hunts_spider_kill_pickup_deposit(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)

        factory = CreatureFactory()
        ant = factory.create("Ant", world=world, x=500, y=500)
        spider = factory.create("Spider", world=world, x=512, y=500)
        world.add_creature(ant)
        world.add_creature(spider)

        nest = world.nest_system.get_creature_nest(ant)
        self.assertGreater(spider.max_hp, ant.max_hp)

        for _ in range(500):
            if not spider.alive:
                break
            try_attack_only(ant, spider, attack_power=1.25)

        self.assertFalse(spider.alive)
        self.assertTrue(has_edible_carcass(spider))
        self.assertTrue(try_pickup_carcass(ant, spider))
        deposited = world.nest_system.deposit_carried(ant)
        self.assertGreater(deposited, 0)
        self.assertGreater(nest.stored_food, 0)


if __name__ == "__main__":
    unittest.main()

"""複数アリが地面バイオマスに張り付く問題の回帰テスト。"""
import unittest

from src.game.ai.colony_actions import ReturnToNestAction
from src.game.ai.hunt_actions import HuntAction
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.game.affiliation_feed import nest_has_usable_storage
from src.sim.utils.creature_helpers import is_edible_prey
from tests.sim.field_drop_helpers import kill_creature, pickup_field_biomass
from src.sim.utils.inventory_helpers import inventory_is_loaded


class TestHuntCarcassStuck(unittest.TestCase):
    def test_multiple_ants_pickup_without_stale_target(self):
        world = World()
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=600, y=600)
        world.add_creature(spider)
        loot = kill_creature(world, spider)
        self.assertIsNotNone(loot)

        ants = []
        for i in range(4):
            ant = factory.create("red_ant", world=world, x=600 + i * 4, y=600)
            ant.satiety = ant.max_satiety * 0.95
            world.add_creature(ant)
            ants.append(ant)

        hunt = HuntAction(target_types=["Spider"])
        for _ in range(30):
            for ant in ants:
                ant.current_action = hunt
                hunt.completed = False
                hunt._target = loot
                hunt.execute(ant)

        carriers = [a for a in ants if inventory_is_loaded(a)]
        self.assertGreaterEqual(len(carriers), 1)

    def test_carrier_switches_to_return_after_pickup(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        ant.satiety = ant.max_satiety * 0.95
        world.add_creature(ant)

        prey = factory.create("springtail", world=world, x=512, y=500)
        world.add_creature(prey)
        loot = kill_creature(world, prey, ant)
        self.assertTrue(pickup_field_biomass(ant, loot))

        hunt = HuntAction(target_types=["springtail", "Spider"])
        ret = ReturnToNestAction()
        self.assertEqual(hunt.calculate_utility(ant), 0.0)
        self.assertGreater(ret.calculate_utility(ant), 0.0)

    def test_off_field_pickup_not_trackable(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        world.add_creature(ant)

        prey = factory.create("springtail", world=world, x=512, y=500)
        world.add_creature(prey)
        loot = kill_creature(world, prey)
        world.world_object_system.remove_instance(loot.id)

        hunt = HuntAction(target_types=["springtail"])
        hunt._target = loot
        from src.sim.utils.creature_helpers import is_trackable_prey

        self.assertFalse(is_trackable_prey(ant, loot, ("springtail",)))

    def test_defense_hunt_ignores_dead_spider_loot(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=120, y=100)
        world.add_creature(soldier)

        spider = factory.create("Spider", world=world, x=150, y=100)
        world.add_creature(spider)
        kill_creature(world, spider)

        hunt = HuntAction(target_types=["Spider"], defense_hunt=True)
        self.assertFalse(
            is_edible_prey(soldier, spider, ("Spider",), living_only=True)
        )
        self.assertEqual(hunt.calculate_utility(soldier), 0.0)

    def test_worker_hunt_spider_pickup_only(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        ant.satiety = ant.max_satiety * 0.95
        world.add_creature(ant)

        live = factory.create("Spider", world=world, x=520, y=500)
        world.add_creature(live)

        hunt = HuntAction(
            target_types=["springtail", "Spider"],
            carcass_only_species=["Spider"],
        )
        self.assertEqual(hunt._find_prey(ant, ("springtail", "Spider")), None)

        loot = kill_creature(world, live)
        self.assertIs(hunt._find_prey(ant, ("springtail", "Spider")), loot)
        self.assertGreater(hunt.calculate_utility(ant), 0.0)

    def test_worker_prefers_nearby_pickup_over_farther_living_prey(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        ant.satiety = ant.max_satiety * 0.95
        world.add_creature(ant)

        dead_prey = factory.create("springtail", world=world, x=508, y=500)
        world.add_creature(dead_prey)
        near_loot = kill_creature(world, dead_prey)

        live_prey = factory.create("springtail", world=world, x=540, y=500)
        world.add_creature(live_prey)

        hunt = HuntAction(
            target_types=["springtail", "Spider"],
            carcass_only_species=["Spider"],
        )
        self.assertIs(hunt._find_prey(ant, ("springtail", "Spider")), near_loot)

    def test_worker_hunts_living_prey_when_closer_than_pickup(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        world.add_creature(ant)

        live_prey = factory.create("springtail", world=world, x=508, y=500)
        world.add_creature(live_prey)

        spider = factory.create("Spider", world=world, x=540, y=500)
        world.add_creature(spider)
        kill_creature(world, spider)

        hunt = HuntAction(
            target_types=["springtail", "Spider"],
            carcass_only_species=["Spider"],
        )
        self.assertIs(hunt._find_prey(ant, ("springtail", "Spider")), live_prey)

    def test_hungry_worker_hunts_spider_pickup_despite_nest_food(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        ant.satiety = ant.max_satiety * 0.08
        world.add_creature(ant)

        spider = factory.create("Spider", world=world, x=520, y=500)
        world.add_creature(spider)
        kill_creature(world, spider)

        self.assertTrue(nest_has_usable_storage(ant))

        hunt = HuntAction(
            target_types=["springtail", "Spider"],
            carcass_only_species=["Spider"],
        )
        self.assertGreater(hunt.calculate_utility(ant), 0.0)


if __name__ == "__main__":
    unittest.main()

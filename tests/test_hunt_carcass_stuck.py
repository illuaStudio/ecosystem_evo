"""複数アリが死骸に張り付く問題の回帰テスト。"""
import unittest

from src.ai.actions import HuntAction, ReturnToNestAction
from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import (
    carcass_on_field,
    is_edible_prey,
    nest_has_usable_food,
    try_attack_only,
    try_pickup_carcass,
)
from src.utils.position_helpers import entity_xy


class TestHuntCarcassStuck(unittest.TestCase):
    def _place_near(self, creature, x, y):
        creature.pos[0] = x
        creature.pos[1] = y
        if hasattr(creature, "position"):
            creature.position.x = x
            creature.position.y = y

    def test_multiple_ants_pickup_without_stale_target(self):
        world = World()
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=600, y=600)
        world.add_creature(spider)
        spider.hp = 0
        spider.become_corpse()

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
                hunt._target = spider
                hunt.execute(ant)

        carriers = [a for a in ants if a.colony.is_carrying]
        self.assertGreaterEqual(len(carriers), 1)
        self.assertTrue(carcass_on_field(world, spider) or len(carriers) >= 2)

    def test_carrier_switches_to_return_after_pickup(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        ant.satiety = ant.max_satiety * 0.95
        world.add_creature(ant)

        prey = factory.create("Amoeba", world=world, x=512, y=500)
        world.add_creature(prey)
        for _ in range(12):
            if not prey.alive:
                break
            try_attack_only(ant, prey, attack_power=2.5)
        self.assertTrue(try_pickup_carcass(ant, prey))

        hunt = HuntAction(target_types=["Amoeba", "Spider"])
        ret = ReturnToNestAction()
        self.assertEqual(hunt.calculate_utility(ant), 0.0)
        self.assertGreater(ret.calculate_utility(ant), 0.0)

    def test_off_field_carcass_not_trackable(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        world.add_creature(ant)

        prey = factory.create("Amoeba", world=world, x=512, y=500)
        prey.become_corpse()
        world.remove_creature(prey)

        hunt = HuntAction(target_types=["Amoeba"])
        hunt._target = prey
        from src.utils.creature_helpers import is_trackable_prey

        self.assertFalse(is_trackable_prey(ant, prey, ("Amoeba",)))

    def test_defense_hunt_ignores_dead_spider(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=120, y=100)
        world.add_creature(soldier)

        spider = factory.create("Spider", world=world, x=150, y=100)
        spider.become_corpse()
        spider.remaining_biomass = 500.0
        world.add_creature(spider)

        hunt = HuntAction(target_types=["Spider"], defense_hunt=True)
        self.assertFalse(is_edible_prey(soldier, spider, ("Spider",), living_only=True))
        self.assertEqual(hunt.calculate_utility(soldier), 0.0)

    def test_worker_hunt_spider_carcass_only(self):
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
            target_types=["Amoeba", "Spider"],
            carcass_only_species=["Spider"],
        )
        self.assertEqual(hunt._find_prey(ant, ("Amoeba", "Spider")), None)

        live.alive = False
        live.remaining_biomass = 200.0
        self.assertIs(hunt._find_prey(ant, ("Amoeba", "Spider")), live)
        self.assertGreater(hunt.calculate_utility(ant), 0.0)

    def test_worker_prefers_nearby_carcass_over_farther_living_prey(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        ant.satiety = ant.max_satiety * 0.95
        world.add_creature(ant)

        dead_amoeba = factory.create("Amoeba", world=world, x=508, y=500)
        dead_amoeba.become_corpse()
        dead_amoeba.remaining_biomass = 80.0
        world.add_creature(dead_amoeba)

        live_amoeba = factory.create("Amoeba", world=world, x=540, y=500)
        world.add_creature(live_amoeba)

        hunt = HuntAction(
            target_types=["Amoeba", "Spider"],
            carcass_only_species=["Spider"],
        )
        self.assertIs(hunt._find_prey(ant, ("Amoeba", "Spider")), dead_amoeba)

    def test_worker_hunts_living_prey_when_closer_than_carcass(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        world.add_creature(ant)

        live_amoeba = factory.create("Amoeba", world=world, x=508, y=500)
        world.add_creature(live_amoeba)

        spider = factory.create("Spider", world=world, x=540, y=500)
        spider.become_corpse()
        spider.remaining_biomass = 800.0
        world.add_creature(spider)

        hunt = HuntAction(
            target_types=["Amoeba", "Spider"],
            carcass_only_species=["Spider"],
        )
        self.assertIs(hunt._find_prey(ant, ("Amoeba", "Spider")), live_amoeba)

    def test_hungry_worker_hunts_spider_carcass_despite_nest_food(self):
        world = World()
        for c in list(world.creatures):
            world.remove_creature(c)
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        ant.satiety = ant.max_satiety * 0.08
        world.add_creature(ant)

        spider = factory.create("Spider", world=world, x=520, y=500)
        spider.become_corpse()
        spider.remaining_biomass = 400.0
        world.add_creature(spider)

        self.assertTrue(nest_has_usable_food(ant))

        hunt = HuntAction(
            target_types=["Amoeba", "Spider"],
            carcass_only_species=["Spider"],
        )
        self.assertGreater(hunt.calculate_utility(ant), 0.0)


if __name__ == "__main__":
    unittest.main()

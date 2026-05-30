"""?????????????????"""
import unittest

from src.ai.actions import CombatAction, FleeAction, HuntAction
from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import (
    find_nearest_flee_threat_among,
    is_creature_threatening_territory,
    is_in_creature_territory,
    needs_self_feed,
)


def _colony_world() -> World:
    return World.from_json(
        {
            "name": "TerritoryTest",
            "world_width": 1000,
            "world_height": 1000,
            "initial_entities": {},
            "population_limits": {
                "red_ant": 20,
                "red_ant_soldier": 10,
                "blue_ant": 20,
                "blue_ant_soldier": 10,
                "yellow_ant": 20,
                "yellow_ant_soldier": 10,
                "Spider": 10,
            },
        }
    )


class TestTerritoryAndCastes(unittest.TestCase):
    def test_soldier_joins_worker_nest(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=110, y=100)
        world.add_creature(soldier)

        worker_nest = world.nest_system.get_creature_nest(worker)
        soldier_nest = world.nest_system.get_creature_nest(soldier)
        self.assertIsNotNone(worker_nest)
        self.assertIs(soldier_nest, worker_nest)

    def test_territory_radius_default(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=200, y=200)
        world.add_creature(worker)

        self.assertTrue(is_in_creature_territory(worker, worker))
        near = factory.create("blue_ant", world=world, x=250, y=200)
        world.add_creature(near)
        self.assertTrue(is_in_creature_territory(worker, near))

        far = factory.create("blue_ant", world=world, x=500, y=500)
        world.add_creature(far)
        self.assertFalse(is_in_creature_territory(worker, far))

    def test_combat_territory_only(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=105, y=100)
        world.add_creature(soldier)

        inside = factory.create("blue_ant", world=world, x=160, y=100)
        world.add_creature(inside)

        action = CombatAction(
            hostile_species=["blue_ant"],
            territory_only=True,
        )
        self.assertGreater(action.calculate_utility(soldier), 0.0)

    def test_soldier_combat_via_hostile_colony_ids(self):
        world = _colony_world()
        world.faction_species = {
            "red_ant": ["red_ant", "red_ant_soldier"],
            "blue_ant": ["blue_ant", "blue_ant_soldier"],
            "yellow_ant": ["yellow_ant", "yellow_ant_soldier"],
        }
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=105, y=100)
        world.add_creature(soldier)
        intruder = factory.create("yellow_ant", world=world, x=165, y=100)
        world.add_creature(intruder)

        action = CombatAction(
            hostile_colony_ids=["blue_ant", "yellow_ant"],
            territory_only=True,
        )
        foes = action._enemies(soldier)
        self.assertIn("yellow_ant", foes)
        self.assertGreater(action.calculate_utility(soldier), 0.0)

    def test_worker_flees_from_soldier_and_spider(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=300, y=300)
        world.add_creature(worker)

        soldier = factory.create("blue_ant_soldier", world=world, x=320, y=300)
        world.add_creature(soldier)

        threat = find_nearest_flee_threat_among(
            worker, ["blue_ant_soldier", "Spider"]
        )
        self.assertIs(threat, soldier)

        flee = FleeAction(threat_species=["blue_ant_soldier", "Spider"])
        self.assertGreater(flee.calculate_utility(worker), 0.0)

    def test_worker_hunt_amoeba_only(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        amoeba = factory.create("Amoeba", world=world, x=150, y=100)
        world.add_creature(amoeba)

        hunt = HuntAction(target_types=["Amoeba"])
        self.assertGreater(hunt.calculate_utility(worker), 0.0)

    def test_soldier_hunts_spider_in_territory_only(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=105, y=100)
        world.add_creature(soldier)

        inside = factory.create("Spider", world=world, x=170, y=100)
        world.add_creature(inside)

        hunt = HuntAction(
            target_types=["Spider"],
            pickup_on_kill=False,
            territory_only=True,
        )
        prey = hunt._find_prey(soldier, ("Spider",))
        self.assertIs(prey, inside)

    def test_defense_hunt_spider_outside_territory_in_vision(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=105, y=100)
        world.add_creature(soldier)

        outside = factory.create("Spider", world=world, x=320, y=100)
        world.add_creature(outside)
        self.assertFalse(is_in_creature_territory(soldier, outside))

        hunt = HuntAction(
            target_types=["Spider"],
            defense_hunt=True,
            territory_only=False,
        )
        self.assertIs(hunt._find_prey(soldier, ("Spider",)), outside)
        soldier.satiety = soldier.max_satiety * 0.1
        self.assertTrue(needs_self_feed(soldier))
        self.assertGreater(hunt.calculate_utility(soldier), 0.0)

    def test_spider_approaching_territory_is_threat(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=105, y=100)
        world.add_creature(soldier)

        approaching = factory.create("Spider", world=world, x=285, y=100)
        world.add_creature(approaching)
        self.assertFalse(is_in_creature_territory(soldier, approaching))
        self.assertTrue(
            is_creature_threatening_territory(soldier, approaching, 90.0)
        )


if __name__ == "__main__":
    unittest.main()

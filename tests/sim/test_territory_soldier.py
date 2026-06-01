"""??????????????????"""
import math
import unittest

from src.sim.ai.actions import CombatAction, FleeAction, HuntAction
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.creature_helpers import (
    find_nearest_flee_threat_among,
    is_creature_threatening_territory,
    is_in_creature_territory,
    needs_self_feed,
)
from src.sim.utils.position_helpers import entity_xy
from tests.sim.world_fixtures import affiliation_settings, load_test_world


def _colony_world() -> World:
    return load_test_world(
        name="TerritoryTest",
        population_limits={
            "red_ant": 20,
            "red_ant_soldier": 10,
            "blue_ant": 20,
            "blue_ant_soldier": 10,
            "yellow_ant": 20,
            "yellow_ant_soldier": 10,
            "Spider": 10,
        },
        affiliation=affiliation_settings(
            affiliation_species={
                "red_ant": ["red_ant", "red_ant_soldier"],
                "blue_ant": ["blue_ant", "blue_ant_soldier"],
                "yellow_ant": ["yellow_ant", "yellow_ant_soldier"],
            },
        ),
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

    def test_soldier_combat_via_hostile_affiliation_ids(self):
        world = _colony_world()
        world.affiliation_species = {
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
            hostile_affiliation_ids=["blue_ant", "yellow_ant"],
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
        amoeba = factory.create("springtail", world=world, x=150, y=100)
        world.add_creature(amoeba)

        hunt = HuntAction(target_types=["springtail"])
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
        worker = factory.create("red_ant", world=world, x=120, y=120)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=125, y=120)
        world.add_creature(soldier)

        nest = world.nest_system.get_creature_nest(soldier)
        territory_r = float(world.affiliation_profiles["red_ant"]["territory_radius"])
        vision = soldier.get_current_vision()
        sx, sy = entity_xy(soldier)
        from src.sim.utils.world_object_helpers import iter_affiliation_access_xy

        tcx, _tcy = iter_affiliation_access_xy(world, nest.affiliation_id)[0]
        min_outside_x = tcx + territory_r + 5
        max_in_vision_x = sx + vision * 0.92
        self.assertGreater(
            max_in_vision_x,
            min_outside_x,
            "????????????????????????",
        )
        spider_x = (min_outside_x + max_in_vision_x) * 0.5
        outside = factory.create("Spider", world=world, x=spider_x, y=sy)
        world.add_creature(outside)
        self.assertFalse(is_in_creature_territory(soldier, outside))
        self.assertLessEqual(
            math.hypot(spider_x - sx, sy - sy),
            vision,
        )

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

        approaching = factory.create("Spider", world=world, x=310, y=100)
        world.add_creature(approaching)
        self.assertFalse(is_in_creature_territory(soldier, approaching))
        self.assertTrue(
            is_creature_threatening_territory(soldier, approaching, 90.0)
        )


if __name__ == "__main__":
    unittest.main()

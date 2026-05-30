"""SeekShelterAction: 巣に隠れる・標的除外・敗北時の隠れ個体死亡。"""
import math
import unittest

from src.sim.ai.actions import SeekShelterAction
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.shelter.helpers import enter_creature_shelter, resolve_nest_shelter
from src.sim.shelter.state import clear_creature_shelter, is_creature_sheltered
from src.sim.shelter.types import ShelterRef
from src.sim.utils.combat_helpers import bite
from src.sim.utils.creature_helpers import is_trackable_prey
from src.sim.utils.movement_helpers import update_flee_latch
from src.sim.utils.position_helpers import entity_xy
from tests.sim.test_hole_combat import _hole_world


class TestSeekShelter(unittest.TestCase):
    def test_sheltered_ant_not_trackable_prey(self):
        world = _hole_world()
        factory = CreatureFactory()
        ant = factory.create("blue_ant", world=world, x=500, y=820)
        world.add_creature(ant)
        spider = factory.create("Spider", world=world, x=600, y=820)
        world.add_creature(spider)

        ref = resolve_nest_shelter(ant)
        self.assertIsNotNone(ref)
        enter_creature_shelter(ant, ref)

        self.assertTrue(is_creature_sheltered(ant))
        self.assertFalse(is_trackable_prey(spider, ant, ("blue_ant",)))

    def test_bite_ignores_sheltered_target(self):
        world = _hole_world()
        factory = CreatureFactory()
        ant = factory.create("blue_ant", world=world, x=500, y=820)
        world.add_creature(ant)
        spider = factory.create("Spider", world=world, x=501, y=820)
        world.add_creature(spider)

        ref = resolve_nest_shelter(ant)
        enter_creature_shelter(ant, ref)
        hp_before = ant.hp
        bite(spider, ant, attack_power=2.0)
        self.assertEqual(ant.hp, hp_before)

    def test_sheltered_ant_does_not_move_when_spider_on_nest(self):
        world = _hole_world()
        factory = CreatureFactory()
        ant = factory.create("blue_ant", world=world, x=500, y=820)
        world.add_creature(ant)
        spider = factory.create("Spider", world=world, x=500, y=820)
        world.add_creature(spider)

        ref = resolve_nest_shelter(ant)
        self.assertIsNotNone(ref)
        enter_creature_shelter(ant, ref)
        ax0, ay0 = entity_xy(ant)

        action = SeekShelterAction(
            threat_species=["Spider"], speed_multiplier=1.55
        )
        update_flee_latch(ant, ("Spider",))
        action.execute(ant)
        ax1, ay1 = entity_xy(ant)
        self.assertAlmostEqual(ax0, ax1, places=2)
        self.assertAlmostEqual(ay0, ay1, places=2)

    def test_threat_on_nest_blocks_approach_direction(self):
        world = _hole_world()
        factory = CreatureFactory()
        ant = factory.create("blue_ant", world=world, x=400, y=820)
        world.add_creature(ant)
        spider = factory.create("Spider", world=world, x=500, y=820)
        world.add_creature(spider)

        nest = world.nest_system.get_creature_nest(ant)
        hole = nest.holes[0]
        spider.position.x = hole.x
        spider.position.y = hole.y

        ref = resolve_nest_shelter(ant, spider)
        self.assertIsNone(ref)

        ax0, ay0 = entity_xy(ant)
        action = SeekShelterAction(
            threat_species=["Spider"], speed_multiplier=1.55
        )
        update_flee_latch(ant, ("Spider",))
        action.execute(ant)
        ax1, ay1 = entity_xy(ant)
        dist_after = math.hypot(ax1 - spider.position.x, ay1 - spider.position.y)
        dist_before = math.hypot(ax0 - spider.position.x, ay0 - spider.position.y)
        self.assertGreaterEqual(dist_after, dist_before - 1e-6)

    def test_defeat_kills_sheltered_worker_not_exposed_soldier(self):
        world = _hole_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=120, y=120)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=200, y=200)
        world.add_creature(soldier)

        ref = resolve_nest_shelter(worker)
        enter_creature_shelter(worker, ref)

        nest = world.nest_system.get_creature_nest(worker)
        hole = nest.holes[0]
        world.nest_system.damage_hole(nest, hole, 500, attacker_colony_id="blue_ant")

        self.assertLessEqual(worker.hp, 0.0)
        self.assertTrue(soldier.alive)
        self.assertGreater(soldier.hp, 0.0)
        clear_creature_shelter(worker)


if __name__ == "__main__":
    unittest.main()

"""巣穴 HP・敵テリトリー重なり・敗北のテスト。"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.colony_helpers import (
    can_attack_hole,
    find_nearest_attackable_hole,
    is_point_in_rival_territory,
    is_colony_defeated,
)
from tests.sim.world_fixtures import colony_settings


def _hole_world(**overrides) -> World:
    data = {
        "name": "HoleCombatTest",
        "world_width": 1000,
        "world_height": 1000,
        "initial_entities": {},
        "population_limits": {
            "red_ant": 10,
            "red_ant_soldier": 6,
            "red_ant_vanguard": 4,
            "blue_ant": 10,
            "blue_ant_soldier": 6,
            "blue_ant_vanguard": 4,
        },
        "colony": colony_settings(
            hole_max_hp=100,
            faction_species={
                "red_ant": ["red_ant", "red_ant_soldier", "red_ant_vanguard"],
                "blue_ant": ["blue_ant", "blue_ant_soldier", "blue_ant_vanguard"],
            },
        ),
    }
    data.update(overrides)
    return World.from_json(data)


class TestHoleCombat(unittest.TestCase):
    def test_hole_has_hp_on_create(self):
        world = _hole_world()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(ant)
        nest = world.nest_system.get_creature_nest(ant)
        self.assertEqual(len(nest.holes), 1)
        self.assertAlmostEqual(nest.holes[0].hp, 100.0)

    def test_cannot_place_in_rival_territory(self):
        world = _hole_world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(red)
        blue = factory.create("blue_ant", world=world, x=500, y=500)
        world.add_creature(blue)
        red_nest = world.nest_system.get_creature_nest(red)
        red_nest.stored_food = 5000

        bx, by = 500.0, 500.0
        self.assertTrue(is_point_in_rival_territory(world, "red_ant", bx, by))
        ok, msg = world.nest_system.can_place_hole(red_nest, bx, by)
        self.assertFalse(ok)
        self.assertTrue(msg)

    def test_hole_hp_not_regenerated_on_update(self):
        world = _hole_world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(red)
        nest = world.nest_system.get_creature_nest(red)
        hole = nest.holes[0]
        hole.hp = 40.0
        world.nest_system.update(100.0)
        self.assertAlmostEqual(hole.hp, 40.0)

    def test_low_hp_finishing_blow_removes_hole(self):
        world = _hole_world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(red)
        nest = world.nest_system.get_creature_nest(red)
        hole = nest.holes[0]
        hole.hp = 0.8
        world.nest_system.damage_hole(nest, hole, 0.1, attacker_colony_id="blue_ant")
        self.assertEqual(len(nest.holes), 0)

    def test_damage_hole_only_from_rival(self):
        world = _hole_world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(red)
        nest = world.nest_system.get_creature_nest(red)
        hole = nest.holes[0]

        dealt = world.nest_system.damage_hole(nest, hole, 50, attacker_colony_id="red_ant")
        self.assertEqual(dealt, 0.0)
        self.assertAlmostEqual(hole.hp, 100.0)

        dealt = world.nest_system.damage_hole(nest, hole, 40, attacker_colony_id="blue_ant")
        self.assertEqual(dealt, 40.0)

    def test_last_hole_destroyed_defeats_colony_keeps_creatures(self):
        world = _hole_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=200, y=200)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=210, y=200)
        world.add_creature(soldier)
        nest = world.nest_system.get_creature_nest(worker)
        hole = nest.holes[0]

        world.nest_system.damage_hole(nest, hole, 200, attacker_colony_id="blue_ant")

        self.assertTrue(is_colony_defeated(world, "red_ant"))
        self.assertIsNone(world.nest_system.get_colony_nest("red_ant"))
        self.assertTrue(worker.colony.defeated)
        self.assertTrue(soldier.colony.defeated)
        self.assertEqual(len(world.creatures), 2)

    def test_attack_hole_yields_when_intruder_in_territory(self):
        from src.sim.ai.actions import AttackHoleAction, CombatAction

        world = _hole_world()
        factory = CreatureFactory()
        red_w = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(red_w)
        red_s = factory.create("red_ant_soldier", world=world, x=105, y=100)
        world.add_creature(red_s)
        blue_w = factory.create("blue_ant", world=world, x=150, y=100)
        world.add_creature(blue_w)

        combat = CombatAction(
            hostile_colony_ids=["blue_ant"], territory_only=True
        )
        attack_hole = AttackHoleAction(hostile_colony_ids=["blue_ant"])
        self.assertGreater(combat.calculate_utility(red_s), 0.0)
        self.assertEqual(attack_hole.calculate_utility(red_s), 0.0)

    def test_defensive_soldier_cannot_attack_distant_enemy_hole(self):
        world = _hole_world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(red)
        blue = factory.create("blue_ant", world=world, x=500, y=500)
        world.add_creature(blue)
        soldier = factory.create("red_ant_soldier", world=world, x=110, y=100)
        world.add_creature(soldier)
        blue_nest = world.nest_system.get_creature_nest(blue)
        hole = blue_nest.holes[0]
        self.assertFalse(can_attack_hole(soldier, hole, "blue_ant"))
        self.assertIsNone(find_nearest_attackable_hole(soldier, ("blue_ant",)))

    def test_vanguard_only_targets_holes_in_vision(self):
        from src.sim.ai.actions import AttackHoleAction

        world = _hole_world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(red)
        blue = factory.create("blue_ant", world=world, x=500, y=500)
        world.add_creature(blue)
        vanguard_far = factory.create("red_ant_vanguard", world=world, x=110, y=110)
        world.add_creature(vanguard_far)
        blue_nest = world.nest_system.get_creature_nest(blue)
        hole = blue_nest.holes[0]

        self.assertIsNone(
            find_nearest_attackable_hole(
                vanguard_far, ("blue_ant",), unrestricted=True
            )
        )
        action = AttackHoleAction(
            hostile_colony_ids=["blue_ant"],
            ignore_territory=True,
            yield_to_intruders=False,
            nest_leash_radius=None,
        )
        self.assertEqual(action.calculate_utility(vanguard_far), 0.0)

        vanguard_near = factory.create("red_ant_vanguard", world=world, x=480, y=480)
        world.add_creature(vanguard_near)
        pair = find_nearest_attackable_hole(
            vanguard_near, ("blue_ant",), unrestricted=True
        )
        self.assertIsNotNone(pair)
        self.assertIs(pair[0], hole)
        self.assertGreater(action.calculate_utility(vanguard_near), 0.0)

    def test_attack_hole_leash_pulls_back_when_configured(self):
        from src.sim.ai.actions import AttackHoleAction

        world = _hole_world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(red)
        blue = factory.create("blue_ant", world=world, x=400, y=400)
        world.add_creature(blue)
        vanguard = factory.create("red_ant_vanguard", world=world, x=300, y=100)
        world.add_creature(vanguard)
        ns = world.nest_system
        self.assertGreater(ns.distance_to_nest(vanguard), 165)
        action = AttackHoleAction(
            hostile_colony_ids=["blue_ant"],
            ignore_territory=True,
            nest_leash_radius=165,
        )
        self.assertEqual(action.calculate_utility(vanguard), 0.0)


if __name__ == "__main__":
    unittest.main()

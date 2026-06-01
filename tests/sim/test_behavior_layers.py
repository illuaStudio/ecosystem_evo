"""Behavior 3 層（Directive / PostLife / Mind）のテスト。"""
import unittest

from src.sim.behavior import (
    MoveToDirective,
    PostLifeRunner,
    normalize_death_policy,
    set_creature_death_policy,
)
from src.sim.bridge import SimBridge
from src.sim.commands import ClearCreatureDirective, IssueCreatureDirective
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.entities.species import expand_death_policy_content
from src.sim.systems.world import World
from src.sim.utils.position_helpers import entity_xy


class TestDeathPolicy(unittest.TestCase):
    def test_unset_policy_runs_no_post_life_parts(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=10, y=10)
        world.add_creature(ant)
        set_creature_death_policy(ant, [])
        ant.become_corpse()
        self.assertFalse(ant.alive)
        self.assertEqual(len(world.world_object_system.iter_field_pickups()), 0)
        world.update(1.0)
        self.assertNotIn(ant, world.creatures)

    def test_species_field_drop_policy_spawns_pickup(self):
        world = World()
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=100, y=100)
        world.add_creature(spider)
        spider.become_corpse()
        self.assertFalse(spider.alive)
        self.assertNotIn(spider, world.creatures)
        pickups = [
            o for o in world.world_object_system.iter_field_pickups()
        ]
        self.assertEqual(len(pickups), 1)
        self.assertGreater(pickups[0].amount_for_kind("biomass"), 0.0)

    def test_immediate_remove_policy(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("Red Ant", world=world, x=50, y=50)
        world.add_creature(ant)
        set_creature_death_policy(ant, "immediate_remove")
        ant.become_corpse()
        self.assertNotIn(ant, world.creatures)

    def test_expand_death_policy_aliases(self):
        self.assertEqual(normalize_death_policy(None), ())
        self.assertEqual(
            normalize_death_policy(expand_death_policy_content("unknown_alias")),
            (),
        )
        self.assertEqual(
            normalize_death_policy(expand_death_policy_content("field_drop")),
            ({"step": "spawn_drop", "type": "field_bulk"}, "remove"),
        )
        self.assertEqual(
            normalize_death_policy(expand_death_policy_content("remove")),
            ("remove",),
        )


class TestPostLifeDecompose(unittest.TestCase):
    def test_loot_decompose_via_world_update(self):
        world = World()
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=100, y=100)
        world.add_creature(spider)
        spider.become_corpse()
        pickups = list(world.world_object_system.iter_field_pickups())
        self.assertEqual(len(pickups), 1)
        initial = pickups[0].amount_for_kind("biomass")

        ticks = 0
        while world.world_object_system.iter_field_pickups() and ticks < 5000:
            world.world_object_system.update_field_objects(10.0)
            ticks += 1

        self.assertGreater(ticks, 0)
        self.assertEqual(len(world.world_object_system.iter_field_pickups()), 0)


class TestSharedParts(unittest.TestCase):
    def test_warp_directive(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("Red Ant", world=world, x=10, y=10)
        world.add_creature(ant)
        bridge = SimBridge(world)

        ok = bridge.execute(
            IssueCreatureDirective(
                creature_id=id(ant),
                kind="warp_to",
                x=250,
                y=180,
            )
        )
        self.assertTrue(ok.ok)
        ant.update(1.0)
        self.assertTrue(ant.directive.is_done())
        x, y = entity_xy(ant)
        self.assertAlmostEqual(x, 250.0, places=1)
        self.assertAlmostEqual(y, 180.0, places=1)

    def test_warp_in_death_policy(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("Red Ant", world=world, x=10, y=10)
        world.add_creature(ant)
        set_creature_death_policy(
            ant,
            {
                "steps": [
                    {"step": "warp_to", "x": 400, "y": 300},
                    "remove",
                ]
            },
        )
        ant.become_corpse()
        x, y = entity_xy(ant)
        self.assertAlmostEqual(x, 400.0, places=1)
        self.assertAlmostEqual(y, 300.0, places=1)
        self.assertNotIn(ant, world.creatures)


class TestDirective(unittest.TestCase):
    def test_move_to_directive_reaches_target(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("Red Ant", world=world, x=10, y=10)
        world.add_creature(ant)
        ant.set_directive(
            MoveToDirective(120, 120, arrival_radius=12.0, speed_multiplier=2.0)
        )

        for _ in range(800):
            if ant.directive.is_done():
                break
            ant.update(1.0)

        self.assertTrue(ant.directive.is_done())
        x, y = entity_xy(ant)
        self.assertLess(((x - 120) ** 2 + (y - 120) ** 2) ** 0.5, 15.0)

    def test_directive_blocks_mind_while_active(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("Red Ant", world=world, x=10, y=10)
        world.add_creature(ant)
        ant.set_directive(MoveToDirective(500, 500, speed_multiplier=0.1))

        ant.update(1.0)
        self.assertFalse(ant.directive.is_done())
        self.assertIsNone(ant.current_action)

    def test_sim_bridge_issue_and_clear_directive(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("Red Ant", world=world, x=10, y=10)
        world.add_creature(ant)
        bridge = SimBridge(world)

        ok = bridge.execute(
            IssueCreatureDirective(
                creature_id=id(ant),
                kind="move_to",
                x=300,
                y=300,
            )
        )
        self.assertTrue(ok.ok)
        self.assertIsNotNone(ant.directive)

        cleared = bridge.execute(ClearCreatureDirective(creature_id=id(ant)))
        self.assertTrue(cleared.ok)
        self.assertIsNone(ant.directive)


if __name__ == "__main__":
    unittest.main()

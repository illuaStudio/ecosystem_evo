"""client_api TargetView（Hunt/Combat ターゲットの Client 向けビュー）。"""
import unittest

from src.game import client_api
from src.game.ai.combat_actions import CombatAction
from src.game.ai.hunt_actions import HuntAction
from src.sim.combat.pickup_target import PickupTarget, PickupTargetKind
from src.sim.components.object_storage import ObjectStorage
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.entities.world_object import WorldObject
from src.sim.systems.world import World


class TestClientApiTargetView(unittest.TestCase):
    def test_hunt_creature_target(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        spider = factory.create("Spider", world=world, x=520, y=500)
        world.add_creature(ant)
        world.add_creature(spider)

        action = HuntAction(target_types=["Spider"])
        action._target = spider
        ant.current_action = action

        view = client_api.get_hunt_target_view(ant)
        self.assertIsNotNone(view)
        assert view is not None
        self.assertEqual(view.kind, "creature")
        self.assertTrue(view.is_creature)
        self.assertEqual(view.species_name, "Spider")
        self.assertIn("Spider", view.name)
        self.assertAlmostEqual(view.x, 520.0)
        self.assertAlmostEqual(view.y, 500.0)
        self.assertGreater(view.size, 0)

    def test_hunt_world_object_field_biomass(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        world.add_creature(ant)

        wo = WorldObject(
            id="pickup_1",
            type_ref="biomass_patch",
            x=530.0,
            y=510.0,
            layer="field",
            storage=ObjectStorage(stored_mass=40.0, max_mass=100.0),
            pickup_radius=14.0,
            label="patch",
        )
        action = HuntAction(target_types=["springtail"])
        action._target = wo
        ant.current_action = action

        view = client_api.get_hunt_target_view(ant)
        self.assertIsNotNone(view)
        assert view is not None
        self.assertEqual(view.kind, "field_biomass")
        self.assertFalse(view.is_creature)
        self.assertIsNone(view.species_name)
        self.assertIn("field", view.name)
        self.assertAlmostEqual(view.x, 530.0)
        self.assertEqual(view.size, 14.0)

    def test_hunt_pickup_target_wrapper(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        world.add_creature(ant)

        wo = WorldObject(
            id="pickup_2",
            type_ref="biomass_patch",
            x=540.0,
            y=520.0,
            layer="field",
            storage=ObjectStorage(stored_mass=25.0, max_mass=50.0),
            pickup_radius=10.0,
        )
        wrapped = PickupTarget(kind=PickupTargetKind.FIELD_OBJECT, world_object=wo)
        action = HuntAction(target_types=["springtail"])
        action._target = wrapped
        ant.current_action = action

        view = client_api.get_hunt_target_view(ant)
        self.assertIsNotNone(view)
        assert view is not None
        self.assertEqual(view.kind, "field_biomass")
        self.assertAlmostEqual(view.x, 540.0)

    def test_combat_creature_target(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        enemy = factory.create("rival_ant", world=world, x=520, y=500)
        world.add_creature(ant)
        world.add_creature(enemy)

        action = CombatAction(hostile_species=["rival_ant"])
        action._target = enemy
        ant.current_action = action

        view = client_api.get_combat_target_view(ant)
        self.assertIsNotNone(view)
        assert view is not None
        self.assertEqual(view.kind, "creature")
        self.assertTrue(view.is_creature)

    def test_no_action_returns_none(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        world.add_creature(ant)
        self.assertIsNone(client_api.get_hunt_target_view(ant))
        self.assertIsNone(client_api.get_combat_target_view(ant))

    def test_aggression_prefers_combat(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=500)
        prey = factory.create("Spider", world=world, x=520, y=500)
        enemy = factory.create("rival_ant", world=world, x=530, y=500)
        world.add_creature(ant)
        world.add_creature(prey)
        world.add_creature(enemy)

        hunt = HuntAction(target_types=["Spider"])
        hunt._target = prey
        ant.current_action = hunt
        self.assertEqual(client_api.get_aggression_target_view(ant).species_name, "Spider")

        combat = CombatAction(hostile_species=["rival_ant"])
        combat._target = enemy
        ant.current_action = combat
        view = client_api.get_aggression_target_view(ant)
        self.assertIsNotNone(view)
        assert view is not None
        self.assertEqual(view.species_name, "rival_ant")


if __name__ == "__main__":
    unittest.main()

"""CombatAction ???????????"""
import unittest

from src.sim.ai.actions import CombatAction
from src.sim.combat.target_query import find_nearest_hostile_creature
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.creature_helpers import try_attack_only
from tests.sim.world_fixtures import affiliation_settings


def _isolated_world() -> World:
    return World.from_json(
        {
            "name": "CombatTest",
            "world_width": 800,
            "world_height": 800,
            "initial_entities": {},
            "population_limits": {"red_ant": 60, "rival_ant": 60},
            "affiliation": affiliation_settings(),
        }
    )


class TestCombatAction(unittest.TestCase):
    def test_find_nearest_hostile(self):
        world = _isolated_world()
        factory = CreatureFactory()
        red = factory.create("red_ant_soldier", world=world, x=100, y=100)
        blue = factory.create("rival_ant", world=world, x=130, y=100)
        world.add_creature(red)
        world.add_creature(blue)

        ref = find_nearest_hostile_creature(red, ("rival_ant",))
        foe = ref.as_creature() if ref else None
        self.assertIs(foe, blue)

    def test_combat_utility_when_rival_in_vision(self):
        world = _isolated_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=105, y=100)
        world.add_creature(soldier)
        other = factory.create("rival_ant", world=world, x=160, y=100)
        world.add_creature(other)

        action = CombatAction(hostile_species=["rival_ant"], territory_only=True)
        self.assertGreater(action.calculate_utility(soldier), 0.0)

    def test_combat_attacks_without_eating(self):
        world = _isolated_world()
        factory = CreatureFactory()
        soldier = factory.create("red_ant_soldier", world=world, x=100, y=100)
        other = factory.create("rival_ant", world=world, x=112, y=100)
        other.hp = 5.0
        world.add_creature(soldier)
        world.add_creature(other)

        sat_before = soldier.satiety
        try_attack_only(soldier, other, attack_power=2.5)
        self.assertFalse(other.alive)
        self.assertEqual(soldier.satiety, sat_before)


if __name__ == "__main__":
    unittest.main()

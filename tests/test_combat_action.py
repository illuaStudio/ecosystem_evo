"""CombatAction と敵対種検索のテスト。"""
import unittest

from src.ai.actions import CombatAction
from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import find_nearest_hostile_among, try_attack_only


def _isolated_world() -> World:
    return World.from_json(
        {
            "name": "CombatTest",
            "world_width": 800,
            "world_height": 800,
            "initial_entities": {},
            "population_limits": {"Ant": 60, "EnemyAnt": 60},
        }
    )


class TestCombatAction(unittest.TestCase):
    def test_find_nearest_hostile(self):
        world = _isolated_world()
        factory = CreatureFactory()
        ant = factory.create("Ant", world=world, x=100, y=100)
        enemy = factory.create("EnemyAnt", world=world, x=130, y=100)
        world.add_creature(ant)
        world.add_creature(enemy)

        foe = find_nearest_hostile_among(ant, ["EnemyAnt"])
        self.assertIs(foe, enemy)

    def test_combat_utility_when_enemy_in_vision(self):
        world = _isolated_world()
        factory = CreatureFactory()
        ant = factory.create("Ant", world=world, x=100, y=100)
        enemy = factory.create("EnemyAnt", world=world, x=140, y=100)
        world.add_creature(ant)
        world.add_creature(enemy)

        action = CombatAction(hostile_species=["EnemyAnt"])
        self.assertGreater(action.calculate_utility(ant), 0.0)

    def test_combat_attacks_without_eating(self):
        world = _isolated_world()
        factory = CreatureFactory()
        ant = factory.create("Ant", world=world, x=100, y=100)
        enemy = factory.create("EnemyAnt", world=world, x=112, y=100)
        enemy.hp = 5.0
        world.add_creature(ant)
        world.add_creature(enemy)

        sat_before = ant.satiety
        try_attack_only(ant, enemy, attack_power=2.5)
        self.assertFalse(enemy.alive)
        self.assertEqual(ant.satiety, sat_before)


if __name__ == "__main__":
    unittest.main()

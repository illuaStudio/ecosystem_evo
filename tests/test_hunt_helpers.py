"""狩りターゲット参照ヘルパーのテスト。"""
import unittest

from src.ai.actions import CombatAction, HuntAction
from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.hunt_helpers import (
    find_attackers_for_target,
    find_hunters_for_prey,
    get_combat_target,
    get_hunt_target,
)


class TestHuntHelpers(unittest.TestCase):
    def test_get_hunt_target_from_action(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("Ant", world=world, x=500, y=500)
        spider = factory.create("Spider", world=world, x=520, y=500)
        world.add_creature(ant)
        world.add_creature(spider)

        action = HuntAction(target_types=["Spider"])
        action._target = spider
        ant.current_action = action

        self.assertIs(get_hunt_target(ant), spider)

    def test_find_hunters_for_prey(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("Ant", world=world, x=500, y=500)
        spider = factory.create("Spider", world=world, x=520, y=500)
        world.add_creature(ant)
        world.add_creature(spider)

        action = HuntAction(target_types=["Spider"])
        action._target = spider
        ant.current_action = action

        hunters = find_hunters_for_prey(world, spider)
        self.assertEqual(len(hunters), 1)
        self.assertIs(hunters[0], ant)

    def test_get_combat_target(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("Ant", world=world, x=500, y=500)
        enemy = factory.create("EnemyAnt", world=world, x=520, y=500)
        world.add_creature(ant)
        world.add_creature(enemy)

        action = CombatAction(hostile_species=["EnemyAnt"])
        action._target = enemy
        ant.current_action = action

        self.assertIs(get_combat_target(ant), enemy)

    def test_find_attackers_includes_combat(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("Ant", world=world, x=500, y=500)
        enemy = factory.create("EnemyAnt", world=world, x=520, y=500)
        world.add_creature(ant)
        world.add_creature(enemy)

        action = CombatAction(hostile_species=["Ant"])
        action._target = enemy
        ant.current_action = action

        attackers = find_attackers_for_target(world, enemy)
        self.assertEqual(len(attackers), 1)
        self.assertIs(attackers[0], ant)


if __name__ == "__main__":
    unittest.main()

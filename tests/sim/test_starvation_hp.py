"""飢餓時 HP ダメージの種別パラメータテスト。"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World


class TestStarvationHpMult(unittest.TestCase):
    def test_global_default_starvation_damage(self):
        world = World()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        queen.satiety = 0.0
        queen.hp = 100.0
        queen.traits["metabolism_rate"] = 0.1

        queen.metabolism._apply_metabolism(1.0)

        self.assertEqual(queen.satiety, 0.0)
        self.assertAlmostEqual(queen.hp, 100.0 - 0.1 * 0.12)

    def test_species_trait_overrides_global(self):
        world = World()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        queen.satiety = 0.0
        queen.hp = 100.0
        queen.traits["metabolism_rate"] = 0.1
        queen.traits["starvation_hp_mult"] = 0.5

        queen.metabolism._apply_metabolism(1.0)

        self.assertAlmostEqual(queen.hp, 100.0 - 0.1 * 0.5)


if __name__ == "__main__":
    unittest.main()

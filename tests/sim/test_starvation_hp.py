"""飢餓時 HP ダメージの種別パラメータテスト。"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World


class TestStarvationHpPerTick(unittest.TestCase):
    def test_starvation_hp_independent_of_metabolism(self):
        world = World()
        factory = CreatureFactory()
        amoeba = factory.create("Amoeba", world=world, x=120, y=120)
        amoeba.satiety = 0.0
        amoeba.hp = 100.0
        amoeba.traits["metabolism_per_tick"] = 0.5
        amoeba.traits["starvation_hp_per_tick"] = 0.02

        amoeba.metabolism._apply_metabolism(1.0)

        self.assertEqual(amoeba.satiety, 0.0)
        self.assertAlmostEqual(amoeba.hp, 99.98)

    def test_species_starvation_damage(self):
        world = World()
        factory = CreatureFactory()
        amoeba = factory.create("Amoeba", world=world, x=120, y=120)
        amoeba.satiety = 0.0
        amoeba.hp = 100.0

        amoeba.metabolism._apply_metabolism(1.0)

        self.assertEqual(amoeba.satiety, 0.0)
        self.assertAlmostEqual(amoeba.hp, 100.0 - amoeba.traits["starvation_hp_per_tick"])

    def test_starvation_scales_with_dt(self):
        world = World()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        queen.satiety = 0.0
        queen.hp = 100.0
        per_tick = float(queen.traits["starvation_hp_per_tick"])

        queen.metabolism._apply_metabolism(10.0)

        self.assertAlmostEqual(queen.hp, 100.0 - per_tick * 10.0)


if __name__ == "__main__":
    unittest.main()

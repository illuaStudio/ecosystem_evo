"""マナ徘徊の退避・密集回避ロジックのユニットテスト。"""
import unittest
from unittest.mock import MagicMock

from src.sim.components.mana_affinity import ManaAffinity
from src.sim.components.position import Position
from src.sim.systems.mana_system import ManaSystem
from src.sim.utils.creature_helpers import count_same_species_near, same_species_repulsion_angle


class TestManaSteering(unittest.TestCase):
    def _params(self) -> dict:
        return {
            "depleted_ratio": 0.12,
            "depletion_rate_threshold": 0.08,
            "no_absorb_escape_ticks": 4,
            "crowd_radius": 40.0,
            "crowd_escape_neighbors": 3,
            "crowd_sample_penalty": 28.0,
        }

    def _entity(self, x=100.0, y=100.0):
        entity = MagicMock()
        entity.alive = True
        entity.position = Position(x, y)
        entity.species.name = "Amoeba"
        entity.mana_no_absorb_ticks = 0
        entity.mana_steer_snap_x = 100.0
        entity.mana_steer_snap_y = 100.0
        entity.mana_steer_snap_density = 1000.0
        entity.max_satiety = 45.0
        entity.satiety = 10.0
        return entity

    def _world(self, density=1500.0, cap=2500.0):
        world = MagicMock()
        world.mana_layer = MagicMock()
        world.mana_layer.mana_density_cap = cap
        world.mana_layer.mana_cell_size = 16
        world.mana_layer.get_mana_density = MagicMock(return_value=density)
        world.mana_layer.mana_density = [[density]]
        world.creatures = []
        return world

    def test_should_escape_on_absolute_depletion(self):
        entity = self._entity()
        cap = 2500.0
        world = self._world(density=cap * 0.05)
        world.mana_layer.get_mana_density = MagicMock(return_value=cap * 0.05)
        self.assertTrue(ManaSystem.should_escape(entity, world, self._params()))

    def test_should_escape_on_depletion_rate(self):
        entity = self._entity()
        world = self._world()
        world.mana_layer.get_mana_density = MagicMock(return_value=900.0)
        entity.mana_steer_snap_density = 1000.0
        self.assertGreaterEqual(ManaSystem.local_depletion_rate(entity, world), 0.1)
        self.assertTrue(ManaSystem.should_escape(entity, world, self._params()))

    def test_should_escape_on_no_absorb_streak(self):
        entity = self._entity()
        entity.mana_no_absorb_ticks = 4
        world = self._world(density=1500.0)
        self.assertTrue(ManaSystem.should_escape(entity, world, self._params()))

    def test_count_same_species_near_excludes_self(self):
        entity = self._entity(0, 0)
        other = MagicMock()
        other.alive = True
        other.species.name = "Amoeba"
        other.pos = [10.0, 0.0]
        other.position = Position(10.0, 0.0)

        world = MagicMock()
        world.creatures = [entity, other]
        entity.world = world

        self.assertEqual(count_same_species_near(entity, 0, 0, 20.0), 1)
        self.assertEqual(count_same_species_near(entity, 0, 0, 5.0), 0)

    def test_repulsion_points_away_from_neighbor(self):
        entity = self._entity(0, 0)
        other = MagicMock()
        other.alive = True
        other.species.name = "Amoeba"
        other.pos = [30.0, 0.0]
        other.position = Position(30.0, 0.0)

        world = MagicMock()
        world.creatures = [entity, other]
        entity.world = world

        angle = same_species_repulsion_angle(entity, 50.0)
        self.assertIsNotNone(angle)
        self.assertAlmostEqual(angle, 180.0, delta=5.0)


if __name__ == "__main__":
    unittest.main()

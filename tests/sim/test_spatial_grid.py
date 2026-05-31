"""Spatial grid proximity queries."""
import unittest

from src.sim.components.position import Position
from src.sim.utils.spatial_grid import SpatialGrid, iter_creatures_in_radius


class _FakeCreature:
    def __init__(self, x: float, y: float, *, alive: bool = True, species: str = "A"):
        self.position = Position(x, y)
        self.alive = alive
        self.species = type("S", (), {"name": species})()


class TestSpatialGrid(unittest.TestCase):
    def test_iter_in_radius_finds_nearby_only(self):
        grid = SpatialGrid(500, 500, cell_size=64)
        a = _FakeCreature(100, 100)
        b = _FakeCreature(110, 100)
        far = _FakeCreature(400, 400)
        grid.rebuild([a, b, far])

        found = list(grid.iter_in_radius(100, 100, 20.0, alive_only=True))
        self.assertEqual(found, [a, b])

    def test_iter_in_radius_respects_alive_filter(self):
        grid = SpatialGrid(500, 500, cell_size=64)
        live = _FakeCreature(50, 50, alive=True)
        dead = _FakeCreature(55, 50, alive=False)
        grid.rebuild([live, dead])

        self.assertEqual(
            list(grid.iter_in_radius(50, 50, 10.0, alive_only=True)),
            [live],
        )
        self.assertEqual(
            list(grid.iter_in_radius(50, 50, 10.0, alive_only=False)),
            [dead],
        )

    def test_fallback_without_grid(self):
        class World:
            creatures = []

        world = World()
        c = _FakeCreature(0, 0)
        world.creatures = [c]

        self.assertEqual(
            list(iter_creatures_in_radius(world, 0, 0, 5.0, alive_only=True)),
            [c],
        )


if __name__ == "__main__":
    unittest.main()

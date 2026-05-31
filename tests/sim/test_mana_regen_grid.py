"""マナ regen multiplier グリッドの一致テスト。"""
import copy
import unittest

from src.sim.systems.world import World


class TestManaRegenGrid(unittest.TestCase):
    def test_regen_multiplier_grid_matches_biome_lookup(self):
        world = World()
        ml = world.mana_layer
        cell = ml.mana_cell_size
        self.assertTrue(ml._regen_multiplier_grid)

        for row in range(ml._mana_rows):
            cy = row * cell + cell * 0.5
            for col in range(ml._mana_cols):
                cx = col * cell + cell * 0.5
                expected = world.biome.get_mana_regen_multiplier(cx, cy)
                self.assertAlmostEqual(
                    ml._regen_multiplier_grid[row][col],
                    expected,
                )

    def test_regenerate_unchanged_with_cached_multipliers(self):
        world = World()
        ml = world.mana_layer
        snapshot = copy.deepcopy(ml.mana_density)
        ml.mana_density[0][0] = 0.0

        ml.regenerate(5.0)
        with_grid = ml.mana_density[0][0]

        ml.mana_density = copy.deepcopy(snapshot)
        ml.mana_density[0][0] = 0.0
        cell = ml.mana_cell_size
        cap = ml.mana_density_cap
        cell_count = ml._mana_cols * ml._mana_rows
        base_per_cell = (ml.regen_rate / cell_count) * 5.0
        row, col = 0, 0
        cx = col * cell + cell * 0.5
        cy = row * cell + cell * 0.5
        mult = world.biome.get_mana_regen_multiplier(cx, cy)
        expected = min(cap, base_per_cell * mult)
        self.assertAlmostEqual(with_grid, expected)


if __name__ == "__main__":
    unittest.main()

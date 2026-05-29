"""個体差（trait_variance）のサンプリングとファクトリー連携。"""
import random
import unittest

from src.entities.creature_factory import CreatureFactory
from src.config import config
from src.entities.species import (
    Species,
    clamp_traits,
    normalize_trait_variance,
    resolve_trait_variance,
    sample_individual_traits,
)
from src.utils.creature_helpers import format_individual_trait_lines
from src.systems.world import World


class TestTraitVariance(unittest.TestCase):
    def test_normalize_trait_variance_requires_bounds_for_uniform(self):
        raw = {
            "base_speed": {"distribution": "uniform", "min": 0.3, "max": 0.7},
            "growth_rate": {"distribution": "uniform"},
            "base_vision": {"distribution": "normal", "std": 5.0, "min": 40, "max": 90},
        }
        result = normalize_trait_variance(raw)
        self.assertIn("base_speed", result)
        self.assertNotIn("growth_rate", result)
        self.assertIn("base_vision", result)

    def test_sample_individual_traits_respects_min_max(self):
        template = {"base_speed": 0.5, "max_hp": 60.0}
        variance = {
            "base_speed": {
                "distribution": "normal",
                "std": 1.0,
                "min": 0.35,
                "max": 0.65,
            },
            "max_hp": {
                "distribution": "uniform",
                "min": 50.0,
                "max": 55.0,
            },
        }
        rng = random.Random(0)
        for _ in range(50):
            traits = sample_individual_traits(template, variance, rng=rng)
            self.assertGreaterEqual(traits["base_speed"], 0.35)
            self.assertLessEqual(traits["base_speed"], 0.65)
            self.assertGreaterEqual(traits["max_hp"], 50.0)
            self.assertLessEqual(traits["max_hp"], 55.0)

    def test_clamp_traits_keeps_max_size_above_base_size(self):
        traits = clamp_traits({"base_size": 8.0, "max_size": 6.0})
        self.assertGreaterEqual(traits["max_size"], traits["base_size"])

    def test_factory_create_applies_amoeba_variance(self):
        world = World()
        rng = random.Random(42)
        speeds = {
            CreatureFactory.create("Amoeba", world=world, x=100, y=100, rng=rng).traits[
                "base_speed"
            ]
            for _ in range(20)
        }
        self.assertGreater(max(speeds) - min(speeds), 0.0)

    def test_offspring_traits_are_independent_of_parent(self):
        world = World()
        parent = CreatureFactory.create("Amoeba", world=world, x=200, y=200, rng=random.Random(1))
        parent.traits["base_speed"] = 0.99

        child = CreatureFactory.create_offspring(
            parent,
            210,
            200,
            base_size=4.0,
            satiety=20.0,
            rng=random.Random(2),
        )
        self.assertNotEqual(child.traits["base_speed"], parent.traits["base_speed"])
        self.assertGreaterEqual(child.traits["base_speed"], 0.35)
        self.assertLessEqual(child.traits["base_speed"], 0.65)
        self.assertEqual(child.traits["base_size"], 4.0)
        self.assertEqual(child.satiety, 20.0)

    def test_all_species_have_default_trait_variance(self):
        for name in config.species:
            species = Species.create(name)
            self.assertGreater(len(species.trait_variance), 0)
            for key in ("base_speed", "base_vision", "max_hp", "max_satiety", "metabolism_rate"):
                self.assertIn(key, species.trait_variance)

    def test_ant_factory_applies_variance(self):
        world = World()
        rng = random.Random(99)
        speeds = [
            CreatureFactory.create("red_ant", world=world, x=300, y=300, rng=rng).traits[
                "base_speed"
            ]
            for _ in range(15)
        ]
        self.assertGreater(max(speeds) - min(speeds), 0.0)

    def test_resolve_trait_variance_json_overrides_default(self):
        traits = {"base_speed": 0.5, "base_vision": 70.0, "max_hp": 60.0, "max_satiety": 45.0, "metabolism_rate": 0.55}
        custom = normalize_trait_variance({
            "base_speed": {"distribution": "normal", "std": 0.05, "min": 0.35, "max": 0.65},
        })
        resolved = resolve_trait_variance(traits, custom)
        self.assertEqual(resolved["base_speed"]["min"], 0.35)
        self.assertIn("base_vision", resolved)

    def test_format_individual_trait_lines_shows_delta(self):
        world = World()
        creature = CreatureFactory.create(
            "Amoeba", world=world, x=100, y=100, rng=random.Random(7)
        )
        lines = format_individual_trait_lines(creature)
        self.assertGreater(len(lines), 0)
        self.assertTrue(any("基本" in line and "Δ" in line for line in lines))
        self.assertTrue(any("基礎速度" in line for line in lines))

    def test_format_individual_trait_lines_for_ant(self):
        world = World()
        ant = CreatureFactory.create("red_ant", world=world, x=300, y=300, rng=random.Random(3))
        lines = format_individual_trait_lines(ant)
        self.assertGreater(len(lines), 0)
        self.assertTrue(any("基礎速度" in line for line in lines))
        self.assertTrue(any("視界" in line for line in lines))

    def test_format_individual_trait_lines_same_order_across_species(self):
        world = World()

        def labels_for(species_name: str, seed: int) -> list[str]:
            c = CreatureFactory.create(
                species_name, world=world, x=100, y=100, rng=random.Random(seed)
            )
            return [line.split(":")[0].strip() for line in format_individual_trait_lines(c)]

        ant_labels = labels_for("red_ant", 1)
        spider_labels = labels_for("Spider", 2)
        self.assertEqual(ant_labels, spider_labels)

        amoeba_labels = labels_for("Amoeba", 3)
        self.assertIn("成長率", amoeba_labels)
        self.assertLess(
            amoeba_labels.index("成長率"),
            amoeba_labels.index("代謝"),
        )
        for key in ("基礎速度", "視界", "代謝", "最大HP", "最大満腹"):
            self.assertIn(key, amoeba_labels)
            self.assertIn(key, ant_labels)


if __name__ == "__main__":
    unittest.main()

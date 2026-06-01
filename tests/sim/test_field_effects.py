"""???????????????????????? ? Phase 1 ???"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.field_modifiers import (
    apply_field_hp_effects,
    resolve_field_hp_delta,
    sample_field_modifiers,
    FieldModifiers,
)
from tests.sim.world_fixtures import affiliation_settings


def _colony_world(**colony_overrides) -> World:
    colony = affiliation_settings(
        territory_effects={
            "hp_regen_per_dt": 0.05,
            "requires_affiliation_match": True,
        },
    )
    colony.update(colony_overrides)
    return World.from_json(
        {
            "name": "FieldEffectTest",
            "world_width": 1000,
            "world_height": 1000,
            "initial_entities": {},
            "population_limits": {"red_ant": 20, "rival_ant": 20, "springtail": 50},
            "affiliation": colony,
        }
    )


def _toxic_biome_world(drain: float = 0.1) -> World:
    return World.from_json(
        {
            "name": "ToxicBiomeTest",
            "world_width": 1000,
            "world_height": 1000,
            "initial_entities": {},
            "population_limits": {"springtail": 50},
            "world": {
                "biome_map_cell_size": 64,
                "biomes": [
                    {
                        "name": "rich",
                        "color": "#2E8B57",
                        "spawn_rate_multiplier": 1.2,
                    },
                    {
                        "name": "poor",
                        "color": "#8F9E6E",
                        "hp_drain_per_dt": drain,
                        "spawn_rate_multiplier": 0.25,
                    },
                ],
                "biome_noise": {
                    "scale": 0.003,
                    "octaves": 4,
                    "persistence": 0.55,
                    "lacunarity": 2.2,
                    "threshold": 0.5,
                    "seed": 42,
                },
            },
        }
    )


class TestFieldEffects(unittest.TestCase):
    def _world_with_fixed_nests(self) -> World:
        world = _colony_world()
        world.nest_system.create_nest(200, 200, "red_ant", affiliation_id="red_ant")
        world.nest_system.create_nest(800, 800, "rival_ant", affiliation_id="rival_ant")
        return world

    def test_territory_regen_only_for_own_colony(self):
        world = self._world_with_fixed_nests()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=200, y=200)
        world.add_creature(red)
        red.hp = 80.0

        # ??????????????????????
        blue = factory.create("rival_ant", world=world, x=210, y=210)
        world.add_creature(blue)
        blue.hp = 80.0

        apply_field_hp_effects(red, dt=10.0)
        apply_field_hp_effects(blue, dt=10.0)

        self.assertGreater(red.hp, 80.0)
        self.assertEqual(blue.hp, 80.0)

    def test_territory_regen_not_outside_territory(self):
        world = self._world_with_fixed_nests()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=900, y=900)
        world.add_creature(red)
        red.hp = 80.0

        apply_field_hp_effects(red, dt=10.0)
        self.assertEqual(red.hp, 80.0)

    def test_biome_hp_drain(self):
        world = _toxic_biome_world(drain=0.08)
        factory = CreatureFactory()
        amoeba = factory.create("springtail", world=world, x=900, y=900)
        world.add_creature(amoeba)
        amoeba.hp = 60.0

        modifiers = sample_field_modifiers(world, amoeba)
        self.assertGreater(modifiers.hp_drain_per_dt, 0.0)

        apply_field_hp_effects(amoeba, dt=5.0)
        self.assertLess(amoeba.hp, 60.0)

    def test_poison_resist_reduces_drain(self):
        world = _toxic_biome_world(drain=0.1)
        factory = CreatureFactory()
        amoeba = factory.create("springtail", world=world, x=900, y=900)
        world.add_creature(amoeba)
        amoeba.traits["poison_resist"] = 0.5

        modifiers = sample_field_modifiers(world, amoeba)
        resisted = resolve_field_hp_delta(amoeba, modifiers, dt=1.0)
        amoeba.traits["poison_resist"] = 0.0
        no_resist = resolve_field_hp_delta(amoeba, modifiers, dt=1.0)

        self.assertGreater(resisted, no_resist)
        self.assertAlmostEqual(resisted, no_resist * 0.5)

    def test_hp_regen_capped_at_max_hp(self):
        world = self._world_with_fixed_nests()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=200, y=200)
        world.add_creature(red)
        red.hp = red.max_hp - 0.001

        apply_field_hp_effects(red, dt=100.0)
        self.assertEqual(red.hp, red.max_hp)

    def test_metabolism_applies_field_effects(self):
        world = self._world_with_fixed_nests()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=200, y=200)
        world.add_creature(red)
        red.hp = 70.0

        died = red.metabolism.update(dt=20.0)
        self.assertFalse(died)
        self.assertGreater(red.hp, 70.0)

    def test_field_drain_can_kill_via_metabolism(self):
        world = _toxic_biome_world(drain=5.0)
        factory = CreatureFactory()
        amoeba = factory.create("springtail", world=world, x=900, y=900)
        world.add_creature(amoeba)
        amoeba.hp = 3.0

        died = amoeba.metabolism.update(dt=1.0)
        self.assertTrue(died)
        self.assertLessEqual(amoeba.hp, 0.0)

    def test_empty_modifiers_no_op(self):
        mod = FieldModifiers()
        self.assertEqual(resolve_field_hp_delta(type("_C", (), {"traits": {}})(), mod, 1.0), 0.0)


from src.sim.systems.world import World
from tests.sim.world_fixtures import affiliation_settings


def _fog_world(drain: float = 0.1, radius: float = 120.0) -> World:
    return World.from_json(
        {
            "name": "PoisonFogTest",
            "world_width": 1000,
            "world_height": 1000,
            "initial_entities": {},
            "population_limits": {"red_ant": 20, "springtail": 50, "Spider": 10},
            "affiliation": affiliation_settings(),
            "field_emitters": {
                "sources": [
                    {
                        "type": "poison_fog",
                        "x": 400,
                        "y": 400,
                        "radius": radius,
                        "hp_drain_per_dt": drain,
                        "tags": ["poison"],
                    }
                ]
            },
        }
    )


class TestPoisonFogEmitters(unittest.TestCase):
    def test_ant_drains_hp_inside_fog(self):
        world = _fog_world()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=400, y=400)
        world.add_creature(ant)
        ant.hp = 100.0

        apply_field_hp_effects(ant, dt=10.0)
        self.assertLess(ant.hp, 100.0)

    def test_amoeba_immune_to_poison_fog(self):
        world = _fog_world()
        factory = CreatureFactory()
        amoeba = factory.create("springtail", world=world, x=400, y=400)
        world.add_creature(amoeba)
        amoeba.hp = 50.0

        apply_field_hp_effects(amoeba, dt=20.0)
        self.assertEqual(amoeba.hp, 50.0)

    def test_spider_drains_hp_inside_fog(self):
        world = _fog_world()
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=400, y=400)
        world.add_creature(spider)
        spider.hp = 80.0

        apply_field_hp_effects(spider, dt=10.0)
        self.assertLess(spider.hp, 80.0)

    def test_outside_fog_radius_no_drain(self):
        world = _fog_world(radius=80.0)
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=400, y=520)
        world.add_creature(ant)
        ant.hp = 100.0

        apply_field_hp_effects(ant, dt=10.0)
        self.assertEqual(ant.hp, 100.0)

    def test_zones_loaded_on_world(self):
        world = _fog_world()
        poison = [z for z in world.zone_system.zones if z.zone_type == "poison_fog"]
        self.assertEqual(len(poison), 1)
        zone = poison[0]
        self.assertAlmostEqual(zone.x, 400.0)

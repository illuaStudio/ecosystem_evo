from src.game.colony_session import get_colony_orchestrator, try_get_colony_orchestrator

def colony(world):
    return get_colony_orchestrator(world)

"""FieldEffectCache のセル参照とフォールバック一致。"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.utils.field_modifiers import sample_field_modifiers
from tests.sim.test_field_effects import _colony_world, _fog_world, _toxic_biome_world


class TestFieldEffectCache(unittest.TestCase):
    def test_cache_matches_uncached_sample(self):
        world = _toxic_biome_world(drain=0.08)
        factory = CreatureFactory()
        creature = factory.create("springtail", world=world, x=900, y=900)
        world.add_creature(creature)

        cached = sample_field_modifiers(world, creature)
        cache = world.field_effect_cache
        world.field_effect_cache = None  # type: ignore[assignment]
        uncached = sample_field_modifiers(world, creature)
        world.field_effect_cache = cache
        self.assertEqual(cached.hp_regen_per_dt, uncached.hp_regen_per_dt)
        self.assertEqual(cached.hp_drain_per_dt, uncached.hp_drain_per_dt)

    def test_territory_rebuilt_after_create_nest(self):
        world = _colony_world()
        factory = CreatureFactory()
        colony(world).create_affiliation_site(200, 200, "red_ant", affiliation_id="red_ant")
        red = factory.create("red_ant", world=world, x=200, y=200)
        world.add_creature(red)

        mods = sample_field_modifiers(world, red)
        self.assertGreater(mods.hp_regen_per_dt, 0.0)

    def test_poison_immunity_via_cache(self):
        world = _fog_world()
        factory = CreatureFactory()
        amoeba = factory.create("springtail", world=world, x=400, y=400)
        world.add_creature(amoeba)

        mods = sample_field_modifiers(world, amoeba)
        self.assertEqual(mods.hp_drain_per_dt, 0.0)


if __name__ == "__main__":
    unittest.main()

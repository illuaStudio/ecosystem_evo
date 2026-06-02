"""Spawn emitter enable/disable and burst via SimBridge."""
from __future__ import annotations

import unittest

from src.game.command_builder import place_spawn_emitter, set_spawn_emitter_enabled
from src.sim.bridge import SimBridge
from tests.sim.world_fixtures import load_test_world


class TestSpawnEmitterControl(unittest.TestCase):
    def test_on_enable_burst_and_budget(self):
        world = load_test_world(name="EmitterCtrl", world_width=800, world_height=600)
        bridge = SimBridge(world)
        ok = place_spawn_emitter(
            bridge,
            "test_emitter",
            400.0,
            300.0,
            {
                "mode": "point",
                "species_pool": ["invader_ant"],
                "target_population": 5,
                "initial_burst_count": 5,
                "lifetime_budget": 10,
                "replenish_batch_size": 2,
                "replenish_cooldown_ticks": 0,
                "spawn_rate_per_dt": 0.0,
                "start_trigger": "on_enable",
                "enabled_at_load": False,
                "spawn_at_center": True,
                "use_biome_weight": False,
                "radius": 20.0,
                "creature_spawn_source": "game",
            },
        )
        self.assertTrue(ok)
        self.assertFalse(world.spawn_system.is_emitter_enabled("test_emitter"))

        burst = set_spawn_emitter_enabled(bridge, "test_emitter", True)
        self.assertEqual(burst, 5)
        self.assertTrue(world.spawn_system.is_emitter_enabled("test_emitter"))
        tracked = world.spawn_system.tracked_creature_ids("test_emitter")
        self.assertEqual(len(tracked), 5)

        set_spawn_emitter_enabled(bridge, "test_emitter", False)
        self.assertFalse(world.spawn_system.is_emitter_enabled("test_emitter"))


if __name__ == "__main__":
    unittest.main()

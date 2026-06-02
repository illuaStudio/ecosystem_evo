"""WaveDirector: initial burst + replenish-on-loss spawning."""
from __future__ import annotations

import unittest

from src.game.wave_director import WaveDirector, WaveNestDef, WaveNestHoleDef, WaveNestSpawnDef, WaveDef
from src.sim.bridge import SimBridge
from tests.sim.world_fixtures import load_test_world


class TestWaveSpawnBurst(unittest.TestCase):
    def test_initial_burst_spawns_many_at_once(self):
        world = load_test_world(name="BurstTest", world_width=1200, world_height=800)
        bridge = SimBridge(world)
        wd = WaveDirector(
            waves=(
                WaveDef(
                    id="t",
                    label="test",
                    story_on_clear="",
                    nests=(
                        WaveNestDef(
                            holes=(WaveNestHoleDef(840.0, 170.0),),
                            max_alive=12,
                            initial_burst_size=12,
                            spawn_burst_size=4,
                            spawn_interval_ticks=50,
                            spawns=(WaveNestSpawnDef("invader_ant", 40),),
                        ),
                    ),
                ),
            ),
            player_affiliation_id="red_ant",
        )
        wd.begin_wave(0)
        wd.tick(world, bridge)
        self.assertGreaterEqual(wd.enemies_alive(world), 10)
        self.assertLessEqual(wd.enemies_alive(world), 12)

    def test_replenish_only_fills_deficit(self):
        world = load_test_world(name="Replenish", world_width=1200, world_height=800)
        bridge = SimBridge(world)
        wd = WaveDirector(
            waves=(
                WaveDef(
                    id="t",
                    label="",
                    story_on_clear="",
                    nests=(
                        WaveNestDef(
                            holes=(WaveNestHoleDef(840.0, 170.0),),
                            max_alive=8,
                            initial_burst_size=8,
                            spawn_burst_size=8,
                            spawn_interval_ticks=0,
                            spawns=(WaveNestSpawnDef("invader_ant", 30),),
                        ),
                    ),
                ),
            ),
        )
        wd.begin_wave(0)
        wd.tick(world, bridge)
        alive_after_burst = wd.enemies_alive(world)
        self.assertEqual(alive_after_burst, 8)

        killed = 0
        for creature in list(world.creatures):
            if id(creature) in wd._spawned_ids and killed < 3:
                creature.hp = 0.0
                creature.become_corpse(cause="hp")
                killed += 1
        world.spawn_system.update(1.0)
        wd.tick(world, bridge)
        self.assertEqual(wd.enemies_alive(world), 8)


if __name__ == "__main__":
    unittest.main()

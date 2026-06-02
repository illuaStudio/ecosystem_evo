"""WaveDirector: initial burst + replenish-on-loss spawning."""
from __future__ import annotations

import unittest

from src.game.wave_director import WaveDef, WaveDirector, WaveHoleDef, WaveNestDef
from src.sim.bridge import SimBridge
from tests.sim.world_fixtures import load_test_world


def _single_hole(**overrides) -> WaveHoleDef:
    base = dict(
        x=840.0,
        y=170.0,
        max_alive=12,
        initial_burst_size=12,
        spawn_burst_size=4,
        spawn_interval_ticks=50,
        spawn_radius=0.0,
        species="invader_ant",
        budget=40,
    )
    base.update(overrides)
    return WaveHoleDef(**base)


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
                    nests=(WaveNestDef(holes=(_single_hole(),)),),
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
                            holes=(
                                _single_hole(
                                    max_alive=8,
                                    initial_burst_size=8,
                                    spawn_burst_size=8,
                                    spawn_interval_ticks=0,
                                    species="invader_ant",
                                    budget=30,
                                ),
                            ),
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

    def test_spawn_radius_spreads_positions(self):
        world = load_test_world(name="Spread", world_width=1200, world_height=800)
        bridge = SimBridge(world)
        wd = WaveDirector(
            waves=(
                WaveDef(
                    id="t",
                    label="",
                    story_on_clear="",
                    nests=(
                        WaveNestDef(
                            holes=(
                                _single_hole(
                                    max_alive=6,
                                    initial_burst_size=6,
                                    spawn_radius=80.0,
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )
        wd.begin_wave(0)
        wd.tick(world, bridge)
        positions = [
            (c.position.x, c.position.y)
            for c in world.creatures
            if id(c) in wd._spawned_ids
        ]
        self.assertGreaterEqual(len(positions), 4)
        xs = {round(p[0], 1) for p in positions}
        self.assertGreater(len(xs), 1, "expected spread within spawn_radius")


if __name__ == "__main__":
    unittest.main()

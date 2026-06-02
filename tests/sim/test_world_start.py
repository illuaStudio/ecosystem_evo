from src.game.colony_session import get_colony_orchestrator, try_get_colony_orchestrator

def colony(world):
    return get_colony_orchestrator(world)

"""スタートワールド（1勢力・女王+働きアリ+極小虫）のスモークテスト。"""
import unittest

from src.config import config
from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES
from src.sim.systems.world import World


class TestWorldStart(unittest.TestCase):
    def test_world_spawns_single_affiliation(self):
        world = World()
        nests = list(colony(world).affiliation_roots.values())
        colony_ids = {n.affiliation_id for n in nests}
        self.assertEqual(colony_ids, {"red_ant"})
        self.assertEqual(len(nests), 1)

    def test_affiliation_species_single_faction(self):
        world = World()
        self.assertIn("red_ant", world.affiliation_species)
        self.assertNotIn("rival_ant", world.affiliation_species)
        self.assertIn("red_ant", world.affiliation_styles)

    def test_initial_population(self):
        world = World()
        queens = sum(1 for c in world.creatures if c.species.name == "red_ant_queen")
        workers = sum(1 for c in world.creatures if c.species.name == "red_ant")
        micro_fauna = sum(
            1 for c in world.creatures if c.species.name in DEFAULT_MICRO_FAUNA_SPECIES
        )
        self.assertEqual(queens, 1)
        self.assertEqual(workers, 2)
        # Micro-fauna spawn tuning is expected to change; assert config-consistent values.
        cfg = config.get_world("Grassland") or {}
        initial_spawns = cfg.get("initial_spawns") or {}
        groups = initial_spawns.get("groups") or []
        expected_micro = 0
        for g in groups:
            for e in (g.get("entries") or []):
                sp = e.get("species")
                if sp in DEFAULT_MICRO_FAUNA_SPECIES:
                    expected_micro += int(e.get("count") or 0)
        self.assertEqual(micro_fauna, expected_micro)
        self.assertEqual(len(world.creatures), queens + workers + micro_fauna)

    def test_species_still_in_config(self):
        self.assertIn("red_ant", config.species)
        self.assertIn("invader_ant", config.species)
        for name in DEFAULT_MICRO_FAUNA_SPECIES:
            self.assertIn(name, config.species)

    def test_spawn_system_configured(self):
        world = World()
        self.assertIsNotNone(world.spawn_system.ambient)
        self.assertEqual(
            tuple(world.spawn_system.species_pool),
            DEFAULT_MICRO_FAUNA_SPECIES,
        )
        self.assertGreater(len(world.spawn_system.emitters), 0)


if __name__ == "__main__":
    unittest.main()

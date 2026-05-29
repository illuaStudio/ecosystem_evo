"""兵隊蟻・テリトリー・逃走のテスト。"""
import unittest

from src.ai.actions import CombatAction, FleeAction, HuntAction
from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import (
    find_nearest_flee_threat_among,
    is_in_creature_territory,
)


def _colony_world() -> World:
    return World.from_json(
        {
            "name": "TerritoryTest",
            "world_width": 1000,
            "world_height": 1000,
            "initial_entities": {},
            "population_limits": {
                "Ant": 20,
                "AntSoldier": 10,
                "EnemyAnt": 20,
                "EnemyAntSoldier": 10,
                "Spider": 10,
            },
        }
    )


class TestTerritoryAndCastes(unittest.TestCase):
    def test_soldier_joins_worker_nest(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("AntSoldier", world=world, x=110, y=100)
        world.add_creature(soldier)

        worker_nest = world.nest_system.get_creature_nest(worker)
        soldier_nest = world.nest_system.get_creature_nest(soldier)
        self.assertIsNotNone(worker_nest)
        self.assertIs(soldier_nest, worker_nest)

    def test_territory_radius_default(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=200, y=200)
        world.add_creature(worker)
        nest = world.nest_system.get_creature_nest(worker)

        self.assertTrue(is_in_creature_territory(worker, worker))
        near = factory.create("EnemyAnt", world=world, x=250, y=200)
        world.add_creature(near)
        self.assertTrue(is_in_creature_territory(worker, near))

        far = factory.create("EnemyAnt", world=world, x=500, y=500)
        world.add_creature(far)
        self.assertFalse(is_in_creature_territory(worker, far))

    def test_combat_territory_only(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("AntSoldier", world=world, x=105, y=100)
        world.add_creature(soldier)

        inside = factory.create("EnemyAnt", world=world, x=160, y=100)
        world.add_creature(inside)
        outside = factory.create("EnemyAnt", world=world, x=400, y=400)
        world.add_creature(outside)

        action = CombatAction(
            hostile_species=["EnemyAnt"],
            territory_only=True,
        )
        self.assertGreater(action.calculate_utility(soldier), 0.0)

        inside_dist = action._find_hostile(soldier, ("EnemyAnt",))
        self.assertIs(inside_dist, inside)

    def test_worker_flees_from_soldier_and_spider(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=300, y=300)
        world.add_creature(worker)

        soldier = factory.create("EnemyAntSoldier", world=world, x=320, y=300)
        world.add_creature(soldier)

        threat = find_nearest_flee_threat_among(
            worker, ["EnemyAntSoldier", "Spider"]
        )
        self.assertIs(threat, soldier)

        flee = FleeAction(threat_species=["EnemyAntSoldier", "Spider"])
        self.assertGreater(flee.calculate_utility(worker), 0.0)

        from src.ai.actions import HuntAction

        hunt = HuntAction(target_types=["Amoeba"])
        self.assertEqual(hunt.calculate_utility(worker), 0.0)

    def test_flee_latch_blocks_hunt_after_threat_leaves_vision(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=200, y=200)
        world.add_creature(worker)
        amoeba = factory.create("Amoeba", world=world, x=240, y=200)
        world.add_creature(amoeba)

        soldier = factory.create("EnemyAntSoldier", world=world, x=215, y=200)
        world.add_creature(soldier)

        from src.utils.creature_helpers import refresh_flee_latch_from_species

        refresh_flee_latch_from_species(worker)
        self.assertTrue(worker.flee_latch)

        soldier.position.x = 900
        soldier.position.y = 900
        from src.utils.position_helpers import sync_legacy_pos

        sync_legacy_pos(soldier)

        refresh_flee_latch_from_species(worker)
        self.assertFalse(worker.flee_latch)

    def test_worker_hunt_amoeba_only(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=100, y=100)
        world.add_creature(worker)
        amoeba = factory.create("Amoeba", world=world, x=150, y=100)
        world.add_creature(amoeba)

        hunt = HuntAction(target_types=["Amoeba"])
        self.assertGreater(hunt.calculate_utility(worker), 0.0)

        hunt_defs = [
            a
            for a in worker.species.mind_data.get("actions", [])
            if a.get("name") == "HuntAction"
        ]
        self.assertEqual(hunt_defs[0]["params"]["target_types"], ["Amoeba"])
        combat_defs = [
            a
            for a in worker.species.mind_data.get("actions", [])
            if a.get("name") == "CombatAction"
        ]
        self.assertEqual(combat_defs, [])

    def test_soldier_hungry_prefers_nest_feed_over_wander(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("AntSoldier", world=world, x=400, y=400)
        world.add_creature(soldier)

        soldier.satiety = soldier.max_satiety * 0.05
        soldier.nutrition_recovery = True

        from src.ai.actions import FeedAtNestAction, WanderAction

        feed = FeedAtNestAction(approach_when_hungry=True)
        wander = WanderAction()
        self.assertGreater(feed.calculate_utility(soldier), 0.0)
        self.assertEqual(wander.calculate_utility(soldier), 0.0)

        from src.ai.actions import CombatAction, HuntAction

        combat = CombatAction(hostile_species=["EnemyAnt"], territory_only=True)
        hunt = HuntAction(target_types=["Spider"], territory_only=True)
        self.assertEqual(combat.calculate_utility(soldier), 0.0)
        self.assertEqual(hunt.calculate_utility(soldier), 0.0)

    def test_soldier_hunts_spider_in_territory_only(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("AntSoldier", world=world, x=105, y=100)
        world.add_creature(soldier)

        inside = factory.create("Spider", world=world, x=170, y=100)
        world.add_creature(inside)
        outside = factory.create("Spider", world=world, x=600, y=600)
        world.add_creature(outside)

        hunt = HuntAction(
            target_types=["Spider"],
            pickup_on_kill=False,
            territory_only=True,
        )
        prey = hunt._find_prey(soldier, ("Spider",))
        self.assertIs(prey, inside)


if __name__ == "__main__":
    unittest.main()

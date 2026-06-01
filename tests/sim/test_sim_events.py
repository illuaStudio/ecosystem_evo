from src.game.colony_session import get_colony_orchestrator, try_get_colony_orchestrator

def colony(world):
    return get_colony_orchestrator(world)

"""??????????????????????"""
import unittest

from src.game.ai.reproduction_actions import AffiliationReproduceAction
from src.sim.entities.creature_factory import CreatureFactory
from src.game.mind_policy import MindPolicy
from src.sim.events import (
    AffiliationDefeatedEvent,
    CombatStartedEvent,
    DeathEvent,
    ItemFoundEvent,
    SpawnEvent,
)
from src.sim.systems.world import World
from src.sim.utils.creature_helpers import try_attack_only
from src.sim.utils.loot_helpers import try_pickup_loot
from tests.sim.field_drop_helpers import loot_after_death
from tests.sim.world_fixtures import affiliation_settings


class TestSimEvents(unittest.TestCase):
    def _empty_world(self) -> World:
        return World.from_json(
            {
                "name": "EventTest",
                "world_width": 800,
                "world_height": 800,
                "initial_entities": {},
                "population_limits": {
                    "springtail": 20,
                    "red_ant": 20,
                    "red_ant_queen": 3,
                },
                "affiliation": affiliation_settings(),
            }
        )

    def test_spawn_event_on_add_creature(self):
        world = self._empty_world()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(ant, spawn_source="initial")

        events = world.events.drain()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], SpawnEvent)
        self.assertEqual(events[0].species_name, "red_ant")
        self.assertEqual(events[0].source, "initial")

    def test_death_event_on_become_corpse(self):
        world = self._empty_world()
        factory = CreatureFactory()
        prey = factory.create("springtail", world=world, x=100, y=100)
        world.add_creature(prey, spawn_source="initial")
        world.events.drain()

        prey.become_corpse(cause="hp")
        events = world.events.drain()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], DeathEvent)
        self.assertEqual(events[0].cause, "hp")
        self.assertIs(events[0].creature, prey)

    def test_item_found_event_on_pickup(self):
        world = self._empty_world()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        prey = factory.create("springtail", world=world, x=105, y=100)
        world.add_creature(ant, spawn_source="initial")
        world.add_creature(prey, spawn_source="initial")
        world.events.drain()

        prey.become_corpse(cause="hp")
        world.events.drain()
        loot = loot_after_death(world, prey)
        self.assertIsNotNone(loot)
        self.assertTrue(try_pickup_loot(ant, loot))

        events = world.events.drain()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], ItemFoundEvent)
        self.assertGreater(events[0].amount, 0)

    def test_combat_started_event_on_attack(self):
        world = self._empty_world()
        factory = CreatureFactory()
        attacker = factory.create("red_ant_soldier", world=world, x=100, y=100)
        prey = factory.create("springtail", world=world, x=110, y=100)
        world.add_creature(attacker, spawn_source="initial")
        world.add_creature(prey, spawn_source="initial")
        world.events.drain()

        try_attack_only(attacker, prey, attack_power=1.0)
        events = world.events.drain()
        combat = [e for e in events if isinstance(e, CombatStartedEvent)]
        self.assertEqual(len(combat), 1)
        self.assertIs(combat[0].target_creature, prey)

        try_attack_only(attacker, prey, attack_power=1.0)
        events = world.events.drain()
        self.assertEqual(events, [])

    def test_reproduction_emits_spawn_with_parent(self):
        world = self._empty_world()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen, spawn_source="initial")
        nest = colony(world).get_creature_affiliation_root(queen)
        world.events.drain()

        profile = MindPolicy().get_profile("workers_only") or {}
        params = next(
            a["params"]
            for a in profile["actions"]
            if a["name"] == "AffiliationReproduceAction"
        )
        from src.sim.utils.affiliation_config_helpers import get_min_storage_reserve

        nest.stored_mass = get_min_storage_reserve(world) + float(params["food_cost"]) + 10

        action = AffiliationReproduceAction(**{**params, "spawn_cooldown": 0})
        self.assertTrue(action.execute(queen))

        events = world.events.drain()
        spawn_events = [e for e in events if isinstance(e, SpawnEvent)]
        self.assertEqual(len(spawn_events), 1)
        self.assertEqual(spawn_events[0].source, "reproduction")
        self.assertIs(spawn_events[0].parent, queen)
        self.assertEqual(spawn_events[0].species_name, "red_ant")

    def test_colony_defeated_event(self):
        world = self._empty_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=120, y=120)
        world.add_creature(worker, spawn_source="initial")
        nest = colony(world).get_affiliation_root("red_ant")
        world.events.drain()

        world.affiliation_species = {"red_ant": ["red_ant"], "rival_ant": ["rival_ant"]}
        ws = world.world_object_system
        for access in list(ws.iter_access_points("red_ant")):
            access.hp = 0.8
            colony(world).damage_access(
                access, "red_ant", 5.0, attacker_affiliation_id="rival_ant"
            )

        events = world.events.drain()
        defeated = [e for e in events if isinstance(e, AffiliationDefeatedEvent)]
        self.assertEqual(len(defeated), 1)
        self.assertEqual(defeated[0].affiliation_id, "red_ant")

    def test_event_bus_subscribe(self):
        world = self._empty_world()
        received = []
        world.events.subscribe(received.append)
        factory = CreatureFactory()
        ant = factory.create("springtail", world=world, x=50, y=50)
        world.add_creature(ant, spawn_source="initial")
        self.assertEqual(len(received), 1)
        self.assertIsInstance(received[0], SpawnEvent)


if __name__ == "__main__":
    unittest.main()

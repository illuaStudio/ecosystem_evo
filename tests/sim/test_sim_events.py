"""シミュレーション層ドメインイベントのテスト。"""
import unittest

from src.sim.ai.actions import ColonyReproduceAction, SplitAction
from src.sim.entities.creature_factory import CreatureFactory
from src.game.mind_policy import MindPolicy
from src.sim.events import (
    ColonyDefeatedEvent,
    CombatStartedEvent,
    DeathEvent,
    ItemFoundEvent,
    SpawnEvent,
)
from src.sim.systems.world import World
from src.sim.utils.creature_helpers import try_attack_only, try_pickup_carcass


class TestSimEvents(unittest.TestCase):
    def _empty_world(self) -> World:
        return World.from_json(
            {
                "name": "EventTest",
                "world_width": 800,
                "world_height": 800,
                "initial_entities": {},
                "population_limits": {
                    "Amoeba": 20,
                    "red_ant": 20,
                    "red_ant_queen": 3,
                },
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
        prey = factory.create("Amoeba", world=world, x=100, y=100)
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
        prey = factory.create("Amoeba", world=world, x=105, y=100)
        world.add_creature(ant, spawn_source="initial")
        world.add_creature(prey, spawn_source="initial")
        world.events.drain()

        prey.become_corpse(cause="hp")
        world.events.drain()
        self.assertTrue(try_pickup_carcass(ant, prey))

        events = world.events.drain()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], ItemFoundEvent)
        self.assertGreater(events[0].amount, 0)

    def test_combat_started_event_on_attack(self):
        world = self._empty_world()
        factory = CreatureFactory()
        attacker = factory.create("red_ant_soldier", world=world, x=100, y=100)
        prey = factory.create("Amoeba", world=world, x=110, y=100)
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
        nest = world.nest_system.get_creature_nest(queen)
        world.events.drain()

        profile = MindPolicy().get_profile("workers_only") or {}
        params = next(
            a["params"]
            for a in profile["actions"]
            if a["name"] == "ColonyReproduceAction"
        )
        nest.stored_food = float(params["min_food_reserve"]) + float(params["food_cost"]) + 10

        action = ColonyReproduceAction(**{**params, "spawn_cooldown": 0})
        self.assertTrue(action.execute(queen))

        events = world.events.drain()
        spawn_events = [e for e in events if isinstance(e, SpawnEvent)]
        self.assertEqual(len(spawn_events), 1)
        self.assertEqual(spawn_events[0].source, "reproduction")
        self.assertIs(spawn_events[0].parent, queen)
        self.assertEqual(spawn_events[0].species_name, "red_ant")

    def test_split_emits_spawn_event(self):
        world = self._empty_world()
        factory = CreatureFactory()
        parent = factory.create("Amoeba", world=world, x=200, y=200)
        world.add_creature(parent, spawn_source="initial")
        world.events.drain()

        parent.traits["base_size"] = 16.0
        parent.satiety = parent.max_satiety
        parent.age = int(parent.life_cycle.get("mature", 0))
        parent.repro_cooldown = 0

        action = SplitAction()
        self.assertTrue(action.execute(parent))

        events = world.events.drain()
        spawn_events = [e for e in events if isinstance(e, SpawnEvent)]
        self.assertEqual(len(spawn_events), 1)
        self.assertEqual(spawn_events[0].source, "split")
        self.assertIs(spawn_events[0].parent, parent)

    def test_colony_defeated_event(self):
        world = self._empty_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=120, y=120)
        world.add_creature(worker, spawn_source="initial")
        nest = world.nest_system.get_colony_nest("red_ant")
        world.events.drain()

        for hole in list(nest.holes):
            hole.hp = 0
            world.nest_system._remove_hole(nest, hole)

        events = world.events.drain()
        defeated = [e for e in events if isinstance(e, ColonyDefeatedEvent)]
        self.assertEqual(len(defeated), 1)
        self.assertEqual(defeated[0].colony_id, "red_ant")

    def test_event_bus_subscribe(self):
        world = self._empty_world()
        received = []
        world.events.subscribe(received.append)
        factory = CreatureFactory()
        ant = factory.create("Amoeba", world=world, x=50, y=50)
        world.add_creature(ant, spawn_source="initial")
        self.assertEqual(len(received), 1)
        self.assertIsInstance(received[0], SpawnEvent)


if __name__ == "__main__":
    unittest.main()

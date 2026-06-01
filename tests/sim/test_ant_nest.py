"""???????????????????????????????????????????????????????????"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.components.inventory import BiomassItem
from src.sim.utils.inventory_helpers import inventory_is_loaded, total_biomass_amount
from src.sim.utils.creature_helpers import (
    get_haul_max_carry,
    has_edible_carcass,
    hunger_ratio,
    try_attack_only,
    try_pickup_carcass,
)
from tests.sim.legacy_corpse_helpers import use_legacy_corpse_on_death
from src.config import config
from src.sim.utils.creature_helpers import distance_to_point
from src.sim.utils.position_helpers import entity_xy
from src.sim.utils.affiliation_config_helpers import get_affiliation_profile as get_affiliation_profile, get_min_food_reserve
from tests.sim.world_fixtures import (
    RED_ANT_PROFILE,
    affiliation_settings,
    load_test_world,
    set_affiliation_stored_food,
)


def _repro_food_cost(params: dict) -> float:
    return float(params["food_cost"])


def _repro_member_species(params: dict) -> list[str]:
    return [str(s) for s in params["member_species"]]


class TestAntNest(unittest.TestCase):
    def _empty_world(self) -> World:
        """????????????????rival_ant ???????????????????"""
        return load_test_world(
            name="AntNestTest",
            world_width=3000,
            world_height=3000,
            population_limits={"red_ant": 60, "rival_ant": 60},
            affiliation=affiliation_settings(
                profiles={"red_ant": dict(RED_ANT_PROFILE)},
                affiliation_species={"red_ant": ["red_ant"]},
            ),
        )

    def _spawn_predators(self, world, count: int = 3):
        factory = CreatureFactory()
        preds = []
        for i in range(count):
            x = 400 + i * 25
            y = 400 + i * 15
            p = factory.create("red_ant", world=world, x=x, y=y)
            world.add_creature(p)
            preds.append(p)
        return preds

    def test_predators_share_single_nest_even_when_far_apart(self):
        world = self._empty_world()
        factory = CreatureFactory()
        preds = []
        for i, (x, y) in enumerate([(120, 120), (850, 850), (500, 200)]):
            p = factory.create("red_ant", world=world, x=x, y=y)
            world.add_creature(p)
            preds.append(p)
        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        affiliation_ids = {get_creature_affiliation_id(p) for p in preds}
        self.assertEqual(len({x for x in affiliation_ids if x}), 1)
        self.assertEqual(len(world.nest_system.nests), 1)

    def test_initial_predators_spawn_near_nest_anchor(self):
        world = World()
        affiliation_cfg = config.get_species("red_ant").get("affiliation", {})
        from src.sim.utils.affiliation_config_helpers import get_affiliation_profile

        profile = get_affiliation_profile(world, "red_ant")
        anchor_x = float(profile.get("nest_x", world.width * 0.5))
        anchor_y = float(profile.get("nest_y", world.height * 0.5))
        spread = float(profile.get("spawn_spread", affiliation_cfg.get("spawn_spread", 28)))

        preds = [c for c in world.creatures if c.species.name == "red_ant"]
        self.assertGreaterEqual(len(preds), 1)
        nest = world.nest_system.get_affiliation_root("red_ant")
        self.assertIsNotNone(nest)
        for p in preds:
            px, py = entity_xy(p)
            dist = ((px - nest.x) ** 2 + (py - nest.y) ** 2) ** 0.5
            self.assertLessEqual(dist, spread + 5)

    def test_nest_spawn_position_uses_existing_nest(self):
        world = World()
        factory = CreatureFactory()
        affiliation_cfg = config.get_species("red_ant").get("affiliation", {})
        first = factory.create("red_ant", world=world, x=300, y=300)
        world.add_creature(first)
        nest = world.nest_system.get_creature_nest(first)

        x, y = world.nest_system.spawn_position("red_ant", affiliation_cfg)
        dist = distance_to_point(type("_P", (), {"pos": [x, y]})(), nest.x, nest.y)
        spread = float(affiliation_cfg.get("spawn_spread", 28))
        self.assertLessEqual(dist, spread + 1)

    def test_p_spawn_joins_existing_nest(self):
        world = self._empty_world()
        factory = CreatureFactory()
        first = factory.create("red_ant", world=world, x=300, y=300)
        world.add_creature(first)
        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        affiliation_id = get_creature_affiliation_id(first)

        second = factory.create("red_ant", world=world, x=900, y=900)
        world.add_creature(second)
        self.assertEqual(get_creature_affiliation_id(second), affiliation_id)
        self.assertEqual(len(world.nest_system.nests), 1)

    def test_new_nest_gets_initial_stored_food_from_affiliation_cfg(self):
        world = load_test_world(
            name="Test",
            affiliation=affiliation_settings(profiles={}, affiliation_species={}),
        )
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        world.nest_system.assign_creature(
            ant,
            {
                "single_affiliation": True,
                "max_food": 500.0,
                "initial_stored_food": 123.0,
            },
        )
        nest = world.nest_system.get_creature_nest(ant)
        self.assertIsNotNone(nest)
        self.assertAlmostEqual(nest.stored_food, 123.0)
        self.assertAlmostEqual(nest.max_food, 500.0)

    def test_initial_stored_food_clamped_to_max_food(self):
        world = load_test_world(name="Test")
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        world.nest_system.assign_creature(
            ant,
            {
                "single_affiliation": True,
                "max_food": 80.0,
                "initial_stored_food": 999.0,
            },
        )
        nest = world.nest_system.get_creature_nest(ant)
        self.assertAlmostEqual(nest.stored_food, 80.0)

    def test_joining_existing_nest_does_not_reset_stored_food(self):
        world = load_test_world(name="Test")
        factory = CreatureFactory()
        first = factory.create("red_ant", world=world, x=300, y=300)
        world.nest_system.assign_creature(
            first,
            {"single_affiliation": True, "max_food": 400.0, "initial_stored_food": 90.0},
        )
        nest = world.nest_system.get_creature_nest(first)
        nest.stored_food = 50.0

        second = factory.create("red_ant", world=world, x=900, y=900)
        world.nest_system.assign_creature(
            second,
            {"single_affiliation": True, "max_food": 400.0, "initial_stored_food": 200.0},
        )
        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        self.assertEqual(get_creature_affiliation_id(second), nest.affiliation_id)
        self.assertAlmostEqual(nest.stored_food, 50.0)

    def test_hunt_pickup_and_deposit_increases_nest_storage(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        predator = preds[0]
        predator.satiety = predator.max_satiety * 0.95
        nest = world.nest_system.get_creature_nest(predator)

        factory = CreatureFactory()
        prey = factory.create("springtail", world=world, x=0, y=0)
        world.add_creature(prey)
        use_legacy_corpse_on_death(prey)

        px, py = entity_xy(predator)
        prey.pos[0] = px + 12
        prey.pos[1] = py
        if hasattr(prey, "position"):
            prey.position.x = prey.pos[0]
            prey.position.y = prey.pos[1]

        for _ in range(12):
            if not prey.alive:
                break
            try_attack_only(predator, prey, attack_power=2.5)
        self.assertFalse(prey.alive)
        self.assertTrue(has_edible_carcass(prey))

        initial_biomass = prey.remaining_biomass
        self.assertTrue(try_pickup_carcass(predator, prey))
        self.assertTrue(inventory_is_loaded(predator))
        self.assertGreater(total_biomass_amount(predator), 0)
        self.assertLess(prey.remaining_biomass, initial_biomass)

        deposited = world.nest_system.deposit_carried(predator)
        self.assertGreater(deposited, 0)
        self.assertGreater(nest.stored_food, 0)
        self.assertFalse(inventory_is_loaded(predator))

    def test_feed_at_nest_reduces_hunger(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        predator = preds[0]
        nest = world.nest_system.get_creature_nest(predator)
        set_affiliation_stored_food(world, nest.affiliation_id, 200.0)
        predator.satiety = predator.max_satiety * 0.2

        before = hunger_ratio(predator)
        world.nest_system.feed_creature(predator, bite_gain=1.2)
        after = hunger_ratio(predator)
        self.assertLess(after, before)
        self.assertLess(nest.stored_food, 200.0)

    def test_food_leak_reduces_storage(self):
        world = load_test_world(
            name="FoodLeakTest",
            world_width=3000,
            world_height=3000,
            population_limits={"red_ant": 60},
        )
        preds = self._spawn_predators(world, 1)
        nest = world.nest_system.get_creature_nest(preds[0])
        reserve = nest.max_food * float(
            get_affiliation_profile(world, "red_ant")["food_leak_reserve_ratio"]
        )
        set_affiliation_stored_food(world, "red_ant", reserve + 500.0)
        food_before = nest.stored_food

        dt = 10.0
        ticks = 200
        for _ in range(ticks):
            world.nest_system.update(dt)

        self.assertLess(nest.stored_food, food_before)
        leak_per_tick = float(get_affiliation_profile(world, "red_ant")["food_leak_per_tick"])
        expected = reserve + 500.0 - ticks * leak_per_tick * dt
        self.assertAlmostEqual(nest.stored_food, max(reserve, expected))

    def test_feed_per_member_ratio_divides_by_colony_size(self):
        world = World()
        for c in list(world.creatures):
            if c.species.name == "red_ant":
                world.remove_creature(c)
        world.nest_system.clear_all_affiliation_sites()
        preds = self._spawn_predators(world, 3)
        nest = world.nest_system.get_creature_nest(preds[0])
        nest.stored_food = 200.0
        members = world.nest_system.member_count(nest.id, "red_ant")
        self.assertEqual(members, 3)
        solo_cap = 200.0 * 0.14
        shared_cap = 200.0 * 0.14 / members
        self.assertLess(shared_cap, solo_cap)

    def _spawn_colony(self, world, workers: int = 1, *, stored_food=None):
        """?? + ???????????????"""
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen)
        nest = world.nest_system.get_creature_nest(queen)
        if stored_food is not None:
            nest.stored_food = stored_food
        workers_list = []
        for i in range(workers):
            w = factory.create("red_ant", world=world, x=120 + i * 10, y=120)
            world.add_creature(w)
            workers_list.append(w)
        return queen, nest, workers_list

    def _reproduce_params(self):
        from src.game.mind_policy import MindPolicy

        profile = MindPolicy().get_profile("workers_only") or {}
        for action in profile.get("actions", []):
            if action.get("name") == "AffiliationReproduceAction":
                return dict(action.get("params", {}))
        return {}

    def test_spawn_worker_consumes_food_and_adds_member(self):
        world = self._empty_world()
        queen, nest, _ = self._spawn_colony(world, workers=0)
        params = self._reproduce_params()
        cost = _repro_food_cost(params)
        from src.sim.utils.affiliation_config_helpers import get_affiliation_profile, get_min_food_reserve

        reserve = get_min_food_reserve(world)

        set_affiliation_stored_food(world, nest.affiliation_id, reserve + cost + 10)
        members_before = world.nest_system.count_affiliation_members(
            nest.id, _repro_member_species(params)
        )
        food_before = nest.stored_food

        queen.pos[0] = nest.x
        queen.pos[1] = nest.y
        if hasattr(queen, "position"):
            queen.position.x = nest.x
            queen.position.y = nest.y

        from src.sim.ai.actions import AffiliationReproduceAction

        action = AffiliationReproduceAction(**{**params, "spawn_cooldown": 0})
        self.assertTrue(action.execute(queen))

        self.assertEqual(
            world.nest_system.count_affiliation_members(nest.id, _repro_member_species(params)),
            members_before + 1,
        )
        self.assertAlmostEqual(nest.stored_food, food_before - cost)

    def test_spawn_worker_blocked_at_max_workers(self):
        world = self._empty_world()
        params = self._reproduce_params()
        max_members = int(params["max_affiliation_members"])
        queen, nest, _ = self._spawn_colony(world, workers=max_members)
        nest.stored_food = nest.max_food

        from src.sim.ai.actions import AffiliationReproduceAction

        action = AffiliationReproduceAction(**{**params, "spawn_cooldown": 0})
        self.assertFalse(action.can_execute(queen))

    def test_spawn_worker_blocked_below_min_reserve(self):
        world = self._empty_world()
        queen, nest, _ = self._spawn_colony(world, workers=0)
        params = self._reproduce_params()
        cost = _repro_food_cost(params)
        from src.sim.utils.affiliation_config_helpers import get_affiliation_profile, get_min_food_reserve

        reserve = get_min_food_reserve(world)

        nest.stored_food = reserve + cost - 1

        from src.sim.ai.actions import AffiliationReproduceAction

        action = AffiliationReproduceAction(**{**params, "spawn_cooldown": 0})
        self.assertFalse(action.can_execute(queen))

    def test_hunt_utility_positive_when_satiated_regardless_of_nest_fill(self):
        world = self._empty_world()
        preds = self._spawn_predators(world, 1)
        predator = preds[0]
        nest = world.nest_system.get_creature_nest(predator)
        predator.satiety = predator.max_satiety * 0.95

        factory = CreatureFactory()
        prey = factory.create("Spider", world=world, x=0, y=0)
        world.add_creature(prey)
        use_legacy_corpse_on_death(prey)
        px, py = entity_xy(predator)
        prey.pos[0] = px + 20
        prey.pos[1] = py
        if hasattr(prey, "position"):
            prey.position.x = prey.pos[0]
            prey.position.y = prey.pos[1]

        from src.sim.ai.actions import HuntAction

        action = HuntAction(target_types=["springtail", "Spider"])
        for stored in (0.0, nest.max_food * 0.5, nest.max_food):
            nest.stored_food = stored
            with self.subTest(stored_food=stored):
                self.assertGreater(action.calculate_utility(predator), 0.0)

    def test_second_predator_can_pickup_same_carcass_chunk(self):
        world = self._empty_world()
        preds = self._spawn_predators(world, 2)
        carrier, other = preds[0], preds[1]
        factory = CreatureFactory()
        prey = factory.create("springtail", world=world, x=0, y=0)
        world.add_creature(prey)
        use_legacy_corpse_on_death(prey)
        px, py = entity_xy(carrier)
        prey.pos[0] = px + 10
        prey.pos[1] = py
        if hasattr(prey, "position"):
            prey.position.x = prey.pos[0]
            prey.position.y = prey.pos[1]

        for _ in range(12):
            if not prey.alive:
                break
            try_attack_only(carrier, prey, attack_power=2.5)
        self.assertTrue(try_pickup_carcass(carrier, prey))
        first_chunk = total_biomass_amount(carrier)
        remaining_after_first = prey.remaining_biomass

        other.pos[0] = prey.pos[0]
        other.pos[1] = prey.pos[1]
        if hasattr(other, "position"):
            other.position.x = prey.pos[0]
            other.position.y = prey.pos[1]

        self.assertTrue(try_pickup_carcass(other, prey))
        self.assertGreater(total_biomass_amount(other), 0)
        self.assertLess(prey.remaining_biomass, remaining_after_first)
        self.assertGreater(first_chunk, 0)

    def test_deposit_chunk_does_not_double_storage(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        predator = preds[0]
        predator.satiety = predator.max_satiety * 0.95
        nest = world.nest_system.get_creature_nest(predator)
        factory = CreatureFactory()
        prey = factory.create("springtail", world=world, x=0, y=0)
        world.add_creature(prey)
        use_legacy_corpse_on_death(prey)
        px, py = entity_xy(predator)
        prey.pos[0] = px + 10
        prey.pos[1] = py
        if hasattr(prey, "position"):
            prey.position.x = prey.pos[0]
            prey.position.y = prey.pos[1]

        for _ in range(12):
            if not prey.alive:
                break
            try_attack_only(predator, prey, attack_power=2.5)
        self.assertTrue(try_pickup_carcass(predator, prey))
        carried = total_biomass_amount(predator)
        deposited = world.nest_system.deposit_carried(predator)
        self.assertGreater(deposited, 0)
        self.assertAlmostEqual(deposited, carried)
        self.assertFalse(inventory_is_loaded(predator))
        nest.stored_food = 0.0
        second = world.nest_system.deposit_carried(predator)
        self.assertEqual(second, 0.0)

    def test_spawn_worker_action_at_nest(self):
        world = self._empty_world()
        queen, nest, _ = self._spawn_colony(world, workers=0)
        params = self._reproduce_params()
        cost = _repro_food_cost(params)
        from src.sim.utils.affiliation_config_helpers import get_affiliation_profile, get_min_food_reserve

        reserve = get_min_food_reserve(world)
        nest.stored_food = reserve + cost + 50

        queen.pos[0] = nest.x
        queen.pos[1] = nest.y
        if hasattr(queen, "position"):
            queen.position.x = nest.x
            queen.position.y = nest.y

        from src.sim.ai.actions import AffiliationReproduceAction

        action = AffiliationReproduceAction(**{**params, "spawn_cooldown": 0})
        members_before = world.nest_system.count_affiliation_members(
            nest.id, _repro_member_species(params)
        )
        self.assertTrue(action.execute(queen))
        self.assertEqual(
            world.nest_system.count_affiliation_members(nest.id, _repro_member_species(params)),
            members_before + 1,
        )

    def test_find_nest_at_click(self):
        world = World()
        preds = self._spawn_predators(world, 1)
        nest = world.nest_system.get_creature_nest(preds[0])
        ns = world.nest_system

        hit = ns.find_nest_at(nest.x, nest.y, pick_radius=36)
        self.assertIs(hit, nest)

        miss = ns.find_nest_at(nest.x + 200, nest.y + 200, pick_radius=36)
        self.assertIsNone(miss)

    def test_reproduction_readiness_reports_food_shortage(self):
        world = self._empty_world()
        queen, nest, _ = self._spawn_colony(world, workers=0)
        params = self._reproduce_params()
        from src.sim.utils.affiliation_config_helpers import get_affiliation_profile, get_min_food_reserve

        needed = get_min_food_reserve(world) + _repro_food_cost(params)

        from src.sim.ai.actions import AffiliationReproduceAction

        action = AffiliationReproduceAction(**params)

        nest.stored_food = needed - 1
        ok, msg = action.reproduction_readiness(queen)
        self.assertFalse(ok)
        self.assertIn("127", msg)

        nest.stored_food = needed
        ok, msg = action.reproduction_readiness(queen)
        self.assertTrue(ok)
        self.assertIn("10", msg)

    def test_deposit_clears_carry_when_nest_full(self):
        world = self._empty_world()
        preds = self._spawn_predators(world, 1)
        ant = preds[0]
        nest = world.nest_system.get_creature_nest(ant)
        set_affiliation_stored_food(world, nest.affiliation_id, nest.max_food)

        ant.inventory.slots[0].item = BiomassItem(amount=42.0)
        px, py = entity_xy(ant)
        ant.pos[0] = nest.x
        ant.pos[1] = nest.y
        if hasattr(ant, "position"):
            ant.position.x = nest.x
            ant.position.y = nest.y

        deposited = world.nest_system.deposit_carried(ant)
        self.assertEqual(deposited, 0.0)
        self.assertFalse(inventory_is_loaded(ant))
        self.assertAlmostEqual(nest.stored_food, nest.max_food)


if __name__ == "__main__":
    unittest.main()

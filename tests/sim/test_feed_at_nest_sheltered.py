"""Sheltered FeedAtNestAction should still feed.

兵隊アリが shelter 状態で FeedAtNestAction に張り付いて空振りする回帰を防ぐ。
"""
from __future__ import annotations

import unittest

from src.game.ai.colony_actions import FeedAtNestAction
from src.game.affiliation_feed import affiliation_has_usable_storage
from src.game.colony_session import get_colony_orchestrator
from src.game.shelter_helpers import enter_creature_shelter
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.shelter.types import ShelterRef
from src.sim.systems.world import World


def colony(world: World):
    return get_colony_orchestrator(world)


class TestFeedAtNestSheltered(unittest.TestCase):
    def test_sheltered_creature_feeds_even_if_site_distance_check_fails(self):
        world = World()
        factory = CreatureFactory()
        soldier = factory.create("red_ant_soldier", world=world, x=400, y=400)
        world.add_creature(soldier)

        nest = colony(world).get_creature_affiliation_root(soldier)
        nest.stored_mass = 200.0
        soldier.satiety = soldier.max_satiety * 0.05

        # Enter shelter at the nest location.
        ref = ShelterRef(kind="affiliation_access", x=float(nest.x), y=float(nest.y))
        enter_creature_shelter(soldier, ref)

        before = float(soldier.satiety)
        FeedAtNestAction(feed_radius=38).execute(soldier)
        after = float(soldier.satiety)

        self.assertGreater(after, before)

    def test_sheltered_creature_feeds_with_compound_parent_fallback(self):
        """shelter により compound parent が付いても、affiliation root から給餌できる。"""
        world = World()
        factory = CreatureFactory()
        soldier = factory.create("red_ant_soldier", world=world, x=400, y=400)
        world.add_creature(soldier)

        nest = colony(world).get_creature_affiliation_root(soldier)
        nest.stored_mass = 200.0
        soldier.satiety = soldier.max_satiety * 0.05

        # Simulate "sheltered with compound parent": parent ids exist but parent storage is empty.
        # (The exact parent id isn't important; we just want the code path.)
        setattr(soldier, "compound_parent_object_ids", ("red_ant",))
        enter_creature_shelter(
            soldier,
            ShelterRef(kind="compound_access", x=float(nest.x), y=float(nest.y), parent_id="red_ant"),
        )

        self.assertTrue(affiliation_has_usable_storage(soldier))

        before = float(soldier.satiety)
        FeedAtNestAction(feed_radius=38).execute(soldier)
        after = float(soldier.satiety)
        self.assertGreater(after, before)


if __name__ == "__main__":
    unittest.main()


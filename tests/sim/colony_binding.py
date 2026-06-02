"""sim テスト用: game 層 ColonyOrchestrator を World に紐付ける。

`tests/sim/` 内テストは `conftest.py` が `@pytest.mark.no_colony` 以外で自動 bind。
他パッケージは `load_test_world()` または明示的 `bind_colony(world)` を使う。
"""
from __future__ import annotations

from src.game.colony_orchestrator import ColonyOrchestrator
from src.game.colony_session import attach_colony_orchestrator


def bind_colony(world):
    """Bind a ColonyOrchestrator to a World for tests that need colony behavior.

    This sets up the game layer state. For event-driven reactions (e.g. affiliation
    assignment on SpawnEvent), tests should call process_spawns_for_game_reactions(world)
    after manual add_creature calls, or use on_tick / process events.
    We wrap update() for leak/maintenance in tests that call world.update(dt) directly.
    """
    orch = ColonyOrchestrator(world)
    attach_colony_orchestrator(world, orch)

    # Test compat: many sim tests call world.update(dt) directly (not via SimRunner).
    # Wrap to run maintenance (leaks) so tests expecting time-based effects still work.
    # Production/main paths use SimRunner which calls maintenance explicitly.
    orig_update = world.update

    def _update_with_maintenance(self, dt: float = 1.0):
        try:
            orch.update(dt)
        except Exception:
            pass
        return orig_update(dt)

    world.update = _update_with_maintenance.__get__(world, type(world))

    # Test-only: wrap add_creature so that manual adds in tests (very common pattern)
    # immediately trigger game reactions (affiliation assignment via the ensure logic
    # that is used in the real SpawnEvent handler). This keeps tests passing without
    # editing every add site, while the production paths remain event-driven
    # (SpawnEvent -> GameDirector._handle -> ensure).
    orig_add = world.add_creature

    def _add_and_process(self, creature, **kwargs):
        res = orig_add(creature, **kwargs)
        from src.game.colony_session import ensure_creature_affiliations
        ensure_creature_affiliations(self)
        return res

    world.add_creature = _add_and_process.__get__(world, type(world))

    # Also ensure at bind time for spawns during creation.
    from src.game.colony_session import ensure_creature_affiliations
    ensure_creature_affiliations(world)
    return orch


def process_spawns_for_game_reactions(world):
    """Helper for event-driven tests: after manual world.add_creature (which emits SpawnEvent),
    call this to trigger game reactions such as affiliation assignment.

    This simulates what happens in GameDirector when processing SpawnEvents.
    """
    from src.game.colony_session import ensure_creature_affiliations
    ensure_creature_affiliations(world)

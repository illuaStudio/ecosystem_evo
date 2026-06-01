"""ゲーム層 Action 共通: 所属拠点リーシュ・テリトリー・個体ターゲット追跡。"""
from __future__ import annotations

from src.sim.utils.movement_helpers import is_beyond_nest_leash, return_toward_nest


class AffiliationLeashMixin:
    """affiliation_site_leash_radius / nest_leash_radius 超過時に所属拠点へ戻る。"""

    def _nest_leash(self):
        raw = self.params.get("affiliation_site_leash_radius")
        if raw is None:
            raw = self.params.get("nest_leash_radius")
        if raw is None:
            return None
        return float(raw)

    def _abort_if_beyond_nest_leash(self, creature) -> bool:
        if not is_beyond_nest_leash(creature, self._nest_leash()):
            return False
        if hasattr(self, "_target"):
            self._target = None
        return_toward_nest(
            creature,
            speed_multiplier=float(self.params["speed_multiplier"]),
        )
        return True


NestLeashMixin = AffiliationLeashMixin


class TerritoryOnlyMixin:
    def _territory_only(self) -> bool:
        return bool(self.params.get("territory_only"))


class CreatureTargetMixin:
    """_target を保持しながら find / trackable で解決する。"""

    _target = None

    def _resolve_creature_target(self, creature, *, find_fn, trackable_fn):
        if trackable_fn(creature, self._target):
            return self._target
        self._target = find_fn(creature)
        return self._target

    def _clear_target(self) -> None:
        self._target = None

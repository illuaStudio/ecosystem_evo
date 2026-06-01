"""シミュ層の中立な所属（affiliation）ヘルパ。"""
from __future__ import annotations

from typing import Optional


def get_creature_affiliation_id(creature) -> Optional[str]:
    """個体の affiliation_id を返す。未所属なら None。"""
    if creature is None:
        return None
    aff = getattr(creature, "affiliation", None)
    if aff is None:
        return None
    aid = getattr(aff, "affiliation_id", None)
    return str(aid) if aid else None


def set_creature_affiliation_id(creature, affiliation_id: str | None) -> None:
    if creature is None:
        return
    aff = getattr(creature, "affiliation", None)
    if aff is None:
        from src.sim.components.affiliation import AffiliationComponent

        creature.affiliation = AffiliationComponent()
    aff.affiliation_id = str(affiliation_id) if affiliation_id else None


def creature_same_affiliation(a, b) -> bool:
    if a is None or b is None:
        return False
    aid = get_creature_affiliation_id(a)
    bid = get_creature_affiliation_id(b)
    return bool(aid) and aid == bid


def creature_has_tag(creature, tag: str) -> bool:
    aff = getattr(creature, "affiliation", None)
    if aff is None:
        return False
    return str(tag) in aff.tags


def creature_add_tag(creature, tag: str) -> None:
    aff = getattr(creature, "affiliation", None)
    if aff is None:
        return
    t = str(tag).strip()
    if not t:
        return
    aff.tags.add(t)


def creature_has_role(creature, role: str) -> bool:
    aff = getattr(creature, "affiliation", None)
    return aff is not None and aff.has_role(role)


def creature_add_role(creature, role: str) -> None:
    aff = getattr(creature, "affiliation", None)
    if aff is None:
        return
    aff.add_role(role)

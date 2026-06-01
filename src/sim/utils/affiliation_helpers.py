"""シミュ層の中立な所属（affiliation）ヘルパ。

段階移行のため、affiliation が未設定の個体は colony_id をフォールバックとして扱える。
"""

from __future__ import annotations

from typing import Optional


def get_creature_affiliation_id(creature) -> Optional[str]:
    """個体の affiliation_id を返す。無ければ colony_id をフォールバックする。"""
    if creature is None:
        return None
    aff = getattr(creature, "affiliation", None)
    if aff is not None:
        aid = getattr(aff, "affiliation_id", None)
        if aid:
            return str(aid)
    # compat: colony
    col = getattr(creature, "colony", None)
    if col is not None:
        cid = getattr(col, "colony_id", None)
        if cid:
            return str(cid)
    return None


def set_creature_affiliation_id(creature, affiliation_id: str | None) -> None:
    if creature is None:
        return
    aff = getattr(creature, "affiliation", None)
    if aff is None:
        try:
            from src.sim.components.affiliation import AffiliationComponent

            aff = AffiliationComponent()
            creature.affiliation = aff
        except Exception:
            return
    aff.affiliation_id = str(affiliation_id) if affiliation_id else None


def creature_same_affiliation(a, b) -> bool:
    """同じ affiliation_id なら True。どちらか未所属なら False。"""
    if a is None or b is None:
        return False
    aid = get_creature_affiliation_id(a)
    bid = get_creature_affiliation_id(b)
    return bool(aid) and aid == bid


def creature_has_tag(creature, tag: str) -> bool:
    aff = getattr(creature, "affiliation", None)
    if aff is None:
        return False
    tags = getattr(aff, "tags", None)
    if not tags:
        return False
    return str(tag) in tags


def creature_add_tag(creature, tag: str) -> None:
    aff = getattr(creature, "affiliation", None)
    if aff is None:
        return
    if hasattr(aff, "add_tag"):
        aff.add_tag(tag)
        return
    t = str(tag).strip()
    if not t:
        return
    tags = getattr(aff, "tags", None)
    if tags is None:
        aff.tags = {t}
    else:
        tags.add(t)


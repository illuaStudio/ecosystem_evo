"""ゲーム層: コロニー内キャスト（種名サフィックス）判定。"""
from __future__ import annotations

from typing import Literal

AffiliationCaste = Literal["worker", "soldier", "vanguard", "combat", "queen", "member"]

_CASTE_ALIASES: dict[str, AffiliationCaste] = {
    "workers": "worker",
    "soldiers": "soldier",
    "vanguards": "vanguard",
    "queens": "queen",
    "members": "member",
}


def normalize_caste(caste: str) -> AffiliationCaste | None:
    key = str(caste).strip().lower()
    if key in _CASTE_ALIASES:
        return _CASTE_ALIASES[key]
    if key in ("worker", "soldier", "vanguard", "combat", "queen", "member"):
        return key  # type: ignore[return-value]
    return None


def creature_matches_affiliation_caste(creature, affiliation_id: str, caste: AffiliationCaste) -> bool:
    if not affiliation_id or creature is None:
        return False
    from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

    if get_creature_affiliation_id(creature) != affiliation_id:
        return False

    name = creature.species.name
    if caste == "member":
        return True
    if caste == "queen":
        return name.endswith("_queen")
    if caste == "soldier":
        return name.endswith("_soldier")
    if caste == "vanguard":
        return name.endswith("_vanguard")
    if caste == "combat":
        return name.endswith("_soldier") or name.endswith("_vanguard")
    if caste == "worker":
        return not name.endswith(("_soldier", "_vanguard", "_queen"))
    return False


def list_affiliation_caste_species(world, affiliation_id: str, caste: AffiliationCaste) -> tuple[str, ...]:
    if world is None or not affiliation_id:
        return ()

    names: set[str] = set()
    for name in (getattr(world, "affiliation_species", {}) or {}).get(affiliation_id, ()):
        names.add(str(name))

    from src.config import config

    for species_name, data in config.species.items():
        aff_cfg = (data or {}).get("affiliation") or {}
        if not aff_cfg.get("enabled"):
            continue
        from src.sim.utils.territory_helpers import resolve_affiliation_id

        if resolve_affiliation_id(species_name, aff_cfg) == affiliation_id:
            names.add(species_name)

    return tuple(
        name
        for name in sorted(names)
        if _species_name_matches_caste(name, caste)
    )


def _species_name_matches_caste(species_name: str, caste: AffiliationCaste) -> bool:
    if caste == "member":
        return True
    if caste == "queen":
        return species_name.endswith("_queen")
    if caste == "soldier":
        return species_name.endswith("_soldier")
    if caste == "vanguard":
        return species_name.endswith("_vanguard")
    if caste == "combat":
        return species_name.endswith("_soldier") or species_name.endswith("_vanguard")
    if caste == "worker":
        return not species_name.endswith(("_soldier", "_vanguard", "_queen"))
    return False

"""コロニー内の種別（caste）判定。種名サフィックス + affiliation_id で絞る。"""
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
    """個体が指定コロニー・種別に該当するか。"""
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
    """ワールドに存在しうる種名のうち、caste に該当するものを列挙。"""
    if world is None or not affiliation_id:
        return ()

    names: set[str] = set()
    affiliation_species = getattr(world, "affiliation_species", {}) or {}
    for name in affiliation_species.get(affiliation_id, ()):
        names.add(str(name))

    from src.config import config

    for species_name, data in config.species.items():
        aff_cfg = (data or {}).get("affiliation") or {}
        if not aff_cfg.get("enabled"):
            continue
        from src.sim.utils.territory_helpers import resolve_affiliation_id

        if resolve_affiliation_id(species_name, aff_cfg) == affiliation_id:
            names.add(species_name)

    matched = [
        name
        for name in sorted(names)
        if _species_name_matches_caste(name, affiliation_id, caste)
    ]
    return tuple(matched)


def _species_name_matches_caste(species_name: str, affiliation_id: str, caste: AffiliationCaste) -> bool:
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

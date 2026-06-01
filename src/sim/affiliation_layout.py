"""ワールド JSON の affiliation ブロック（sim 内の中立データ）。"""
from __future__ import annotations


class AffiliationLayoutState:
    profiles: dict[str, dict]
    settings: dict
    styles: dict
    species_by_affiliation: dict[str, list]

    def __init__(
        self,
        *,
        profiles: dict[str, dict],
        settings: dict,
        styles: dict,
        species_by_affiliation: dict[str, list],
    ) -> None:
        self.profiles = profiles
        self.settings = settings
        self.styles = styles
        self.species_by_affiliation = species_by_affiliation

    @classmethod
    def from_block(cls, block: dict | None) -> "AffiliationLayoutState":
        affiliation_block = dict(block or {})
        styles = dict(affiliation_block.pop("factions", {}))
        species_by_affiliation = {
            str(k): list(v) if isinstance(v, (list, tuple)) else [v]
            for k, v in (affiliation_block.pop("affiliation_species", {}) or {}).items()
        }
        profiles = {
            str(k): dict(v)
            for k, v in (affiliation_block.pop("profiles", {}) or {}).items()
        }
        return cls(
            profiles=profiles,
            settings=affiliation_block,
            styles=styles,
            species_by_affiliation=species_by_affiliation,
        )

    def get_profile(self, affiliation_id: str) -> dict:
        if not affiliation_id:
            return {}
        return dict(self.profiles.get(affiliation_id) or {})

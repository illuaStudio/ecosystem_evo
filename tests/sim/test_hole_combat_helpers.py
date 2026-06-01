"""test_hole_combat / test_seek_shelter 共通（colony_access 優先）。"""

from __future__ import annotations


def list_colony_access(world, affiliation_id: str):
    return list(world.nest_system.iter_affiliation_access(affiliation_id))


def primary_access(world, affiliation_id: str):
    ws = world.world_object_system
    points = ws.iter_access_points(affiliation_id)
    return points[0] if points else None


def damage_colony_access(world, affiliation_id: str, access, amount: float, *, attacker_affiliation_id: str):
    return world.nest_system.damage_access(
        access, affiliation_id, amount, attacker_affiliation_id=attacker_affiliation_id
    )

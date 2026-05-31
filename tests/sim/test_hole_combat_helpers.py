"""test_hole_combat / test_seek_shelter 共通（colony_access 優先）。"""

from __future__ import annotations


def list_colony_access(world, colony_id: str):
    return list(world.nest_system.iter_colony_access(colony_id))


def primary_access(world, colony_id: str):
    ws = world.world_object_system
    points = ws.iter_access_points(colony_id)
    return points[0] if points else None


def damage_colony_access(world, colony_id: str, access, amount: float, *, attacker_colony_id: str):
    return world.nest_system.damage_access(
        access, colony_id, amount, attacker_colony_id=attacker_colony_id
    )

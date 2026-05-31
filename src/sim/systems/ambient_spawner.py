"""後方互換 re-export。新規コードは spawn_system を使用。"""
from src.sim.systems.spawn_system import (
    SpawnSystem,
    count_alive_in_pool,
    count_alive_in_radius,
)

AmbientSpawner = SpawnSystem

__all__ = [
    "AmbientSpawner",
    "SpawnSystem",
    "count_alive_in_pool",
    "count_alive_in_radius",
]

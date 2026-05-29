"""マナ濃度マップとの相互作用を担当する ECS System。"""
import math
import random
from typing import Any, List, Optional

from src.components.mana_affinity import ManaAffinity
from src.utils.creature_helpers import (
    count_same_species_near,
    same_species_repulsion_angle,
)

SATIETY_CAP_RATIO = 0.95


class ManaSystem:
    """ManaAffinity コンポーネントを持つエンティティのマナ吸収・勾配誘導を処理する。"""

    def update(self, entities: List[Any], world: Any, dt: float = 1.0) -> None:
        """マナ親和性を持つ生存個体のマナ吸収（行動種別に応じて）。"""
        if world is None:
            return

        from src.ai.actions import ManaGradientWanderAction, ManaWanderAction

        for entity in entities:
            if not getattr(entity, "alive", True):
                continue
            affinity = getattr(entity, "mana_affinity", None)
            if not isinstance(affinity, ManaAffinity):
                continue
            action = getattr(entity, "current_action", None)
            if isinstance(action, ManaWanderAction):
                rate = float(
                    action.params.get("mana_absorption_rate", affinity.consumption_rate)
                )
                self.absorb_mana(entity, world, affinity, rate, dt)
            elif isinstance(action, ManaGradientWanderAction):
                rate = float(
                    action.params.get("mana_absorption_rate", affinity.consumption_rate)
                )
                absorbed = self.absorb_mana(entity, world, affinity, rate, dt)
                self._record_absorb_result(entity, world, absorbed, action.params)

    def apply_gradient_steering(
        self,
        entity: Any,
        world: Any,
        params: dict,
    ) -> None:
        """マナ勾配に沿って wander_angle を調整する（ManaGradientWanderAction 用）。"""
        if world is None or not getattr(entity, "alive", True):
            return

        escape = self.should_escape(entity, world, params)

        strength = float(params["gradient_strength"])
        angle_range = float(params["angle_range"])
        speed_multiplier = float(params["speed_multiplier"])

        if escape:
            strength = min(1.0, strength * 1.5)
            angle_range *= 0.35
            speed_multiplier = min(1.4, speed_multiplier * 1.25)

        gradient_dir = self.get_local_gradient_direction(entity, world, params)
        wander_angle = getattr(entity, "wander_angle", 0.0)
        diff = ((gradient_dir - wander_angle + 180) % 360) - 180
        wander_angle = (wander_angle + diff * strength) % 360

        repulsion = same_species_repulsion_angle(
            entity, float(params.get("crowd_radius", 42.0))
        )
        if repulsion is not None:
            blend = float(params.get("crowd_repulsion_strength", 0.35))
            if escape:
                blend = min(0.85, blend * 1.4)
            rep_diff = ((repulsion - wander_angle + 180) % 360) - 180
            wander_angle = (wander_angle + rep_diff * blend) % 360

        entity.wander_angle = wander_angle

        from src.systems.movement_system import MovementSystem

        sim_dt = float(getattr(world, "sim_dt", 1.0))
        MovementSystem.wander_step(
            entity, angle_range, speed_multiplier, sim_dt, world
        )

    def absorb_mana(
        self,
        entity: Any,
        world: Any,
        affinity: ManaAffinity,
        rate: Optional[float] = None,
        dt: float = 1.0,
    ) -> float:
        """現在位置のマナを消費して満腹度を回復。吸収量を返す。"""
        if world is None or not getattr(entity, "alive", True):
            return 0.0

        cap = entity.max_satiety * SATIETY_CAP_RATIO
        if entity.satiety >= cap:
            return 0.0

        consumption = rate if rate is not None else affinity.consumption_rate
        want = min(
            float(consumption) * affinity.affinity * float(dt),
            cap - entity.satiety,
        )
        if want <= 0:
            return 0.0

        position = entity.position
        absorbed = world.mana_layer.consume(want, position.x, position.y)
        if absorbed <= 0:
            return 0.0

        entity.satiety += absorbed
        return absorbed

    @staticmethod
    def should_escape(entity: Any, world: Any, params: dict) -> bool:
        """絶対枯渇・減少率・吸収失敗・密集のいずれかで退避モード。"""
        cap = getattr(world.mana_layer, "mana_density_cap", 2500.0)
        position = entity.position
        local_density = world.mana_layer.get_mana_density(position.x, position.y)
        if local_density < cap * float(params.get("depleted_ratio", 0.12)):
            return True

        rate_threshold = float(params.get("depletion_rate_threshold", 0.08))
        if ManaSystem.local_depletion_rate(entity, world) >= rate_threshold:
            return True

        no_absorb_limit = int(params.get("no_absorb_escape_ticks", 4))
        if getattr(entity, "mana_no_absorb_ticks", 0) >= no_absorb_limit:
            return True

        crowd_radius = float(params.get("crowd_radius", 42.0))
        escape_neighbors = int(params.get("crowd_escape_neighbors", 3))
        neighbors = count_same_species_near(
            entity,
            position.x,
            position.y,
            crowd_radius,
            exclude_self=True,
        )
        return neighbors >= escape_neighbors

    @staticmethod
    def local_depletion_rate(entity: Any, world: Any) -> float:
        """同一セル付近に留まっているときのマナ密度の相対減少率（0〜1）。"""
        position = entity.position
        snap_x = getattr(entity, "mana_steer_snap_x", None)
        snap_y = getattr(entity, "mana_steer_snap_y", None)
        snap_density = getattr(entity, "mana_steer_snap_density", None)
        if snap_x is None or snap_y is None or snap_density is None:
            return 0.0

        cell = float(getattr(world.mana_layer, "mana_cell_size", 16))
        if math.hypot(position.x - snap_x, position.y - snap_y) > cell * 1.5:
            return 0.0

        current = world.mana_layer.get_mana_density(position.x, position.y)
        if snap_density <= 1e-6:
            return 0.0
        return max(0.0, (snap_density - current) / snap_density)

    @staticmethod
    def _record_absorb_result(
        entity: Any, world: Any, absorbed: float, params: dict
    ) -> None:
        """吸収結果と位置のマナ密度を記録（次ティックの退避判定用）。"""
        sat_cap = entity.max_satiety * SATIETY_CAP_RATIO
        hungry = entity.satiety < sat_cap

        if absorbed > 0:
            entity.mana_no_absorb_ticks = 0
        elif hungry:
            entity.mana_no_absorb_ticks = getattr(entity, "mana_no_absorb_ticks", 0) + 1

        position = entity.position
        entity.mana_steer_snap_x = position.x
        entity.mana_steer_snap_y = position.y
        entity.mana_steer_snap_density = world.mana_layer.get_mana_density(
            position.x, position.y
        )

    @staticmethod
    def _crowd_penalty_at(
        entity: Any, world: Any, x: float, y: float, params: dict
    ) -> float:
        radius = float(params.get("crowd_radius", 42.0))
        per_neighbor = float(params.get("crowd_sample_penalty", 28.0))
        count = count_same_species_near(
            entity, x, y, radius, exclude_self=True
        )
        return count * per_neighbor

    @staticmethod
    def get_local_gradient_direction(
        entity: Any,
        world: Any,
        params: dict,
    ) -> float:
        """
        局所的なマナ密度勾配を計算して移動方向（度数）を返す。
        creature_helpers.get_local_mana_gradient_direction の ECS 版。
        """
        if (
            not world
            or not hasattr(world.mana_layer, "mana_density")
            or not world.mana_layer.mana_density
        ):
            return getattr(entity, "wander_angle", random.uniform(0, 360))

        wander_angle = getattr(entity, "wander_angle", 0.0)
        cap = getattr(world.mana_layer, "mana_density_cap", 2500.0)
        position = entity.position
        current_density = world.mana_layer.get_mana_density(position.x, position.y)
        escape = ManaSystem.should_escape(entity, world, params) or (
            current_density < cap * float(params.get("depleted_ratio", 0.12))
        )

        radius = float(params.get("local_gradient_radius", 35.0))
        samples = int(params.get("local_gradient_samples", 8))
        escape_radius = float(params.get("escape_radius", 96.0))

        best_score = float("-inf")
        best_angle = wander_angle

        if escape:
            search_radii = [radius, escape_radius, escape_radius * 1.5]
            sample_count = max(samples, 12)
        else:
            search_radii = [radius]
            sample_count = samples

        for search_radius in search_radii:
            for i in range(sample_count):
                angle = (wander_angle + (i * 360.0 / sample_count) - 180.0) % 360.0
                rad = math.radians(angle)

                tx = position.x + math.cos(rad) * search_radius
                ty = position.y + math.sin(rad) * search_radius

                tx = max(0, min(world.width, tx))
                ty = max(0, min(world.height, ty))

                sample_density = world.mana_layer.get_mana_density(tx, ty)
                gradient = sample_density - current_density
                angle_diff = min(abs((angle - wander_angle + 180) % 360 - 180), 90)
                crowd_penalty = ManaSystem._crowd_penalty_at(
                    entity, world, tx, ty, params
                )

                if escape:
                    dist_penalty = search_radius * 0.0015
                    score = (
                        sample_density * 2.0
                        - angle_diff * 0.08
                        - dist_penalty
                        - crowd_penalty
                    )
                else:
                    score = (
                        gradient * 1.2
                        + sample_density * 0.05
                        - angle_diff * 0.12
                        - crowd_penalty * 0.65
                    )

                if score > best_score:
                    best_score = score
                    best_angle = angle

        return best_angle

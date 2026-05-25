"""マナ濃度マップとの相互作用を担当する ECS System。"""
import math
import random
from typing import Any, List, Optional

from src.components.mana_affinity import ManaAffinity

SATIETY_CAP_RATIO = 0.95


class ManaSystem:
    """ManaAffinity コンポーネントを持つエンティティのマナ吸収・勾配誘導を処理する。"""

    def update(self, entities: List[Any], world: Any, dt: float = 1.0) -> None:
        """マナ親和性を持つ生存個体のマナ吸収（行動種別に応じて）。"""
        del dt
        if world is None:
            return

        from src.ai.actions import ManaGradientWanderAction

        for entity in entities:
            if not getattr(entity, "alive", True):
                continue
            affinity = getattr(entity, "mana_affinity", None)
            if not isinstance(affinity, ManaAffinity):
                continue
            action = getattr(entity, "current_action", None)
            if not isinstance(action, ManaGradientWanderAction):
                continue
            rate = float(action.params.get("mana_absorption_rate", affinity.consumption_rate))
            self.absorb_mana(entity, world, affinity, rate)

    def apply_gradient_steering(
        self,
        entity: Any,
        world: Any,
        params: dict,
    ) -> None:
        """マナ勾配に沿って wander_angle を調整する（ManaGradientWanderAction 用）。"""
        if world is None or not getattr(entity, "alive", True):
            return

        cap = getattr(world, "mana_density_cap", 2500.0)
        position = entity.position
        local_density = world.get_mana_density(position.x, position.y)
        depleted = local_density < cap * float(params["depleted_ratio"])

        strength = float(params["gradient_strength"])
        angle_range = float(params["angle_range"])
        speed_multiplier = float(params["speed_multiplier"])

        if depleted:
            strength = min(1.0, strength * 1.5)
            angle_range *= 0.35
            speed_multiplier = min(1.4, speed_multiplier * 1.25)

        gradient_dir = self.get_local_gradient_direction(entity, world, params)
        wander_angle = getattr(entity, "wander_angle", 0.0)
        diff = ((gradient_dir - wander_angle + 180) % 360) - 180
        entity.wander_angle = (wander_angle + diff * strength) % 360

        from src.systems.movement_system import MovementSystem

        MovementSystem.wander_step(entity, angle_range, speed_multiplier)

    def absorb_mana(
        self,
        entity: Any,
        world: Any,
        affinity: ManaAffinity,
        rate: Optional[float] = None,
    ) -> float:
        """現在位置のマナを消費して満腹度を回復。吸収量を返す。"""
        if world is None or not getattr(entity, "alive", True):
            return 0.0

        cap = entity.max_satiety * SATIETY_CAP_RATIO
        if entity.satiety >= cap:
            return 0.0

        consumption = rate if rate is not None else affinity.consumption_rate
        want = min(float(consumption) * affinity.affinity, cap - entity.satiety)
        if want <= 0:
            return 0.0

        position = entity.position
        absorbed = world.consume_mana(want, position.x, position.y)
        if absorbed <= 0:
            return 0.0

        entity.satiety += absorbed
        return absorbed

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
            or not hasattr(world, "mana_density")
            or not world.mana_density
        ):
            return getattr(entity, "wander_angle", random.uniform(0, 360))

        wander_angle = getattr(entity, "wander_angle", 0.0)
        cap = getattr(world, "mana_density_cap", 2500.0)
        position = entity.position
        current_density = world.get_mana_density(position.x, position.y)
        depleted = current_density < cap * float(params["depleted_ratio"])

        radius = float(params.get("local_gradient_radius", 35.0))
        samples = int(params.get("local_gradient_samples", 8))
        escape_radius = float(params.get("escape_radius", 96.0))

        best_score = float("-inf")
        best_angle = wander_angle

        if depleted:
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

                sample_density = world.get_mana_density(tx, ty)
                gradient = sample_density - current_density
                angle_diff = min(abs((angle - wander_angle + 180) % 360 - 180), 90)

                if depleted:
                    dist_penalty = search_radius * 0.0015
                    score = sample_density * 2.0 - angle_diff * 0.08 - dist_penalty
                else:
                    score = gradient * 1.2 + sample_density * 0.05 - angle_diff * 0.12

                if score > best_score:
                    best_score = score
                    best_angle = angle

        return best_angle

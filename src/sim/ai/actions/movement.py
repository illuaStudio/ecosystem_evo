from src.sim.ai.actions.base import Action
from src.sim.utils.creature_helpers import (
    closeness_ratio,
    find_nearest_flee_threat_among,
    hunger_ratio,
    is_flee_latch_active,
    is_flee_threat,
    is_in_vision,
    move_away_from,
    needs_self_feed,
    update_flee_latch,
    wander_step,
)


class WanderAction(Action):
    DEFAULT_PARAMS = {
        "angle_range": 30,
        "speed_multiplier": 0.85,
    }

    def execute(self, creature) -> bool:
        wander_step(
            creature,
            self.params["angle_range"],
            self.params["speed_multiplier"],
        )
        return False

    def calculate_utility(self, creature) -> float:
        colony = getattr(creature, "colony", None)
        if colony is not None and needs_self_feed(creature):
            return 0.0
        return 0.6


class ManaWanderAction(Action):
    """自由徘徊しながらマナを吸収。濃い場所は鈍く、薄い場所は活発にランダム探索。"""

    DEFAULT_PARAMS = {
        "angle_range_sparse": 32,
        "angle_range_dense": 12,
        "speed_multiplier_sparse": 1.0,
        "speed_multiplier_dense": 0.35,
        "mana_absorption_rate": 0.75,
    }

    def execute(self, creature) -> bool:
        p = self.params
        world = creature.world
        if world is None:
            wander_step(
                creature,
                p["angle_range_sparse"],
                p["speed_multiplier_sparse"],
            )
            return False

        cap = max(1.0, float(getattr(world.mana_layer, "mana_density_cap", 2500.0)))
        pos = creature.position
        density = world.mana_layer.get_mana_density(pos.x, pos.y)
        t = min(1.0, max(0.0, density / cap))

        angle = p["angle_range_sparse"] + (p["angle_range_dense"] - p["angle_range_sparse"]) * t
        speed = p["speed_multiplier_sparse"] + (
            p["speed_multiplier_dense"] - p["speed_multiplier_sparse"]
        ) * t
        wander_step(creature, angle, speed)
        return False

    def calculate_utility(self, creature) -> float:
        hunger = hunger_ratio(creature)
        return 0.75 + hunger * 0.25


class ManaGradientWanderAction(Action):
    """マナの濃い方向へ移動傾向を強めた徘徊行動。
    局所勾配に従い、周囲の残量変化を見ながら少しずつ移動する。"""

    SATIETY_CAP_RATIO = 0.95

    DEFAULT_PARAMS = {
        "angle_range": 45,
        "speed_multiplier": 0.9,
        "mana_absorption_rate": 0.75,
        "gradient_strength": 0.65,
        "local_gradient_radius": 35.0,
        "local_gradient_samples": 8,
        "escape_radius": 96.0,
        "depleted_ratio": 0.12,
        "depletion_rate_threshold": 0.08,
        "no_absorb_escape_ticks": 4,
        "crowd_radius": 42.0,
        "crowd_escape_neighbors": 3,
        "crowd_sample_penalty": 28.0,
        "crowd_repulsion_strength": 0.35,
    }

    def execute(self, creature) -> bool:
        world = creature.world
        if world is None or getattr(world, "mana_system", None) is None:
            wander_step(creature, self.params["angle_range"], self.params["speed_multiplier"])
            return False

        world.mana_system.apply_gradient_steering(creature, world, self.params)
        return False

    def calculate_utility(self, creature) -> float:
        hunger = hunger_ratio(creature)
        return 0.75 + hunger * 0.25


class FleeAction(Action):
    """指定種（兵隊蟻・クモ等）から離れる。"""

    DEFAULT_PARAMS = {
        "threat_species": (),
        "speed_multiplier": 1.5,
        "safe_distance_ratio": 0.55,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._threat = None

    def _threats(self) -> tuple[str, ...]:
        raw = self.params.get("threat_species") or ()
        return tuple(raw)

    def execute(self, creature) -> bool:
        threats = self._threats()
        if not threats or not creature.world:
            return False

        update_flee_latch(creature, threats)
        if not is_flee_latch_active(creature):
            return False

        threat = self._resolve_threat(creature, threats)
        if threat is None:
            return False

        move_away_from(
            creature,
            threat,
            speed_multiplier=float(self.params["speed_multiplier"]),
        )
        return False

    def calculate_utility(self, creature) -> float:
        threats = self._threats()
        if not threats:
            return 0.0

        update_flee_latch(creature, threats)
        if is_flee_latch_active(creature):
            return 1.0

        threat = find_nearest_flee_threat_among(
            creature, threats, exclude=creature
        )
        if threat is None:
            return 0.0

        closeness = closeness_ratio(creature, threat)
        return min(1.0, 0.7 + closeness * 0.3)

    def _resolve_threat(self, creature, threats: tuple[str, ...]):
        if (
            self._threat is not None
            and is_flee_threat(creature, self._threat, threats)
            and is_in_vision(creature, self._threat)
        ):
            return self._threat
        self._threat = find_nearest_flee_threat_among(
            creature, threats, exclude=creature
        )
        return self._threat

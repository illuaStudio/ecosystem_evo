"""ライフステージ・個体差表示・個体数上限。"""
import math

from src.sim.utils.geo_helpers import distance_between
from src.sim.utils.position_helpers import entity_xy

def current_size(creature) -> float:
    """現在の表示・判定サイズ（traits.base_size）。"""
    return float(creature.traits.get("base_size", 9.0))

LIFE_STAGE_PIPELINE = [
    ("Juvenile", "mature"),
    ("Adult", "elder"),
    ("Elder", "death"),
]

def get_life_stage(age: int, life_cycle: dict) -> str:
    """
    life_cycle 方式のライフステージ判定（LIFE_STAGE_PIPELINE 参照）。

    例: mature=280 → age<280 は Juvenile, elder=1800 → Adult, death=3500 → Elder
    age >= death は LifeCycleManager で自然死（表示用 Expired）

    # 使用例
    stage = get_life_stage(creature.age, creature.life_cycle)
    """
    if not life_cycle:
        return "Adult"

    for stage_name, next_key in LIFE_STAGE_PIPELINE:
        limit = life_cycle.get(next_key)
        if limit is None:
            continue
        if age < int(limit):
            return stage_name
    return "Expired"

def format_life_stage_line(creature) -> str | None:
    """
    選択個体 UI 用の1行テキスト（life_cycle がある種のみ表示）。
    例: Adult (Age: 1243 / 3500) / Juvenile → Mature in 87 ticks
    """
    life_cycle = creature.life_cycle
    if not life_cycle:
        return None

    stage = get_life_stage(creature.age, life_cycle)
    death = int(life_cycle.get("death", 0))

    if stage == "Juvenile":
        mature_at = int(life_cycle.get("mature", 0))
        ticks = max(0, mature_at - creature.age)
        return f"ライフステージ: {stage} → Mature in {ticks} ticks"

    if death > 0:
        return f"ライフステージ: {stage} (Age: {creature.age} / {death})"
    return f"ライフステージ: {stage} (Age: {creature.age})"

TRAIT_DISPLAY_LABELS = {
    "base_size": "サイズ(base)",
    "max_size": "サイズ上限",
    "growth_rate": "成長率",
    "base_speed": "基礎速度",
    "base_vision": "視界",
    "max_hp": "最大HP",
    "max_satiety": "最大満腹",
    "metabolism_per_tick": "代謝/tick",
    "starvation_hp_per_tick": "飢餓HP/tick",
    "corpse_decompose_rate": "死骸分解",
    "satiety_hungry_below": "飢餓閾値",
    "satiety_full_above": "満腹閾値",
}

def _format_trait_number(value: float) -> str:
    av = abs(value)
    if av >= 100:
        return f"{value:.0f}"
    if av >= 10:
        return f"{value:.1f}"
    if av >= 1:
        return f"{value:.2f}"
    return f"{value:.4f}"

def _format_trait_delta(delta: float) -> str:
    if abs(delta) < 1e-9:
        return "±0"
    sign = "+" if delta > 0 else ""
    return f"{sign}{_format_trait_number(delta)}"

def format_individual_trait_lines(creature) -> list[str]:
    """選択個体 UI 用: trait_variance 対象の実値・種基本値・差分（全種同一順）。"""
    from src.sim.entities.species import INDIVIDUAL_TRAIT_DISPLAY_ORDER

    variance = getattr(creature.species, "trait_variance", None) or {}
    if not variance:
        return []

    base_traits = creature.species.traits
    lines: list[str] = []
    for key in INDIVIDUAL_TRAIT_DISPLAY_ORDER:
        if key not in variance or key not in creature.traits:
            continue
        actual = float(creature.traits[key])
        base = float(base_traits.get(key, actual))
        label = TRAIT_DISPLAY_LABELS.get(key, key)
        delta_str = _format_trait_delta(actual - base)
        lines.append(
            f"  {label}: {_format_trait_number(actual)}"
            f" (基本 {_format_trait_number(base)}, Δ{delta_str})"
        )
    return lines

def count_alive_by_species(world, species_name: str) -> int:
    """ワールド上の生存個体数（種族名で集計）。"""
    if world is None:
        return 0
    count = 0
    for other in world.creatures:
        if not getattr(other, "alive", True):
            continue
        if other.species.name != species_name:
            continue
        count += 1
    return count

def get_species_population_cap(world, species_name: str) -> int | None:
    """ワールド JSON の population_limits における種族上限。"""
    if world is None:
        return None
    getter = getattr(world, "get_population_cap", None)
    if callable(getter):
        return getter(species_name)
    limits = getattr(world, "population_limits", None) or {}
    raw = limits.get(species_name)
    if raw is None:
        return None
    cap = int(raw)
    return cap if cap > 0 else None

def is_species_at_population_cap(world, species_name: str) -> bool:
    """ワールド個体数上限に達しているか（未設定は上限なし）。"""
    cap = get_species_population_cap(world, species_name)
    if cap is None:
        return False
    return count_alive_by_species(world, species_name) >= cap

def is_at_population_cap(creature) -> bool:
    """個体の種族がワールド個体数上限に達しているか。"""
    if not creature.world:
        return False
    return is_species_at_population_cap(creature.world, creature.species.name)
